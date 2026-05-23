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
