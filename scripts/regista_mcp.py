#!/usr/bin/env python3
"""MCP server: read-only access to the regista PostgreSQL event log.

Exposes three tools:
  list_golden_runs   — enumerate sf2_golden_* schemas with work-item counts
  golden_run_summary — state distribution + per-(role,gate) pass rates for one run
  get_failure_modes  — ranked failure modes (gate + diagnostic_kind) for one run

Connection: reads REGISTA_DSN env var, defaults to the local test DSN.
"""
from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager

DSN = os.environ.get(
    "REGISTA_DSN",
    "postgresql://regista_test:regista_test@localhost:5432/regista_test",
)

# ---------------------------------------------------------------------------
# MCP protocol helpers
# ---------------------------------------------------------------------------


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _error_response(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _ok(req_id, text: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {"content": [{"type": "text", "text": text}]},
    }


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


@contextmanager
def _conn():
    import psycopg

    conn = psycopg.connect(DSN)
    try:
        yield conn
    finally:
        conn.close()


def _golden_schemas(conn) -> list[str]:
    cur = conn.cursor()
    cur.execute(
        "SELECT schema_name FROM information_schema.schemata "
        "WHERE schema_name LIKE 'sf2_golden_%' OR schema_name LIKE 'sf2_p5_%' "
        "ORDER BY schema_name"
    )
    return [r[0] for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def tool_list_golden_runs(_args: dict) -> str:
    with _conn() as conn:
        schemas = _golden_schemas(conn)
        if not schemas:
            return "No golden-run schemas found."
        rows = ["schema | work_items | locked | cannot_proceed | new"]
        rows.append("-" * 70)
        cur = conn.cursor()
        for schema in schemas:
            try:
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE current_state = 'locked') AS locked,
                        COUNT(*) FILTER (WHERE current_state = 'cannot_proceed') AS cannot_proceed,
                        COUNT(*) FILTER (WHERE current_state = 'new') AS new_state
                    FROM {schema}.work_items_current
                    """
                )
                total, locked, cp, new_s = cur.fetchone()
                rows.append(f"{schema} | {total} | {locked} | {cp} | {new_s}")
            except Exception as exc:
                rows.append(f"{schema} | (error: {exc})")
        return "\n".join(rows)


def tool_golden_run_summary(args: dict) -> str:
    schema = args.get("schema", "").strip()
    if not schema:
        return "Required argument: schema (e.g. 'sf2_golden_038')"
    with _conn() as conn:
        schemas = _golden_schemas(conn)
        if schema not in schemas:
            return f"Unknown schema '{schema}'. Known: {', '.join(schemas[-10:])}"
        cur = conn.cursor()

        # State distribution
        cur.execute(
            f"""
            SELECT work_item_type, current_state, COUNT(*)
            FROM {schema}.work_items_current
            GROUP BY work_item_type, current_state
            ORDER BY work_item_type, current_state
            """
        )
        state_rows = cur.fetchall()

        # Pass rates by (role, gate_name) from submit events
        cur.execute(
            f"""
            SELECT
                e.actor_metadata->>'role' AS role,
                e.payload->>'gate_name' AS gate_name,
                COUNT(*) FILTER (WHERE (e.payload->>'passed')::boolean = true) AS passed,
                COUNT(*) AS total
            FROM {schema}.events e
            WHERE e.transition IN ('gate_pass', 'gate_fail')
              AND e.payload IS NOT NULL
            GROUP BY role, gate_name
            ORDER BY role, gate_name
            """
        )
        rate_rows = cur.fetchall()

        lines = [f"=== {schema} ===", "", "State distribution:"]
        for wi_type, state, count in state_rows:
            lines.append(f"  {wi_type:30s}  {state:20s}  {count}")

        lines += ["", "Gate pass rates (role | gate | passed/total | %):"]
        for role, gate_name, passed, total in rate_rows:
            pct = round(100 * passed / total) if total else 0
            lines.append(f"  {(role or '?'):30s}  {(gate_name or '?'):35s}  {passed}/{total}  {pct}%")

        return "\n".join(lines)


def tool_get_failure_modes(args: dict) -> str:
    schema = args.get("schema", "").strip()
    limit = int(args.get("limit", 20))
    if not schema:
        return "Required argument: schema (e.g. 'sf2_golden_038')"
    with _conn() as conn:
        schemas = _golden_schemas(conn)
        if schema not in schemas:
            return f"Unknown schema '{schema}'. Known: {', '.join(schemas[-10:])}"
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                e.actor_metadata->>'role' AS role,
                e.payload->>'gate_name' AS gate_name,
                e.payload->'diagnostics'->>'diagnostic_kind' AS diagnostic_kind,
                COUNT(*) AS occurrences
            FROM {schema}.events e
            WHERE e.transition = 'gate_fail'
              AND e.payload IS NOT NULL
            GROUP BY role, gate_name, diagnostic_kind
            ORDER BY occurrences DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
        if not rows:
            return f"No gate failures found in {schema}."
        lines = [f"Top failure modes in {schema} (role | gate | kind | count):"]
        for role, gate_name, diag_kind, count in rows:
            lines.append(
                f"  {(role or '?'):30s}  {(gate_name or '?'):35s}  {(diag_kind or '?'):30s}  {count}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "list_golden_runs",
        "description": (
            "List all sf2 golden-run schemas in the regista database with "
            "work-item counts and state breakdown (locked / cannot_proceed / new). "
            "Use this first to discover available run names."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "golden_run_summary",
        "description": (
            "For a specific golden run, show: (1) work-item state distribution by type, "
            "(2) gate pass rates by (role, gate_name). "
            "Useful for assessing run quality and identifying weak stages."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schema": {
                    "type": "string",
                    "description": "Schema name, e.g. 'sf2_golden_038'",
                }
            },
            "required": ["schema"],
        },
    },
    {
        "name": "get_failure_modes",
        "description": (
            "For a specific golden run, return the top N gate failure modes ranked by "
            "frequency, broken down by (role, gate_name, diagnostic_kind). "
            "Use this to identify the dominant failure patterns in a run."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schema": {
                    "type": "string",
                    "description": "Schema name, e.g. 'sf2_golden_038'",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return (default 20)",
                    "default": 20,
                },
            },
            "required": ["schema"],
        },
    },
]

TOOL_FNS = {
    "list_golden_runs": tool_list_golden_runs,
    "golden_run_summary": tool_golden_run_summary,
    "get_failure_modes": tool_get_failure_modes,
}

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method", "")

        if method == "initialize":
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "regista-eventlog", "version": "1.0.0"},
                },
            })

        elif method == "notifications/initialized":
            pass  # no response needed

        elif method == "tools/list":
            _send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})

        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name", "")
            args = params.get("arguments", {})
            fn = TOOL_FNS.get(name)
            if fn is None:
                _send(_error_response(req_id, -32601, f"Unknown tool: {name}"))
            else:
                try:
                    text = fn(args)
                    _send(_ok(req_id, text))
                except Exception as exc:
                    _send(_ok(req_id, f"Error: {exc}"))

        elif method == "ping":
            _send({"jsonrpc": "2.0", "id": req_id, "result": {}})

        else:
            _send(_error_response(req_id, -32601, f"Method not found: {method}"))


if __name__ == "__main__":
    main()
