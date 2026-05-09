from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass

from substrate import Substrate

from factory.config import FactoryConfig, load_config
from factory.constants import (
    TRANSITION_GATE_FAIL,
    TRANSITION_GATE_PASS,
    TRANSITION_SUBMIT,
)


@dataclass(frozen=True)
class GateAttempt:
    work_item_id: str
    work_item_type: str
    role: str
    channel: str
    family: str
    attempt_n: int
    gate_name: str
    passed: bool


def collect_gate_attempts(sub: Substrate, config: FactoryConfig) -> list[GateAttempt]:
    page = sub.query_work_items(
        workflow_name=config.workflow_name,
        workflow_version=config.workflow_version,
        page_size=config.query_page_size,
    )
    attempts: list[GateAttempt] = []
    for wi in page.items:
        events = sub.read_events(work_item_id=wi.work_item_id, limit=config.telemetry_event_limit)
        worker_meta: dict = {}
        for ev in events:
            md = ev.actor_metadata or {}
            if ev.transition == TRANSITION_SUBMIT:
                worker_meta = md
            if ev.transition not in (TRANSITION_GATE_PASS, TRANSITION_GATE_FAIL):
                continue
            payload = ev.payload or {}
            diagnostics = payload.get("diagnostics", {})
            gate_name = diagnostics.get("gate_name", "unknown")
            attempts.append(
                GateAttempt(
                    work_item_id=str(wi.work_item_id),
                    work_item_type=wi.work_item_type,
                    role=worker_meta.get("role", "unknown"),
                    channel=worker_meta.get("channel", "unknown"),
                    family=worker_meta.get("family", "unknown"),
                    attempt_n=md.get("attempt_n", 0) or 0,
                    gate_name=gate_name,
                    passed=ev.transition == TRANSITION_GATE_PASS,
                )
            )
    return attempts


@dataclass
class PassRateRow:
    role: str
    channel: str
    family: str
    gate_name: str
    total_evaluations: int
    first_attempt_passes: int
    total_passes: int

    @property
    def first_attempt_rate(self) -> str:
        if self.total_evaluations == 0:
            return "\u2014"
        return f"{self.first_attempt_passes / self.total_evaluations:.0%}"

    @property
    def overall_rate(self) -> str:
        if self.total_evaluations == 0:
            return "\u2014"
        return f"{self.total_passes / self.total_evaluations:.0%}"


def compute_pass_rates(attempts: list[GateAttempt]) -> list[PassRateRow]:
    by_key: dict[tuple[str, str, str, str], list[GateAttempt]] = defaultdict(list)
    for a in attempts:
        key = (a.role, a.channel, a.family, a.gate_name)
        by_key[key].append(a)

    rows: list[PassRateRow] = []
    for (role, channel, family, gate_name), group in sorted(by_key.items()):
        per_item: dict[str, list[GateAttempt]] = defaultdict(list)
        for a in group:
            per_item[a.work_item_id].append(a)

        total_evaluations = len(per_item)
        first_attempt_passes = 0
        total_passes = 0
        for item_attempts in per_item.values():
            sorted_attempts = sorted(item_attempts, key=lambda a: a.attempt_n)
            if any(a.passed for a in sorted_attempts):
                total_passes += 1
            first = sorted_attempts[0]
            if first.passed and first.attempt_n <= 1:
                first_attempt_passes += 1

        rows.append(
            PassRateRow(
                role=role,
                channel=channel,
                family=family,
                gate_name=gate_name,
                total_evaluations=total_evaluations,
                first_attempt_passes=first_attempt_passes,
                total_passes=total_passes,
            )
        )
    return rows


def format_pass_rate_table(rows: list[PassRateRow]) -> str:
    if not rows:
        return "No gate evaluation data found."

    lines: list[str] = []
    lines.append("=" * 90)
    lines.append("Telemetry: Per-(Role, Channel, Gate) Pass-Rate Report")
    lines.append("=" * 90)
    lines.append("")
    header = (
        f"  {'Role':22s}  {'Channel':12s}  {'Family':10s}  "
        f"{'Gate':28s}  {'Items':>5s}  {'1st-Att':>7s}  {'Overall':>7s}"
    )
    lines.append(header)
    sep = f"  {'-' * 22}  {'-' * 12}  {'-' * 10}  {'-' * 28}  {'-' * 5}  {'-' * 7}  {'-' * 7}"
    lines.append(sep)

    for row in rows:
        lines.append(
            f"  {row.role:22s}  {row.channel:12s}  {row.family:10s}  "
            f"{row.gate_name:28s}  {row.total_evaluations:>5d}  "
            f"{row.first_attempt_rate:>7s}  {row.overall_rate:>7s}"
        )

    total_items = sum(r.total_evaluations for r in rows)
    total_first = sum(r.first_attempt_passes for r in rows)
    total_overall = sum(r.total_passes for r in rows)
    overall_pct = f"{total_overall / total_items:.0%}" if total_items else "\u2014"
    first_pct = f"{total_first / total_items:.0%}" if total_items else "\u2014"
    lines.append("")
    lines.append(
        f"  Overall: {total_items} items evaluated, "
        f"{first_pct} first-attempt pass, {overall_pct} overall pass"
    )
    lines.append("")

    return "\n".join(lines)


def run_telemetry_report(config: FactoryConfig) -> str:
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    try:
        attempts = collect_gate_attempts(sub, config)
        rows = compute_pass_rates(attempts)
        return format_pass_rate_table(rows)
    finally:
        sub.close()


def _main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Software Factory v2 - Telemetry Report")
    parser.add_argument("--config", type=str, default=None, help="Path to factory config YAML")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    report = run_telemetry_report(config)
    print(report)


def main() -> None:
    _main()


if __name__ == "__main__":
    main()
