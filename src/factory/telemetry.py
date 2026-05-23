from __future__ import annotations

import argparse
import logging
import re
from collections import defaultdict
from dataclasses import dataclass

from substrate import Substrate

from factory.config import FactoryConfig, load_config
from factory.constants import (
    GATE_NAME_UNKNOWN,
    STATE_CANNOT_PROCEED,
    STATE_IN_PROGRESS,
    STATE_LOCKED,
    TELEMETRY_UNKNOWN_RATE_THRESHOLD,
    TRANSITION_CHANNEL_FAIL,
    TRANSITION_GATE_FAIL,
    TRANSITION_GATE_PASS,
    TRANSITION_ROUTE_TO_CANNOT_PROCEED,
    TRANSITION_SUBMIT,
)
from factory.event_schemas import (
    ChannelFailPayload,
    EventSchemaError,
    GateFailPayload,
    SubmitPayload,
)

log = logging.getLogger(__name__)


def _query_work_items_and_events(
    sub: Substrate, config: FactoryConfig
) -> tuple[dict[str, object], dict[str, list]]:
    """Load all work items and their events once.

    Returns (work_items_by_id, events_by_id) where work_items_by_id maps
    work_item_id str to the work item object and events_by_id maps the same
    id str to a list of Event objects.  This eliminates O(nxm) re-scanning
    when multiple telemetry collectors consume the same data (BC-196).
    """
    page = sub.query_work_items(
        workflow_name=config.workflow_name,
        workflow_version=config.workflow_version,
        page_size=config.query_page_size,
    )
    work_items_by_id: dict[str, object] = {}
    events_by_id: dict[str, list] = {}
    for wi in page.items:
        wi_id = str(wi.work_item_id)
        events = sub.read_events(work_item_id=wi.work_item_id, limit=config.telemetry_event_limit)
        work_items_by_id[wi_id] = wi
        events_by_id[wi_id] = events
    return work_items_by_id, events_by_id


DETERMINISTIC_GATES = frozenset(
    {
        "interface_spec",
        "interface_spec_syntax",
        "interface_spec_stub",
        "interface_spec_structural_semantics",
        "interface_spec_file_exists",
        "interface_spec_not_empty",
        "test_suite",
        "test_suite_syntax",
        "test_suite_import_forbidden",
        "test_suite_collect",
        "test_suite_file_exists",
        "test_suite_not_empty",
        "test_suite_assertions",
        "test_suite_dependency",
        "implementation",
        "implementation_syntax",
        "implementation_import_forbidden",
        "implementation_imports",
        "implementation_mypy",
        "implementation_pytest",
        "implementation_lint",
        "implementation_file_exists",
        "implementation_not_empty",
        "implementation_dependency",
        "inner_pytest",
        "inner_import",
        "inner_test_collect",
        "inner_mypy",
        "inner_ruff",
        "inner_import_symbols",
        "inner_json_shape",
        "cross_family_review",
        "jury",
        "jury_quorum",
        "jury_disagree",
        "integration_import",
        "integration_mypy",
        "integration_pytest",
        "integration",
    }
)


@dataclass
class ExitCriteriaMetrics:
    lock_within_budget_rate: float
    locked_count: int
    total_count: int
    mean_attempts_to_lock: float
    first_gate_evaluation_pass_rate: float
    first_gate_evaluation_passes: int
    first_gate_evaluation_evaluations: int
    stuck_count: int
    unknown_gate_rate: float
    unknown_gate_count: int
    total_gate_events: int
    deterministic_gate_rate: float
    deterministic_count: int
    inner_gate_first_pass_rate: float
    inner_gate_first_passes: int
    inner_gate_evaluations: int
    # RFC-029 attempt-count buckets
    inner_gate_attempt_0_pass_rate: float
    inner_gate_attempt_0_passes: int
    inner_gate_attempt_1_recovery_rate: float
    inner_gate_attempt_1_recovery_count: int
    inner_gate_attempt_1_total: int
    inner_gate_attempt_2plus_rate: float
    inner_gate_attempt_2plus_count: int
    inner_gate_attempt_2plus_total: int
    inner_gate_exhausted_budget_rate: float
    inner_gate_exhausted_budget_count: int
    inner_gate_exhausted_budget_total: int
    # RFC-029 per-item attempt log for hard-tail diagnosis
    inner_gate_item_attempts: list[tuple[str, int, str]]


def compute_exit_criteria(
    sub: Substrate,
    config: FactoryConfig,
    attempts: list[GateAttempt],
    work_items: dict[str, object] | None = None,
) -> ExitCriteriaMetrics:
    if work_items is None:
        page = sub.query_work_items(
            workflow_name=config.workflow_name,
            workflow_version=config.workflow_version,
            page_size=config.query_page_size,
        )
        work_items = {str(wi.work_item_id): wi for wi in page.items}
    locked = 0
    cannot_proceed = 0
    total = len(work_items)
    for wi in work_items.values():
        if wi.current_state == STATE_LOCKED:
            locked += 1
        elif wi.current_state == STATE_CANNOT_PROCEED:
            cannot_proceed += 1
    stuck = total - locked - cannot_proceed

    per_item_attempts: dict[str, int] = defaultdict(int)
    for a in attempts:
        per_item_attempts[a.work_item_id] += 1

    total_attempts = sum(per_item_attempts.values())
    mean_attempts = total_attempts / len(per_item_attempts) if per_item_attempts else 0.0

    # Compute first gate-evaluation pass rate per (work_item, gate_name).
    # "First attempt" means the earliest gate evaluation for that pair,
    # regardless of substrate attempt_n (which conflates worker claims
    # and gate claims).  Inner-gate events are not substrate transitions,
    # so we measure outer-gate first evaluations here.  Inner gate data
    # is available via runner log parsing (work_item_size_metrics.py).
    per_item: dict[str, list[GateAttempt]] = defaultdict(list)
    for a in attempts:
        if not a.gate_name.startswith("inner_"):
            per_item[a.work_item_id].append(a)

    first_gate_eval_passes = 0
    first_gate_eval_evaluations = 0
    for item_attempts in per_item.values():
        sorted_attempts = sorted(item_attempts, key=lambda a: a.attempt_n)
        by_gate: dict[str, list[GateAttempt]] = defaultdict(list)
        for sa in sorted_attempts:
            by_gate[sa.gate_name].append(sa)
        for gate_attempts in by_gate.values():
            gate_sorted = sorted(gate_attempts, key=lambda a: a.attempt_n)
            first = gate_sorted[0]
            first_gate_eval_evaluations += 1
            if first.passed:
                first_gate_eval_passes += 1

    first_gate_eval_rate = (
        first_gate_eval_passes / first_gate_eval_evaluations if first_gate_eval_evaluations else 0.0
    )

    unknown_gate_count = sum(1 for a in attempts if a.gate_name == GATE_NAME_UNKNOWN)
    total_gate_events = len(attempts)
    unknown_rate = unknown_gate_count / total_gate_events if total_gate_events else 0.0

    deterministic_count = sum(1 for a in attempts if a.gate_name in DETERMINISTIC_GATES)
    deterministic_rate = deterministic_count / total_gate_events if total_gate_events else 0.0

    lock_rate = locked / total if total else 0.0

    inner_attempts = [a for a in attempts if a.gate_name.startswith("inner_")]
    inner_per_item: dict[str, list[GateAttempt]] = defaultdict(list)
    for a in inner_attempts:
        inner_per_item[a.work_item_id].append(a)
    inner_first_passes = 0
    inner_evaluations = 0
    for item_attempts in inner_per_item.values():
        sorted_ia = sorted(item_attempts, key=lambda a: (a.attempt_n, a.inner_retry or 0))
        by_gate_ia: dict[str, list[GateAttempt]] = defaultdict(list)
        for sa in sorted_ia:
            by_gate_ia[sa.gate_name].append(sa)
        for gate_attempts in by_gate_ia.values():
            gate_sorted = sorted(gate_attempts, key=lambda a: (a.attempt_n, a.inner_retry or 0))
            inner_evaluations += 1
            if gate_sorted[0].passed:
                inner_first_passes += 1
    inner_rate = inner_first_passes / inner_evaluations if inner_evaluations else 0.0

    # RFC-029: attempt-count bucketing per (work_item_id, gate_name).
    # For each group, flatten inner evaluations across all substrate submits
    # and count how many evaluations were needed before first pass.
    bucket_0_passes = 0
    bucket_1_recovery_count = 0
    bucket_1_total = 0
    bucket_2plus_count = 0
    bucket_2plus_total = 0
    exhausted_count = 0
    exhausted_total = 0
    item_attempt_log: list[tuple[str, int, str]] = []
    for item_attempts in inner_per_item.values():
        sorted_ia = sorted(item_attempts, key=lambda a: (a.attempt_n, a.inner_retry or 0))
        by_gate_ia = defaultdict(list)
        for sa in sorted_ia:
            by_gate_ia[sa.gate_name].append(sa)
        for gate_name, gate_attempts in by_gate_ia.items():
            gate_sorted = sorted(gate_attempts, key=lambda a: (a.attempt_n, a.inner_retry or 0))
            first_pass_idx = None
            for idx, a in enumerate(gate_sorted):
                if a.passed:
                    first_pass_idx = idx
                    break
            if first_pass_idx == 0:
                bucket_0_passes += 1
                item_attempt_log.append((gate_attempts[0].work_item_id, 1, gate_name))
            elif first_pass_idx == 1:
                bucket_1_recovery_count += 1
                bucket_1_total += 1
                item_attempt_log.append((gate_attempts[0].work_item_id, 2, gate_name))
            elif first_pass_idx is not None:
                bucket_2plus_count += 1
                bucket_2plus_total += 1
                item_attempt_log.append(
                    (gate_attempts[0].work_item_id, first_pass_idx + 1, gate_name)
                )
            else:
                exhausted_count += 1
                exhausted_total += 1
                item_attempt_log.append(
                    (gate_attempts[0].work_item_id, len(gate_sorted), gate_name)
                )

    total_inner_groups = bucket_0_passes + bucket_1_total + bucket_2plus_total + exhausted_total
    bucket_0_rate = bucket_0_passes / total_inner_groups if total_inner_groups else 0.0
    bucket_1_rate = bucket_1_recovery_count / bucket_1_total if bucket_1_total else 0.0
    bucket_2plus_rate = bucket_2plus_count / bucket_2plus_total if bucket_2plus_total else 0.0
    exhausted_rate = exhausted_count / exhausted_total if exhausted_total else 0.0

    return ExitCriteriaMetrics(
        lock_within_budget_rate=lock_rate,
        locked_count=locked,
        total_count=total,
        mean_attempts_to_lock=mean_attempts,
        first_gate_evaluation_pass_rate=first_gate_eval_rate,
        first_gate_evaluation_passes=first_gate_eval_passes,
        first_gate_evaluation_evaluations=first_gate_eval_evaluations,
        stuck_count=stuck,
        unknown_gate_rate=unknown_rate,
        unknown_gate_count=unknown_gate_count,
        total_gate_events=total_gate_events,
        deterministic_gate_rate=deterministic_rate,
        deterministic_count=deterministic_count,
        inner_gate_first_pass_rate=inner_rate,
        inner_gate_first_passes=inner_first_passes,
        inner_gate_evaluations=inner_evaluations,
        inner_gate_attempt_0_pass_rate=bucket_0_rate,
        inner_gate_attempt_0_passes=bucket_0_passes,
        inner_gate_attempt_1_recovery_rate=bucket_1_rate,
        inner_gate_attempt_1_recovery_count=bucket_1_recovery_count,
        inner_gate_attempt_1_total=bucket_1_total,
        inner_gate_attempt_2plus_rate=bucket_2plus_rate,
        inner_gate_attempt_2plus_count=bucket_2plus_count,
        inner_gate_attempt_2plus_total=bucket_2plus_total,
        inner_gate_exhausted_budget_rate=exhausted_rate,
        inner_gate_exhausted_budget_count=exhausted_count,
        inner_gate_exhausted_budget_total=exhausted_total,
        inner_gate_item_attempts=sorted(item_attempt_log, key=lambda t: (-t[1], t[0])),
    )


def format_exit_criteria_summary(metrics: ExitCriteriaMetrics) -> str:
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("Pipeline Exit Criteria Summary")
    lines.append("=" * 70)
    lines.append("")

    lr = f"{metrics.lock_within_budget_rate:.0%}"
    lr_line = (
        f"  Lock-within-budget rate:     {lr} "
        f"({metrics.locked_count}/{metrics.total_count})  (informational)"
    )
    lines.append(lr_line)

    ma = f"{metrics.mean_attempts_to_lock:.2f}"
    ma_pass = metrics.mean_attempts_to_lock <= 2.0
    ma_label = "PASS" if ma_pass else "FAIL"
    lines.append(f"  Mean attempts to lock:        {ma}  {ma_label:4s} [target: <=2.0]")

    fa = f"{metrics.first_gate_evaluation_pass_rate:.0%}"
    fa_pass = metrics.first_gate_evaluation_pass_rate >= 0.60
    fa_label = "PASS" if fa_pass else "FAIL"
    fa_line = (
        f"  First gate-evaluation pass rate: {fa} "
        f"({metrics.first_gate_evaluation_passes}/{metrics.first_gate_evaluation_evaluations})  "
        f"{fa_label:4s} [target: >=60%]"
    )
    lines.append(fa_line)
    if metrics.inner_gate_evaluations > 0:
        ig = f"{metrics.inner_gate_first_pass_rate:.0%}"
        ig_pass = metrics.inner_gate_first_pass_rate >= 0.60
        ig_label = "PASS" if ig_pass else "FAIL"
        ig_line = (
            f"  Inner gate first-pass rate:    {ig} "
            f"({metrics.inner_gate_first_passes}/{metrics.inner_gate_evaluations})  "
            f"{ig_label:4s} [target: >=60%]"
        )
        lines.append(ig_line)

        # RFC-029: attempt-count buckets
        lines.append("")
        lines.append("  Inner gate attempt buckets (RFC-029):")
        total_inner_groups = (
            metrics.inner_gate_attempt_0_passes
            + metrics.inner_gate_attempt_1_total
            + metrics.inner_gate_attempt_2plus_total
            + metrics.inner_gate_exhausted_budget_total
        )
        a0 = f"{metrics.inner_gate_attempt_0_pass_rate:.0%}"
        lines.append(
            f"    attempt-0 pass:              {a0} "
            f"({metrics.inner_gate_attempt_0_passes}/{total_inner_groups})"
        )
        a1 = f"{metrics.inner_gate_attempt_1_recovery_rate:.0%}"
        lines.append(
            f"    attempt-1 recovery:          {a1} "
            f"({metrics.inner_gate_attempt_1_recovery_count}/{metrics.inner_gate_attempt_1_total})"
        )
        a2p = f"{metrics.inner_gate_attempt_2plus_rate:.0%}"
        lines.append(
            f"    attempt-2+ needed:           {a2p} "
            f"({metrics.inner_gate_attempt_2plus_count}/{metrics.inner_gate_attempt_2plus_total})"
        )
        ex = f"{metrics.inner_gate_exhausted_budget_rate:.0%}"
        lines.append(
            f"    exhausted budget:            {ex} "
            f"({metrics.inner_gate_exhausted_budget_count}/{metrics.inner_gate_exhausted_budget_total})"
        )

        if metrics.inner_gate_item_attempts:
            lines.append("")
            lines.append("  Per-item inner gate attempt log (hard tail):")
            for wid, att_count, gate_name in metrics.inner_gate_item_attempts:
                lines.append(f"    {wid[:22]}  {att_count:>2d} evals  {gate_name}")
    else:
        lines.append("  Inner gate first-pass rate:    — (no inner gate data in substrate)")

    lines.append("")
    lines.append(
        f"  Stuck items:                 {metrics.stuck_count}  [target: <=1 per 16-item DAG]"
    )

    ur = f"{metrics.unknown_gate_rate:.1%}"
    ur_pass = metrics.unknown_gate_rate <= TELEMETRY_UNKNOWN_RATE_THRESHOLD
    ur_label = "PASS" if ur_pass else "FAIL"
    ur_line = (
        f"  Unknown gate rate:            {ur} "
        f"({metrics.unknown_gate_count}/{metrics.total_gate_events})  "
        f"{ur_label:4s} [target: <1%]"
    )
    lines.append(ur_line)

    dr = f"{metrics.deterministic_gate_rate:.0%}"
    dr_pass = metrics.deterministic_gate_rate >= 0.80
    dr_label = "PASS" if dr_pass else "FAIL"
    dr_line = (
        f"  Deterministic gate rate:      {dr} "
        f"({metrics.deterministic_count}/{metrics.total_gate_events})  "
        f"{dr_label:4s} [target: >=80%]"
    )
    lines.append(dr_line)

    all_pass = ma_pass and fa_pass and ig_pass and ur_pass and dr_pass
    lines.append("")
    lines.append(f"  Overall: {'ALL PASS' if all_pass else 'SOME FAIL'}")
    lines.append("")
    return "\n".join(lines)


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
    # RFC-034: resolved model string at the time of the attempt. None means
    # the channel did not (or could not) resolve a single model — e.g. jury
    # aggregate, or legacy rows from before the model field was plumbed
    # through. NULL is treated as a distinct bucket by `compute_pass_rates`.
    model: str | None = None
    # RFC-029: retry number within a single substrate attempt for inner-gate
    # evaluations. 0 = first inner evaluation, 1 = first retry, etc. None
    # for outer-gate events (they have no retry concept within one event).
    inner_retry: int | None = None


def collect_gate_attempts(
    sub: Substrate,
    config: FactoryConfig,
    events_by_id: dict[str, list] | None = None,
) -> list[GateAttempt]:
    if events_by_id is None:
        _, events_by_id = _query_work_items_and_events(sub, config)
    attempts: list[GateAttempt] = []
    for wi_id, events in events_by_id.items():
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
                        if parsed.inner_gate_attempts:
                            for iga in parsed.inner_gate_attempts:
                                attempts.append(
                                    GateAttempt(
                                        work_item_id=wi_id,
                                        work_item_type=(
                                            ev.work_item_type
                                            if hasattr(ev, "work_item_type")
                                            else "unknown"
                                        ),
                                        role=worker_meta.get("role", "unknown"),
                                        channel=worker_meta.get("channel", "unknown"),
                                        family=worker_meta.get("family", "unknown"),
                                        attempt_n=md.get("attempt_n", 0) or 0,
                                        gate_name=iga.get("gate_name", "unknown"),
                                        passed=iga.get("passed", False),
                                        duration_seconds=worker_duration,
                                        model=worker_meta.get("model"),
                                        inner_retry=iga.get("retry"),
                                    )
                                )
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
                    wi_id,
                    ev.transition,
                )
            attempts.append(
                GateAttempt(
                    work_item_id=wi_id,
                    work_item_type=(
                        ev.work_item_type if hasattr(ev, "work_item_type") else "unknown"
                    ),
                    role=worker_meta.get("role", "unknown"),
                    channel=worker_meta.get("channel", "unknown"),
                    family=worker_meta.get("family", "unknown"),
                    attempt_n=md.get("attempt_n", 0) or 0,
                    gate_name=gate_name,
                    passed=ev.transition == TRANSITION_GATE_PASS,
                    prompt_template_hash=worker_meta.get("prompt_template_hash"),
                    duration_seconds=worker_duration,
                    model=worker_meta.get("model"),
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
    # RFC-034: resolved model string. NULL is a distinct bucket — pre-RFC-034
    # rows or genuine "no single model" cases like jury aggregate.
    model: str | None = None

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
    # RFC-034: model is part of the grouping key so that a channel whose
    # underlying model snapshot changes (e.g. kimi-k2.6 → kimi-k2.7) does
    # not silently merge into one confounded bucket.
    by_key: dict[tuple[str, str, str, str, str | None, str | None], list[GateAttempt]] = (
        defaultdict(list)
    )
    for a in attempts:
        key = (a.role, a.channel, a.family, a.gate_name, a.prompt_template_hash, a.model)
        by_key[key].append(a)

    rows: list[PassRateRow] = []
    for (role, channel, family, gate_name, prompt_template_hash, model), group in sorted(
        by_key.items(), key=lambda kv: tuple("" if x is None else x for x in kv[0])
    ):
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
            if first.passed:
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
                model=model,
            )
        )
    return rows


def format_pass_rate_table(rows: list[PassRateRow]) -> str:
    if not rows:
        return "No gate evaluation data found."

    lines: list[str] = []
    lines.append("=" * 138)
    lines.append("Telemetry: Per-(Role, Channel, Model, Gate, PromptHash) Pass-Rate Report")
    lines.append("=" * 138)
    lines.append("")
    header = (
        f"  {'Role':22s}  {'Channel':12s}  {'Family':10s}  {'Model':18s}  "
        f"{'Gate':28s}  {'Hash':>8s}  {'Items':>5s}  {'1st-Att':>7s}  "
        f"{'Overall':>7s}  {'MeanDur':>7s}"
    )
    lines.append(header)
    sep = (
        f"  {'-' * 22}  {'-' * 12}  {'-' * 10}  {'-' * 18}  {'-' * 28}  "
        f"{'-' * 8}  {'-' * 5}  {'-' * 7}  {'-' * 7}  {'-' * 7}"
    )
    lines.append(sep)

    null_model_rows = 0
    for row in rows:
        model_label = (row.model or "—")[:18]
        if row.model is None:
            null_model_rows += 1
        lines.append(
            f"  {row.role:22s}  {row.channel:12s}  {row.family:10s}  {model_label:18s}  "
            f"{row.gate_name:28s}  {row.hash_prefix:>8s}  {row.total_evaluations:>5d}  "
            f"{row.first_attempt_rate:>7s}  {row.overall_rate:>7s}  "
            f"{row.mean_duration_label:>7s}"
        )

    # RFC-034: detect confounded groups along both prompt and model axes.
    # Same role/channel/family/gate with multiple hashes OR multiple models
    # is a comparison-group confound.
    from collections import defaultdict

    by_four: dict[tuple[str, str, str, str], set[str | None]] = defaultdict(set)
    by_four_models: dict[tuple[str, str, str, str], set[str | None]] = defaultdict(set)
    for r in rows:
        k = (r.role, r.channel, r.family, r.gate_name)
        by_four[k].add(r.prompt_template_hash)
        by_four_models[k].add(r.model)
    confounded = [(k, hashes) for k, hashes in by_four.items() if len(hashes) > 1]
    confounded_models = [(k, models) for k, models in by_four_models.items() if len(models) > 1]
    if confounded:
        lines.append("")
        for (role, channel, family, gate_name), hashes in confounded:
            lines.append(
                f"  WARNING: prompt changed within comparison group "
                f"({role}/{channel}/{family}/{gate_name}); results confounded"
            )
    if confounded_models:
        if not confounded:
            lines.append("")
        for (role, channel, family, gate_name), models in confounded_models:
            model_list = ", ".join(sorted(m or "<null>" for m in models))
            lines.append(
                f"  WARNING: model changed within comparison group "
                f"({role}/{channel}/{family}/{gate_name}); models seen: {model_list}; "
                f"results confounded"
            )
    if null_model_rows and null_model_rows < len(rows):
        lines.append("")
        lines.append(
            f"  NOTE: {null_model_rows}/{len(rows)} rows have model=NULL "
            f"(pre-RFC-034 rows or genuine no-single-model cases like jury_aggregate)."
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


# Regex patterns for contract-shaped complaints in cannot_proceed rationales.
# Used by telemetry to count BC-120 trigger instances empirically.
CONTRACT_COMPLAINT_PATTERNS: frozenset[str] = frozenset(
    {
        r"signature",
        r"parameter\s+(?:missing|wrong|extra)",
        r"interface\s+(?:wrong|broken|invalid|mismatch)",
        r"wrong\s+(?:type|return\s*type)",
        r"should\s+(?:return|accept|take)",
        r"contract\s+(?:broken|wrong|invalid)",
        r"contract\s+is\s+(?:wrong|invalid|broken)",
        r"missing\s+(?:return|parameter|arg)",
        r"type\s+mismatch",
        r"incompatible\s+signature",
        r"function\s+signature",
    }
)


def _looks_like_contract_complaint(rationale: str) -> bool:
    """Return True if a cannot_proceed rationale appears contract-shaped."""
    text = rationale.lower()
    return any(re.search(pat, text) for pat in CONTRACT_COMPLAINT_PATTERNS)


@dataclass
class ContractComplaintMetrics:
    total_cannot_proceed: int
    contract_shaped: int
    cross_family_review_agreed: int
    samples: list[str]


def collect_contract_complaints(
    sub: Substrate,
    config: FactoryConfig,
    work_items: dict[str, object] | None = None,
    events_by_id: dict[str, list] | None = None,
) -> ContractComplaintMetrics:
    if work_items is None or events_by_id is None:
        work_items, events_by_id = _query_work_items_and_events(sub, config)
    total = 0
    contract_shaped = 0
    cross_family_agreed = 0
    samples: list[str] = []

    for wi_id, wi in work_items.items():
        if wi.current_state != STATE_CANNOT_PROCEED:
            continue
        events = events_by_id.get(wi_id, [])
        for ev in events:
            if ev.transition != TRANSITION_ROUTE_TO_CANNOT_PROCEED:
                continue
            total += 1
            # Try payload first, then fallback to ev.custom_fields (future compat)
            payload = ev.payload or {}
            if "custom_fields_update" in payload:
                diagnostics = payload["custom_fields_update"].get("diagnostics", {})
            else:
                cf = getattr(ev, "custom_fields", None) or {}
                diagnostics = cf.get("diagnostics", {})
            rationale = diagnostics.get("rationale", "")
            if not rationale and isinstance(diagnostics, dict):
                rationale = str(diagnostics.get("message", diagnostics.get("reason", "")))
            if _looks_like_contract_complaint(rationale):
                contract_shaped += 1
                if len(samples) < 5:
                    samples.append(rationale[:200])
            # Cross-family reviewer agreement: look for a preceding review_fail
            # with diagnostics citing the contract. This is approximate — the
            # full check requires reading linked review work items.
            for rev_ev in events:
                if rev_ev.transition == "review_fail":
                    rev_diagnostics = (rev_ev.payload or {}).get("diagnostics", {})
                    rev_msg = str(rev_diagnostics.get("message", "")).lower()
                    if any(k in rev_msg for k in ("contract", "interface", "signature")):
                        cross_family_agreed += 1
                        break

    return ContractComplaintMetrics(
        total_cannot_proceed=total,
        contract_shaped=contract_shaped,
        cross_family_review_agreed=cross_family_agreed,
        samples=samples,
    )


def format_contract_complaint_summary(metrics: ContractComplaintMetrics) -> str:
    lines: list[str] = []
    lines.append("-" * 70)
    lines.append("Contract Complaint Telemetry (BC-120 trigger watch)")
    lines.append("-" * 70)
    lines.append(f"  Total cannot_proceed events:        {metrics.total_cannot_proceed}")
    lines.append(
        f"  Contract-shaped rationales:         {metrics.contract_shaped}  (trigger threshold: ≥3)"
    )
    lines.append(
        f"  Cross-family reviewer agreed:       {metrics.cross_family_review_agreed}  "
        f"(trigger threshold: ≥3)"
    )
    if metrics.samples:
        lines.append("")
        lines.append("  Sample rationales (first 200 chars):")
        for s in metrics.samples:
            lines.append(f"    • {s!r}")
    lines.append("")
    return "\n".join(lines)


def run_telemetry_report(config: FactoryConfig) -> str:
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    try:
        work_items, events_by_id = _query_work_items_and_events(sub, config)
        attempts = collect_gate_attempts(sub, config, events_by_id=events_by_id)
        rows = compute_pass_rates(attempts)
        metrics = compute_exit_criteria(sub, config, attempts, work_items=work_items)
        detail = format_pass_rate_table(rows)
        summary = format_exit_criteria_summary(metrics)
        complaint_metrics = collect_contract_complaints(
            sub, config, work_items=work_items, events_by_id=events_by_id
        )
        complaint_summary = format_contract_complaint_summary(complaint_metrics)
        routing_metrics = collect_routing_hints(
            sub, config, work_items=work_items, events_by_id=events_by_id
        )
        routing_summary = format_routing_hint_summary(routing_metrics)
        return summary + "\n" + complaint_summary + "\n" + routing_summary + "\n" + detail
    finally:
        sub.close()


@dataclass
class RoutingHintMetrics:
    total_outcome_fail: int
    routing_hint_present: int
    routing_hint_by_type: dict[str, int]
    samples: list[dict]


def collect_routing_hints(
    sub: Substrate,
    config: FactoryConfig,
    work_items: dict[str, object] | None = None,
    events_by_id: dict[str, list] | None = None,
) -> RoutingHintMetrics:
    if work_items is None or events_by_id is None:
        work_items, events_by_id = _query_work_items_and_events(sub, config)
    total = 0
    present = 0
    by_type: dict[str, int] = {}
    samples: list[dict] = []

    for wi_id, wi in work_items.items():
        if wi.work_item_type != "outcome_verification":
            continue
        events = events_by_id.get(wi_id, [])
        for ev in events:
            if ev.transition != TRANSITION_GATE_FAIL:
                continue
            total += 1
            payload = ev.payload or {}
            diagnostics = payload.get("diagnostics", {})
            hint = diagnostics.get("routing_hint")
            if isinstance(hint, dict):
                present += 1
                hint_type = hint.get("work_item_type", "unknown")
                by_type[hint_type] = by_type.get(hint_type, 0) + 1
                if len(samples) < 5:
                    samples.append(
                        {
                            "work_item_id": str(wi.work_item_id),
                            "rationale": diagnostics.get("message", "")[:200],
                            "hint_type": hint_type,
                            "hint_reason": hint.get("reason", "")[:200],
                        }
                    )

    return RoutingHintMetrics(
        total_outcome_fail=total,
        routing_hint_present=present,
        routing_hint_by_type=by_type,
        samples=samples,
    )


def format_routing_hint_summary(metrics: RoutingHintMetrics) -> str:
    lines: list[str] = []
    lines.append("-" * 70)
    lines.append("Routing Hint Telemetry (BC-145)")
    lines.append("-" * 70)
    lines.append(f"  Total outcome_verification gate_fail events: {metrics.total_outcome_fail}")
    lines.append(f"  Routing hints present:                        {metrics.routing_hint_present}")
    if metrics.routing_hint_by_type:
        lines.append("  By target work_item_type:")
        for hint_type, count in sorted(metrics.routing_hint_by_type.items()):
            lines.append(f"    - {hint_type}: {count}")
    else:
        lines.append("  By target work_item_type: (none)")
    if metrics.samples:
        lines.append("")
        lines.append("  Samples:")
        for s in metrics.samples:
            lines.append(
                f"    {s['work_item_id'][:8]}... -> {s['hint_type']} ({s['hint_reason']!r})"
            )
    lines.append("")
    return "\n".join(lines)


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
        work_items, events_by_id = _query_work_items_and_events(sub, config)
        attempts = collect_gate_attempts(sub, config, events_by_id=events_by_id)
        rows = compute_pass_rates(attempts)

        unknown_count = sum(1 for a in attempts if a.gate_name == GATE_NAME_UNKNOWN)
        unknown_rate = unknown_count / len(attempts) if attempts else 0.0

        # Orphan submits: work-items with a submit but no gate event and not in_progress
        orphan_count = 0
        unmatched_count = 0
        for wi_id, wi in work_items.items():
            events = events_by_id.get(wi_id, [])
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
            and unknown_rate < TELEMETRY_UNKNOWN_RATE_THRESHOLD
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
