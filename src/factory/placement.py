from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from factory.config import FactoryConfig
from factory.telemetry import PassRateRow

log = logging.getLogger(__name__)

DEFAULT_MIN_SAMPLES = 3
DEFAULT_CONFIDENCE_THRESHOLD = 0.05


@dataclass(frozen=True)
class PlacementPolicy:
    """Decision rule for channel placement.

    Declarative data so the principal can A/B placement strategies without
    touching the runner.
    """

    min_samples: int = DEFAULT_MIN_SAMPLES
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    fallback_to_current: bool = True
    prefer_family: str | None = None
    gate_filter: str | None = None
    # RFC-035: cost and Anthropic-preference policies are follow-up work


@dataclass(frozen=True)
class PlacementChange:
    """A single proposed role→channel change."""

    role: str
    current_channel: str
    current_model: str | None
    proposed_channel: str
    proposed_model: str | None
    rationale: str
    current_rate: float
    proposed_rate: float
    sample_count: int


@dataclass(frozen=True)
class PlacementDiff:
    changes: tuple[PlacementChange, ...] = ()
    untouched: tuple[str, ...] = ()
    no_data: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def _rate_for_role_channel(
    role: str,
    channel: str,
    model: str | None,
    rows: list[PassRateRow],
    gate_filter: str | None = None,
) -> tuple[float, int]:
    """Compute first-attempt pass rate for a (role, channel, model) tuple.

    Returns (rate, total_evaluations).
    """
    matching = [
        r
        for r in rows
        if r.role == role
        and r.channel == channel
        and (model is None or r.model == model)
        and (gate_filter is None or r.gate_name == gate_filter)
    ]
    total_evaluations = sum(r.total_evaluations for r in matching)
    first_attempt_passes = sum(r.first_attempt_passes for r in matching)
    rate = first_attempt_passes / total_evaluations if total_evaluations > 0 else 0.0
    return rate, total_evaluations


def propose(
    rows: list[PassRateRow],
    config: FactoryConfig,
    policy: PlacementPolicy | None = None,
) -> PlacementDiff:
    """Return a structured diff of proposed role→channel changes.

    Never mutates *config* directly.  The caller decides whether to apply
    (dry-run, propose-pr, live) via :func:`apply`.
    """
    policy = policy or PlacementPolicy()
    changes: list[PlacementChange] = []
    untouched: list[str] = []
    no_data: list[str] = []

    # Gather all (channel, model) pairs seen in telemetry for each role
    role_options: dict[str, set[tuple[str, str | None]]] = {}
    for r in rows:
        role_options.setdefault(r.role, set()).add((r.channel, r.model))

    for rc in config.roles:
        if rc.channel == "code":
            # Mechanical gate has no model placement decision
            continue

        current_rate, current_samples = _rate_for_role_channel(
            rc.role, rc.channel, rc.model, rows, policy.gate_filter
        )

        options = role_options.get(rc.role, set())
        if not options:
            no_data.append(rc.role)
            continue

        best_channel = rc.channel
        best_model = rc.model
        best_rate = current_rate
        best_samples = current_samples

        for ch, mod in options:
            if ch == rc.channel and mod == rc.model:
                continue
            rate, samples = _rate_for_role_channel(rc.role, ch, mod, rows, policy.gate_filter)
            if samples < policy.min_samples:
                continue
            # Prefer current if rate is within confidence threshold
            if policy.fallback_to_current and (
                abs(rate - current_rate) <= policy.confidence_threshold
            ):
                continue
            if rate > best_rate:
                best_channel = ch
                best_model = mod
                best_rate = rate
                best_samples = samples

        if best_channel != rc.channel or best_model != rc.model:
            changes.append(
                PlacementChange(
                    role=rc.role,
                    current_channel=rc.channel,
                    current_model=rc.model,
                    proposed_channel=best_channel,
                    proposed_model=best_model,
                    rationale=(
                        f"{best_channel}/{best_model or '—'} first-attempt pass rate "
                        f"{best_rate:.0%} ({best_samples} samples) vs current "
                        f"{rc.channel}/{rc.model or '—'} {current_rate:.0%} "
                        f"({current_samples} samples)"
                    ),
                    current_rate=current_rate,
                    proposed_rate=best_rate,
                    sample_count=best_samples,
                )
            )
        else:
            untouched.append(rc.role)

    return PlacementDiff(
        changes=tuple(changes),
        untouched=tuple(untouched),
        no_data=tuple(no_data),
    )


def apply(
    diff: PlacementDiff,
    config: FactoryConfig,
    mode: str = "dry-run",
    output_dir: Path | None = None,
) -> Path | None:
    """Apply a placement diff in one of three modes.

    Args:
        diff: The placement diff to apply.
        config: The current factory config (used for dry-run and propose-pr).
        mode: One of ``dry-run`` (default), ``propose-pr``, or ``live``.
        output_dir: Directory to write diff files.  Defaults to ``runs/`` under
            the repo root, creating it if necessary.

    Returns:
        The path to the written diff file (dry-run / propose-pr) or ``None``
        (live mode).
    """
    if mode not in ("dry-run", "propose-pr", "live"):
        raise ValueError(f"Unknown mode: {mode}. Use dry-run, propose-pr, or live.")

    if mode == "live":
        # Live mode is intentionally destructive and requires explicit consent.
        # In a non-interactive context this is a no-op with loud logging.
        log.warning(
            "placement_live_mode_skipped: Live mode requires explicit "
            "interactive confirmation. Re-run with --interactive or use "
            "propose-pr mode.",
        )
        return None

    out = output_dir or Path("runs")
    out.mkdir(parents=True, exist_ok=True)
    stamp = int(__import__("time").time())
    path = out / f"placement-{stamp}.diff"
    path.write_text(diff.to_json(indent=2))
    log.info("placement_diff_written", path=str(path), mode=mode)
    return path


def _main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Software Factory v2 - Placement Proposer")
    parser.add_argument(
        "--history-from",
        choices=["substrate"],
        default="substrate",
        help="Source of pass-rate history (only 'substrate' implemented)",
    )
    parser.add_argument(
        "--policy",
        choices=["highest-pass-rate"],
        default="highest-pass-rate",
        help="Placement policy to apply",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="runs",
        help="Output directory for diff files (default: runs/)",
    )
    parser.add_argument(
        "--mode",
        choices=["dry-run", "propose-pr", "live"],
        default="dry-run",
        help="Apply mode (default: dry-run)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to factory config YAML",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=DEFAULT_MIN_SAMPLES,
        help=f"Minimum samples required for a comparison group (default: {DEFAULT_MIN_SAMPLES})",
    )
    args = parser.parse_args(argv)

    from substrate import Substrate

    from factory.config import load_config
    from factory.telemetry import (
        _query_work_items_and_events,
        collect_gate_attempts,
        compute_pass_rates,
    )

    config = FactoryConfig() if args.config is None else load_config(args.config)
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    try:
        _work_items, events_by_id = _query_work_items_and_events(sub, config)
        attempts = collect_gate_attempts(sub, config, events_by_id=events_by_id)
        rows = compute_pass_rates(attempts)
    finally:
        sub.close()

    policy = PlacementPolicy(min_samples=args.min_samples)
    diff = propose(rows, config, policy=policy)

    if diff.changes:
        print("Proposed changes:")
        for ch in diff.changes:
            print(f"  {ch.role}: {ch.current_channel} -> {ch.proposed_channel}")
            print(f"    rationale: {ch.rationale}")
    else:
        print("No changes proposed.")

    if diff.no_data:
        print(f"Roles with no telemetry data: {', '.join(diff.no_data)}")

    out_path = apply(diff, config, mode=args.mode, output_dir=Path(args.output))
    if out_path:
        print(f"Diff written to: {out_path}")


def main() -> None:
    _main()


if __name__ == "__main__":
    main()
