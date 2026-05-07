#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from substrate import Substrate

DSN = "postgresql://substrate_test:substrate_test@localhost:5432/substrate_test"
KEY_PATH = str(Path(__file__).resolve().parent / "tests" / "test_keys.json")


def run_report(dsn: str, project: str, key_path: str):
    sub = Substrate(dsn, project, key_path)

    page = sub.query_work_items(
        workflow_name="software_factory",
        workflow_version=1,
        page_size=50,
    )

    by_state = defaultdict(list)
    by_shape: dict[str, list] = defaultdict(list)
    items = []

    for wi in page.items:
        items.append(wi)
        by_state[wi.current_state].append(str(wi.work_item_id))
        cf = wi.custom_fields or {}
        shape = cf.get("shape", "unknown")
        by_shape[shape].append(wi)

    print("=" * 72)
    print("Phase 1 Run Report")
    print("=" * 72)

    print("\nState summary:")
    for state in ("new", "in_progress", "gating", "locked", "cannot_proceed"):
        ids = by_state.get(state, [])
        print(f"  {state:16s}: {len(ids):>3}")

    print(f"\nTotal work-items: {len(items)}")

    total_locked = len(by_state.get("locked", []))

    print("\nPer-work-item detail:")
    print(f"  {'Item':>8s}  {'Shape':20s}  {'State':16s}  {'Att':>3s}  "
          f"{'Context Hash':>16s}  Gate Diagnostics")
    print(f"  {'-'*8}  {'-'*20}  {'-'*16}  {'-'*3}  {'-'*16}  {'-'*20}")

    for wi in sorted(items, key=lambda w: str(w.work_item_id)):
        cf = wi.custom_fields or {}
        shape = cf.get("shape", "?")
        diagnostics = cf.get("diagnostics", None)

        att_n = "?"
        ctx_hash = ""

        try:
            events = sub.read_events(work_item_id=wi.work_item_id, limit=100)
            for ev in events:
                md = ev.actor_metadata or {}
                ch = md.get("context_hash", "") or ""
                if ch:
                    ctx_hash = ch[:16]
                an = md.get("attempt_n", 0) or 0
                if an:
                    att_n = str(an)
        except Exception:
            pass

        diag_str = ""
        if diagnostics and isinstance(diagnostics, dict):
            gname = diagnostics.get("gate_name", "?")
            passed = diagnostics.get("passed", "?")
            msgs = diagnostics.get("messages", [])
            suffix = f" — {msgs[0][:60]}" if msgs else ""
            diag_str = f"{gname} (pass={passed}){suffix}"

        print(
            f"  {str(wi.work_item_id)[:8]:>8s}  {shape:20s}  "
            f"{wi.current_state:16s}  {att_n:>3s}  {ctx_hash:>16s}  {diag_str}"
        )

    print("\nCategory breakdown:")
    for shape in ("pure-interface", "error-taxonomy", "ADT-validation", "adversarial"):
        shape_items = by_shape.get(shape, [])
        locked_count = sum(1 for wi in shape_items if wi.current_state == "locked")
        total = len(shape_items)
        rate = f"{locked_count}/{total}" if total > 0 else "—"
        pct = f" ({locked_count/total*100:.0f}%)" if total > 0 else ""
        print(f"  {shape:20s}: {rate} locked{pct}")

    print("\n--- Phase 1 Exit Criteria ---")

    primary_locked = total_locked
    criteria_line = (
        f"  Primary set (>=9/10 locked): {primary_locked}/10 "
        f"{'PASS' if primary_locked >= 9 else 'FAIL'}"
    )
    print(criteria_line)

    adversarial_items = by_shape.get("adversarial", [])
    adversarial_cannot_proceed = all(
        wi.current_state == "cannot_proceed" for wi in adversarial_items
    )
    adv_state = (
        "cannot_proceed"
        if adversarial_items and adversarial_cannot_proceed
        else f"FAIL ({len(adversarial_items)} adversarial items, "
        f"{sum(1 for wi in adversarial_items if wi.current_state == 'cannot_proceed')} "
        f"in cannot_proceed)"
    )
    print(f"  Adversarial (cannot_proceed): {adv_state}")

    for shape in ("pure-interface", "error-taxonomy", "ADT-validation"):
        shape_items = by_shape.get(shape, [])
        locked_count = sum(1 for wi in shape_items if wi.current_state == "locked")
        total = len(shape_items)
        passes = f"{locked_count}/{total}" if total > 0 else "0/0"
        meets = locked_count >= 2 or total == 0
        print(f"  {shape:20s} >=2/3 per category: {passes} {'PASS' if meets else 'FAIL'}")

    all_pass = (primary_locked >= 9 and adversarial_items and adversarial_cannot_proceed
                and all(sum(1 for wi in by_shape.get(s, []) if wi.current_state == "locked") >= 2
                        if by_shape.get(s) else True
                        for s in ("pure-interface", "error-taxonomy", "ADT-validation")))
    print(f"\n  Overall exit criteria met: {'YES' if all_pass else 'NO'}")

    sub.close()


def main():
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Phase 1 run report from substrate event log")
    parser.add_argument("--project", default="sf2_test", help="Substrate project name")
    parser.add_argument("--dsn", default=DSN, help="Postgres connection string")
    parser.add_argument("--key-path", default=KEY_PATH, help="Path to HMAC key file")
    args = parser.parse_args()
    run_report(args.dsn, args.project, args.key_path)


if __name__ == "__main__":
    main()
