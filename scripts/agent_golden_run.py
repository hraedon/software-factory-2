#!/usr/bin/env python3
"""Agent-mediated golden run wrapper — BC-140 safety protocol.

Encapsulates the pre-flight checklist, workspace isolation, process supervision,
and monitoring guardrails required for unattended agent execution of factory
golden runs. Never touches application state stores (e.g. opencode DB).

Usage:
    python scripts/agent_golden_run.py --config golden-run-NNN-config.yaml \
        --fixtures tests/fixtures/cert-watch-mini

The script will:
1. Validate pre-flight checks (open critical/high breadcrumbs, attempt_threshold, workspace root)
2. Populate work items
3. Launch runner + gate + scheduler from /tmp (never from repo root)
4. Monitor logs every 30s for danger signals
5. Pause and print a loud warning if any guardrail trips
6. Run telemetry when processes go idle
7. Offer to clean up workspace + logs (never the opencode DB)
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path("/projects/software-factory-2")
BREADCRUMBS_README = REPO_ROOT / "breadcrumbs" / "README.md"
AGENTS_MD = REPO_ROOT / "AGENTS.md"

DANGER_SIGNALS = [
    ("claim_near_budget", re.compile(r"claim_near_budget")),
    ("gate_fail_cross_family_review", re.compile(r"gate_failed.*cross_family_review")),
    ("gate_fail_jury", re.compile(r"gate_failed.*jury")),
    ("channel_invoke_failed", re.compile(r"channel_invoke_failed")),
]


def _fatal(msg: str) -> None:
    print(f"[FATAL] {msg}", file=sys.stderr)
    sys.exit(1)


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"[INFO] {msg}")


def _check_open_breadcrumbs() -> list[str]:
    """Return list of open critical/high breadcrumbs from README."""
    if not BREADCRUMBS_README.exists():
        _warn("breadcrumbs/README.md not found — skipping pre-flight check")
        return []

    content = BREADCRUMBS_README.read_text()
    critical_high: list[str] = []
    in_open = False
    for line in content.splitlines():
        if "## Open" in line:
            in_open = True
            continue
        if in_open and line.startswith("## "):
            in_open = False
            continue
        if in_open and line.startswith("|") and "critical" in line.lower():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 5 and parts[1].isdigit():
                critical_high.append(f"BC-{parts[1]} ({parts[3]}): {parts[2]}")
        if in_open and line.startswith("|") and "high" in line.lower():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 5 and parts[1].isdigit():
                critical_high.append(f"BC-{parts[1]} ({parts[3]}): {parts[2]}")

    return critical_high


def _validate_config(config_path: Path) -> dict:
    """Read config YAML and return key safety fields."""
    try:
        import yaml
    except ImportError:
        _fatal("PyYAML required: pip install pyyaml")

    data = yaml.safe_load(config_path.read_text())
    return {
        "project_name": data.get("project_name", "unknown"),
        "workspace_root": data.get("workspace_root", ""),
        "attempt_threshold": data.get("attempt_threshold", 999),
        "workflow_version": data.get("workflow_version", 0),
        "inner_gate_retries": data.get("inner_gate_retries", 0),
        "jury_quorum": data.get("jury_quorum", 0),
    }


def _preflight(config_path: Path, fixtures: str | None) -> None:
    """Run BC-140 pre-flight checklist. Abort on any failure."""
    _info("=== Pre-flight checklist ===")

    # 1. Check open critical/high breadcrumbs
    open_items = _check_open_breadcrumbs()
    critical_items = [b for b in open_items if "critical" in b.lower()]
    if critical_items:
        _fatal(
            "Open CRITICAL breadcrumbs found — do not run until resolved:\n"
            + "\n".join(f"  - {item}" for item in critical_items)
        )
    if open_items:
        _warn("Open HIGH/MEDIUM breadcrumbs:\n" + "\n".join(f"  - {item}" for item in open_items))
    else:
        _info("No open critical/high breadcrumbs.")

    # 2. Validate config
    cfg = _validate_config(config_path)
    _info(
        f"Config: project={cfg['project_name']} "
        f"workflow_version={cfg['workflow_version']} "
        f"jury_quorum={cfg['jury_quorum']}"
    )

    if cfg["attempt_threshold"] > 3:
        _fatal(
            f"attempt_threshold={cfg['attempt_threshold']} is > 3. "
            "Reduce to ≤3 before running."
        )
    _info(f"attempt_threshold={cfg['attempt_threshold']} ✓")

    if cfg["inner_gate_retries"] > 2:
        _warn(
            f"inner_gate_retries={cfg['inner_gate_retries']} is > 2. "
            "Consider reducing."
        )
    else:
        _info(f"inner_gate_retries={cfg['inner_gate_retries']} ✓")

    # 3. Workspace root outside repo
    wr = Path(cfg["workspace_root"]).resolve()
    repo = REPO_ROOT.resolve()
    if repo in wr.parents or wr == repo:
        _fatal(
            f"workspace_root={wr} is inside the repo. "
            "Must be outside (e.g. /tmp/sf2-golden-NNN)."
        )
    _info(f"workspace_root={wr} ✓ (outside repo)")

    # 4. Fixtures exist
    if fixtures:
        fp = REPO_ROOT / fixtures
        if not fp.exists():
            _fatal(f"Fixtures path does not exist: {fp}")
        _info(f"Fixtures={fixtures} ✓")

    _info("=== Pre-flight passed ===")


def _populate(config_path: Path, fixtures: str | None) -> None:
    """Run populate_work_items.py from repo root."""
    _info("Populating work items...")
    cmd = [
        sys.executable,
        str(REPO_ROOT / "populate_work_items.py"),
        "--config", str(config_path),
        "--reset",
    ]
    if fixtures:
        cmd += ["--fixtures", str(REPO_ROOT / fixtures)]
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        _fatal(f"populate_work_items failed:\n{result.stderr}")
    _info("Populate complete.")


def _launch_processes(
    config_path: Path, log_prefix: str
) -> tuple[subprocess.Popen, subprocess.Popen, subprocess.Popen]:
    """Launch runner, gate, scheduler from /tmp. Returns Popen objects."""
    _info("Launching pipeline processes from /tmp...")
    runner_log = Path(f"/tmp/{log_prefix}-runner.log")
    gate_log = Path(f"/tmp/{log_prefix}-gate.log")
    sched_log = Path(f"/tmp/{log_prefix}-scheduler.log")

    # Clean old logs
    for p in (runner_log, gate_log, sched_log):
        p.unlink(missing_ok=True)

    runner = subprocess.Popen(
        [sys.executable, "-m", "factory.runner", "--config", str(config_path)],
        stdout=open(runner_log, "w"),
        stderr=subprocess.STDOUT,
        cwd="/tmp",
    )
    gate = subprocess.Popen(
        [sys.executable, "-m", "factory.gate_process", "--config", str(config_path)],
        stdout=open(gate_log, "w"),
        stderr=subprocess.STDOUT,
        cwd="/tmp",
    )
    scheduler = subprocess.Popen(
        [sys.executable, "-m", "factory.scheduler", "--config", str(config_path)],
        stdout=open(sched_log, "w"),
        stderr=subprocess.STDOUT,
        cwd="/tmp",
    )

    _info(f"Runner PID={runner.pid}, Gate PID={gate.pid}, Scheduler PID={scheduler.pid}")
    _info(f"Logs: {runner_log}, {gate_log}, {sched_log}")
    return runner, gate, scheduler


def _monitor_logs(log_prefix: str, interval: int = 30) -> None:
    """Tail logs every N seconds and check for danger signals."""
    runner_log = Path(f"/tmp/{log_prefix}-runner.log")
    gate_log = Path(f"/tmp/{log_prefix}-gate.log")
    sched_log = Path(f"/tmp/{log_prefix}-scheduler.log")

    seen_counts: dict[str, int] = {name: 0 for name, _ in DANGER_SIGNALS}
    last_line_counts: dict[str, int] = {}

    _info("Monitoring logs (Ctrl+C to interrupt, processes continue in background)...")
    idle_cycles = 0
    max_idle_cycles = 3  # 3 * interval = ~90s of no new lines

    while True:
        time.sleep(interval)

        # Check for new lines and danger signals
        any_new_lines = False
        for log_path in (runner_log, gate_log, sched_log):
            if not log_path.exists():
                continue
            lines = log_path.read_text().splitlines()
            prev = last_line_counts.get(str(log_path), 0)
            new_lines = lines[prev:]
            if new_lines:
                any_new_lines = True
                last_line_counts[str(log_path)] = len(lines)
                for name, pattern in DANGER_SIGNALS:
                    count = sum(1 for line in new_lines if pattern.search(line))
                    if count:
                        seen_counts[name] += count

        if not any_new_lines:
            idle_cycles += 1
            if idle_cycles >= max_idle_cycles:
                _info("No new log lines for >90s — processes appear idle.")
                return
        else:
            idle_cycles = 0

        # Alert on danger signals
        for name, count in seen_counts.items():
            if count > 0:
                _warn(f"DANGER SIGNAL: {name} detected {count} time(s)")
                if name == "claim_near_budget" and count >= 3:
                    _fatal(
                        "Multiple items at attempt_threshold. The runner hard-stops, "
                        "but this indicates systemic gate failures. "
                        "Kill processes and investigate before re-running."
                    )
                if name in ("gate_fail_cross_family_review", "gate_fail_jury") and count >= 3:
                    _fatal(
                        f"Multiple {name} failures detected. "
                        "Review/jury items are cycling. Kill processes and check BC-139 fix."
                    )
                if name == "channel_invoke_failed" and count >= 5:
                    _fatal(
                        "Multiple channel invoke failures. "
                        "Model channel may be down or rate-limited. "
                        "Kill processes and verify channel health."
                    )


def _run_telemetry(config_path: Path) -> None:
    """Run telemetry and telemetry --verify."""
    _info("Running telemetry...")
    for flag in ("", "--verify"):
        cmd = [sys.executable, "-m", "factory.telemetry", "--config", str(config_path)]
        if flag:
            cmd.append(flag)
        result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            _warn(f"telemetry {'--verify ' if flag else ''} exited {result.returncode}")


def _cleanup_offered(workspace_root: str, log_prefix: str) -> None:
    """Offer to clean workspace and logs. Never touch opencode DB."""
    wr = Path(workspace_root)
    logs = [Path(f"/tmp/{log_prefix}-{suffix}.log") for suffix in ("runner", "gate", "scheduler")]
    _info("=== Cleanup ===")
    _info(f"Workspace: {wr}")
    _info(f"Logs: {', '.join(str(log) for log in logs)}")
    _info("NOTE: This script NEVER touches ~/.local/share/opencode/ or any application DB.")
    # In non-interactive mode (agent), just clean up automatically
    _info("Auto-cleaning workspace + logs (non-interactive mode)...")
    if wr.exists():
        shutil.rmtree(wr)
        _info(f"Removed {wr}")
    for log in logs:
        log.unlink(missing_ok=True)
        _info(f"Removed {log}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent-mediated golden run with BC-140 safety protocol"
    )
    parser.add_argument(
        "--config", required=True, help="Path to golden-run config YAML"
    )
    parser.add_argument(
        "--fixtures", help="Path to fixtures (relative to repo root)"
    )
    parser.add_argument(
        "--log-prefix", help="Log file prefix (default: derived from config)"
    )
    parser.add_argument(
        "--no-cleanup", action="store_true",
        help="Skip workspace/log cleanup"
    )
    parser.add_argument(
        "--monitor-interval", type=int, default=30,
        help="Seconds between log checks"
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        _fatal(f"Config not found: {config_path}")

    log_prefix = args.log_prefix or config_path.stem

    _preflight(config_path, args.fixtures)
    _populate(config_path, args.fixtures)
    _runner, _gate, _scheduler = _launch_processes(config_path, log_prefix)

    try:
        _monitor_logs(log_prefix, interval=args.monitor_interval)
    except KeyboardInterrupt:
        _info("Monitoring interrupted by user. Processes continue in background.")

    _run_telemetry(config_path)

    if not args.no_cleanup:
        cfg = _validate_config(config_path)
        _cleanup_offered(cfg["workspace_root"], log_prefix)

    _info("Done.")


if __name__ == "__main__":
    main()
