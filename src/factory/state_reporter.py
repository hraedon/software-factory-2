from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import structlog
from substrate import Substrate

from factory.config import FactoryConfig, load_config
from factory.constants import (
    STATE_CANNOT_PROCEED,
    STATE_IN_PROGRESS,
    STATE_LOCKED,
    STATE_NEW,
    TRANSITION_GATE_FAIL,
)

log = structlog.get_logger()


@dataclass
class ProgressSummary:
    total: int
    by_state: dict[str, int]
    completion_percent: float
    by_type: dict[str, dict[str, int]]
    mean_time_in_progress_minutes: float | None


@dataclass
class FailureSummary:
    diagnostic_kind: str
    count: int
    most_recent_gate: str
    most_recent_message: str


@dataclass
class ChannelHealth:
    role: str
    channel: str
    model: str | None


@dataclass
class DiskPressure:
    workspace_root: str
    workspace_size_mb: float
    tmp_size_mb: float | None


@dataclass
class PipelineSnapshot:
    project_name: str
    workflow_name: str
    workflow_version: int
    timestamp: str
    progress: ProgressSummary
    recent_failures: list[FailureSummary]
    channel_health: list[ChannelHealth]
    disk_pressure: DiskPressure | None


class StateReporter:
    def __init__(self, sub: Substrate, config: FactoryConfig) -> None:
        self._sub = sub
        self._config = config

    def snapshot(self) -> PipelineSnapshot:
        config = self._config
        page = self._sub.query_work_items(
            workflow_name=config.workflow_name,
            workflow_version=config.workflow_version,
            page_size=config.query_page_size,
        )
        items = page.items

        by_state: dict[str, int] = {}
        by_type: dict[str, dict[str, int]] = {}
        in_progress_timestamps: list[datetime] = []

        for wi in items:
            state = wi.current_state
            by_state[state] = by_state.get(state, 0) + 1
            wi_type = wi.work_item_type
            if wi_type not in by_type:
                by_type[wi_type] = {}
            by_type[wi_type][state] = by_type[wi_type].get(state, 0) + 1

            if state == STATE_IN_PROGRESS:
                events = self._sub.read_events(
                    work_item_id=wi.work_item_id,
                    limit=1,
                )
                if events:
                    ts_str = events[0].timestamp
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        in_progress_timestamps.append(ts)
                    except (ValueError, TypeError):
                        pass

        locked = by_state.get(STATE_LOCKED, 0)
        in_progress = by_state.get(STATE_IN_PROGRESS, 0)
        new = by_state.get(STATE_NEW, 0)
        active_total = locked + in_progress + new
        completion = (locked / active_total * 100) if active_total > 0 else 0.0

        mean_time_min: float | None = None
        if in_progress_timestamps:
            now = datetime.now(UTC)
            deltas = [(now - ts).total_seconds() / 60 for ts in in_progress_timestamps]
            mean_time_min = sum(deltas) / len(deltas)

        progress = ProgressSummary(
            total=len(items),
            by_state=by_state,
            completion_percent=round(completion, 1),
            by_type=by_type,
            mean_time_in_progress_minutes=(
                round(mean_time_min, 1) if mean_time_min is not None else None
            ),
        )

        recent_failures = self._collect_recent_failures()

        channel_health = self._collect_channel_health()

        disk_pressure = self._collect_disk_pressure()

        return PipelineSnapshot(
            project_name=config.project_name,
            workflow_name=config.workflow_name,
            workflow_version=config.workflow_version,
            timestamp=datetime.now(UTC).isoformat(),
            progress=progress,
            recent_failures=recent_failures,
            channel_health=channel_health,
            disk_pressure=disk_pressure,
        )

    def _collect_recent_failures(self) -> list[FailureSummary]:
        try:
            events = self._sub.read_events(
                work_item_id=None,
                transition=TRANSITION_GATE_FAIL,
                limit=50,
            )
        except Exception:
            return []

        kind_counts: dict[str, list[tuple[str, str]]] = {}
        for ev in events:
            payload = ev.payload or {}
            diagnostics = payload.get("diagnostics", {})
            if isinstance(diagnostics, str):
                continue
            dkind = diagnostics.get("diagnostic_kind", "generic")
            gate = diagnostics.get("gate_name", "unknown")
            msg = diagnostics.get("message", "")
            if dkind not in kind_counts:
                kind_counts[dkind] = []
            kind_counts[dkind].append((gate, msg))

        summaries: list[FailureSummary] = []
        for kind, instances in sorted(kind_counts.items(), key=lambda x: -len(x[1])):
            recent = instances[0]
            summaries.append(
                FailureSummary(
                    diagnostic_kind=kind,
                    count=len(instances),
                    most_recent_gate=recent[0],
                    most_recent_message=recent[1][:120] if recent[1] else "",
                )
            )
        return summaries[:5]

    def _collect_channel_health(self) -> list[ChannelHealth]:
        config = self._config
        health: list[ChannelHealth] = []
        for rc in config.roles:
            health.append(
                ChannelHealth(
                    role=rc.role,
                    channel=rc.channel,
                    model=rc.model,
                )
            )
        return health

    def _collect_disk_pressure(self) -> DiskPressure | None:
        config = self._config
        ws_root = config.workspace_root
        if ws_root is None:
            return None
        ws_path = Path(str(ws_root))
        if not ws_path.exists():
            return None
        ws_size = _du_mb(ws_path)
        tmp_path = Path("/tmp")
        tmp_size = _du_mb(tmp_path) if tmp_path.exists() else None
        return DiskPressure(
            workspace_root=str(ws_root),
            workspace_size_mb=round(ws_size, 1),
            tmp_size_mb=round(tmp_size, 1) if tmp_size is not None else None,
        )

    def render_markdown(self, snap: PipelineSnapshot) -> str:
        lines: list[str] = []
        lines.append(f"# Pipeline State: {snap.project_name}")
        lines.append(f"**Workflow:** {snap.workflow_name} v{snap.workflow_version}")
        lines.append(f"**Timestamp:** {snap.timestamp}")
        lines.append("")

        p = snap.progress
        lines.append("## Progress")
        lines.append(f"- **Total items:** {p.total}")
        lines.append(f"- **Completion:** {p.completion_percent}%")
        for state, count in sorted(p.by_state.items()):
            lines.append(f"  - {state}: {count}")
        if p.mean_time_in_progress_minutes is not None:
            lines.append(f"- **Mean time in_progress:** {p.mean_time_in_progress_minutes} min")

        if p.by_type:
            lines.append("")
            lines.append("### By Type")
            lines.append("| Type | new | in_progress | gating | locked | cannot_proceed |")
            lines.append("|---|---|---|---|---|---|")
            for wtype, states in sorted(p.by_type.items()):
                lines.append(
                    f"| {wtype} "
                    f"| {states.get('new', 0)} "
                    f"| {states.get('in_progress', 0)} "
                    f"| {states.get('gating', 0)} "
                    f"| {states.get('locked', 0)} "
                    f"| {states.get('cannot_proceed', 0)} |"
                )

        if snap.recent_failures:
            lines.append("")
            lines.append("## Recent Failures")
            lines.append("| Kind | Count | Gate | Message |")
            lines.append("|---|---|---|---|")
            for f in snap.recent_failures:
                msg = f.most_recent_message[:80]
                lines.append(f"| {f.diagnostic_kind} | {f.count} | {f.most_recent_gate} | {msg} |")

        if snap.channel_health:
            lines.append("")
            lines.append("## Channel Bindings")
            lines.append("| Role | Channel | Model |")
            lines.append("|---|---|---|")
            for ch in snap.channel_health:
                lines.append(f"| {ch.role} | {ch.channel} | {ch.model or '-'} |")

        if snap.disk_pressure is not None:
            dp = snap.disk_pressure
            lines.append("")
            lines.append("## Disk Pressure")
            lines.append(f"- Workspace ({dp.workspace_root}): {dp.workspace_size_mb} MB")
            if dp.tmp_size_mb is not None:
                lines.append(f"- /tmp: {dp.tmp_size_mb} MB")

        return "\n".join(lines)

    def render_brief(self, snap: PipelineSnapshot) -> str:
        p = snap.progress
        locked = p.by_state.get(STATE_LOCKED, 0)
        cannot_proceed = p.by_state.get(STATE_CANNOT_PROCEED, 0)
        stuck = p.total - locked - cannot_proceed
        active = p.by_state.get(STATE_IN_PROGRESS, 0) + p.by_state.get("gating", 0)
        return (
            f"{locked}/{p.total} locked, "
            f"{active} active, "
            f"{cannot_proceed} cannot_proceed, "
            f"{stuck} stuck, "
            f"{p.completion_percent}% complete"
        )

    def render_json(self, snap: PipelineSnapshot) -> str:
        return json.dumps(asdict(snap), indent=2, default=str)


def _du_mb(path: Path) -> float:
    try:
        import os

        from factory.subprocess import run as run_subprocess

        result = run_subprocess(
            cmd=["du", "-sm", str(path)],
            cwd=path if path.is_dir() else path.parent,
            env=dict(os.environ),
            timeout_s=10,
        )
        if result.returncode == 0:
            parts = result.stdout.split()
            if parts:
                return float(parts[0])
    except Exception:
        pass
    return 0.0


def _main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Software Factory v2 - State Reporter")
    parser.add_argument("--config", type=str, required=True, help="Path to config YAML")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--brief", action="store_true", help="One-line summary")
    parser.add_argument("--watch", type=int, default=None, help="Poll every N seconds")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    try:
        reporter = StateReporter(sub, config)
        if args.watch is not None:
            interval = max(args.watch, 5)
            while True:
                snap = reporter.snapshot()
                print(reporter.render_brief(snap))
                sys.stdout.flush()
                time.sleep(interval)
        else:
            snap = reporter.snapshot()
            if args.json:
                print(reporter.render_json(snap))
            elif args.brief:
                print(reporter.render_brief(snap))
            else:
                print(reporter.render_markdown(snap))
    finally:
        sub.close()


def main() -> None:
    _main()


if __name__ == "__main__":
    main()
