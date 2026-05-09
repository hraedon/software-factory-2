from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from dataclasses import dataclass

from substrate import Substrate

from factory.config import FactoryConfig, load_config
from factory.constants import (
    GATE_NAME_UNKNOWN,
    STATE_IN_PROGRESS,
    TRANSITION_CHANNEL_FAIL,
    TRANSITION_GATE_FAIL,
    TRANSITION_GATE_PASS,
    TRANSITION_SUBMIT,
)
from factory.event_schemas import (
    ChannelFailPayload,
    EventSchemaError,
    GateFailPayload,
    SubmitPayload,
)

log = logging.getLogger(__name__)


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
    prompt_template_hash: str | None = None
    duration_seconds: float | None = None


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
        worker_duration: float | None = None
        for ev in events:
            md = ev.actor_metadata or {}
            if ev.transition == TRANSITION_SUBMIT:
                worker_meta = md
                payload = ev.payload or {}
                if payload:
                    try:
                        parsed = SubmitPayload.from_dict(payload)
                        worker_duration = parsed.duration_seconds
                    except EventSchemaError:
                        pass
            if ev.transition not in (TRANSITION_GATE_PASS, TRANSITION_GATE_FAIL):
                continue
            gate_name = md.get("gate_name")
            if not gate_name:
                payload = ev.payload or {}
                diagnostics: dict = {}
                if ev.transition == TRANSITION_GATE_FAIL:
                    try:
                        parsed = GateFailPayload.from_dict(payload)
                        diagnostics = parsed.diagnostics
                    except EventSchemaError:
                        diagnostics = payload.get("diagnostics", {})
                elif ev.transition == TRANSITION_CHANNEL_FAIL:
                    try:
                        parsed = ChannelFailPayload.from_dict(payload)
                        diagnostics = parsed.diagnostics
                    except EventSchemaError:
                        diagnostics = payload.get("diagnostics", {})
                else:
                    diagnostics = payload.get("diagnostics", {})
                gate_name = diagnostics.get("gate_name")
            if not gate_name:
                gate_name = GATE_NAME_UNKNOWN
                log.warning(
                    "telemetry_gate_name_unknown: work_item_id=%s transition=%s",
                    str(wi.work_item_id),
                    ev.transition,
                )
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
                    prompt_template_hash=worker_meta.get("prompt_template_hash"),
                    duration_seconds=worker_duration,
                ),
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
    prompt_template_hash: str | None = None
    mean_duration_seconds: float | None = None
    median_duration_seconds: float | None = None

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

    @property
    def hash_prefix(self) -> str:
        if not self.prompt_template_hash:
            return "\u2014"
        return self.prompt_template_hash[:8]

    @property
    def mean_duration_label(self) -> str:
        if self.mean_duration_seconds is None:
            return "\u2014"
        return f"{self.mean_duration_seconds:.1f}s"


def compute_pass_rates(attempts: list[GateAttempt]) -> list[PassRateRow]:
    by_key: dict[tuple[str, str, str, str, str | None], list[GateAttempt]] = defaultdict(list)
    for a in attempts:
        key = (a.role, a.channel, a.family, a.gate_name, a.prompt_template_hash)
        by_key[key].append(a)

    rows: list[PassRateRow] = []
    for (role, channel, family, gate_name, prompt_template_hash), group in sorted(by_key.items()):
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

        durations = [a.duration_seconds for a in group if a.duration_seconds is not None]
        mean_duration = sum(durations) / len(durations) if durations else None
        median_duration = None
        if durations:
            sorted_durations = sorted(durations)
            n = len(sorted_durations)
            median_duration = (
                sorted_durations[n // 2]
                if n % 2 == 1
                else (sorted_durations[n // 2 - 1] + sorted_durations[n // 2]) / 2
            )

        rows.append(
            PassRateRow(
                role=role,
                channel=channel,
                family=family,
                gate_name=gate_name,
                total_evaluations=total_evaluations,
                first_attempt_passes=first_attempt_passes,
                total_passes=total_passes,
                prompt_template_hash=prompt_template_hash,
                mean_duration_seconds=mean_duration,
                median_duration_seconds=median_duration,
            )
        )
    return rows


def format_pass_rate_table(rows: list[PassRateRow]) -> str:
    if not rows:
        return "No gate evaluation data found."

    lines: list[str] = []
    lines.append("=" * 118)
    lines.append("Telemetry: Per-(Role, Channel, Gate, PromptHash) Pass-Rate Report")
    lines.append("=" * 118)
    lines.append("")
    header = (
        f"  {'Role':22s}  {'Channel':12s}  {'Family':10s}  "
        f"{'Gate':28s}  {'Hash':>8s}  {'Items':>5s}  {'1st-Att':>7s}  "
        f"{'Overall':>7s}  {'MeanDur':>7s}"
    )
    lines.append(header)
    sep = (
        f"  {'-' * 22}  {'-' * 12}  {'-' * 10}  {'-' * 28}  "
        f"{'-' * 8}  {'-' * 5}  {'-' * 7}  {'-' * 7}  {'-' * 7}"
    )
    lines.append(sep)

    for row in rows:
        lines.append(
            f"  {row.role:22s}  {row.channel:12s}  {row.family:10s}  "
            f"{row.gate_name:28s}  {row.hash_prefix:>8s}  {row.total_evaluations:>5d}  "
            f"{row.first_attempt_rate:>7s}  {row.overall_rate:>7s}  "
            f"{row.mean_duration_label:>7s}"
        )

    # Detect confounded groups: same role/channel/family/gate with multiple hashes
    from collections import defaultdict

    by_four: dict[tuple[str, str, str, str], set[str | None]] = defaultdict(set)
    for r in rows:
        by_four[(r.role, r.channel, r.family, r.gate_name)].add(r.prompt_template_hash)
    confounded = [(k, hashes) for k, hashes in by_four.items() if len(hashes) > 1]
    if confounded:
        lines.append("")
        for (role, channel, family, gate_name), hashes in confounded:
            lines.append(
                f"  WARNING: prompt changed within comparison group "
                f"({role}/{channel}/{family}/{gate_name}); results confounded"
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


@dataclass
class VerifyResult:
    unknown_gate_name_count: int
    unknown_gate_name_rate: float
    orphan_submit_count: int
    unmatched_gate_count: int
    confounding_warning_count: int
    passed: bool


def run_telemetry_verify(config: FactoryConfig) -> VerifyResult:
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    try:
        attempts = collect_gate_attempts(sub, config)
        rows = compute_pass_rates(attempts)

        unknown_count = sum(1 for a in attempts if a.gate_name == GATE_NAME_UNKNOWN)
        unknown_rate = unknown_count / len(attempts) if attempts else 0.0

        # Orphan submits: work-items with a submit but no gate event and not in_progress
        page = sub.query_work_items(
            workflow_name=config.workflow_name,
            workflow_version=config.workflow_version,
            page_size=config.query_page_size,
        )
        orphan_count = 0
        unmatched_count = 0
        for wi in page.items:
            events = sub.read_events(
                work_item_id=wi.work_item_id, limit=config.telemetry_event_limit
            )
            has_submit = False
            has_gate = False
            for ev in events:
                if ev.transition == TRANSITION_SUBMIT:
                    has_submit = True
                if ev.transition in (TRANSITION_GATE_PASS, TRANSITION_GATE_FAIL):
                    has_gate = True
            if has_submit and not has_gate and wi.current_state != STATE_IN_PROGRESS:
                orphan_count += 1
            if has_gate and not has_submit:
                unmatched_count += 1

        # Confounding warnings
        by_four: dict[tuple[str, str, str, str], set[str | None]] = defaultdict(set)
        for r in rows:
            by_four[(r.role, r.channel, r.family, r.gate_name)].add(r.prompt_template_hash)
        confounding = sum(1 for hashes in by_four.values() if len(hashes) > 1)

        passed = (
            unknown_count == 0
            and unknown_rate < 0.01
            and orphan_count == 0
            and unmatched_count == 0
        )
        return VerifyResult(
            unknown_gate_name_count=unknown_count,
            unknown_gate_name_rate=unknown_rate,
            orphan_submit_count=orphan_count,
            unmatched_gate_count=unmatched_count,
            confounding_warning_count=confounding,
            passed=passed,
        )
    finally:
        sub.close()


def _main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Software Factory v2 - Telemetry Report")
    parser.add_argument("--config", type=str, default=None, help="Path to factory config YAML")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run data-quality verification instead of report",
    )
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.verify:
        result = run_telemetry_verify(config)
        print(f"unknown_gate_name_count: {result.unknown_gate_name_count}")
        print(f"unknown_gate_name_rate: {result.unknown_gate_name_rate:.4f}")
        print(f"orphan_submit_count: {result.orphan_submit_count}")
        print(f"unmatched_gate_count: {result.unmatched_gate_count}")
        print(f"confounding_warning_count: {result.confounding_warning_count}")
        print(f"verify_passed: {result.passed}")
        if not result.passed:
            raise SystemExit(1)
    else:
        report = run_telemetry_report(config)
        print(report)


def main() -> None:
    _main()


if __name__ == "__main__":
    main()
