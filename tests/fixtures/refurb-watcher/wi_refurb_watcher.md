# Interface Specification: Refurb Watcher

## Dependencies

- `interface_ref`: `refurb_config`
- `interface_ref`: `page_fetcher`
- `interface_ref`: `page_parser`
- `interface_ref`: `matcher`
- `interface_ref`: `seen_store`
- `interface_ref`: `notifier`

## AC-01: Run One Cycle

A function `run_cycle(config: RefurbConfig) -> CycleResult` must execute one complete polling cycle and return a `CycleResult` dataclass with:
- `listings_found: int` — total listings parsed from the page
- `new_matches: int` — listings that matched a predicate and were previously unseen
- `restocked_matches: int` — listings that matched a predicate and were previously sold out
- `sold_out_count: int` — previously available items that are no longer on the page
- `notifications_sent: int`
- `notifications_failed: int`
- `errors: list[str]` — descriptions of any non-fatal errors encountered

The cycle must execute these steps in order:
1. Fetch the page using `fetch_with_retry`
2. If fetch failed, return `CycleResult` with zero counts and the error in `errors`
3. Parse listings from the HTML
4. Match listings against predicates
5. Reconcile current listings against the seen store
6. Send notifications for new and restocked items
7. Mark all current listings as seen
8. Mark sold-out items

## AC-02: Graceful Degradation

If any individual step in the cycle fails, the watcher must not crash. Specifically:
- If the page fetch fails (network error, timeout), return a `CycleResult` with `listings_found=0` and the error in `errors`
- If parsing returns an empty list (not an error — the page may genuinely have no listings), proceed with empty results
- If a notification fails, increment `notifications_failed` and continue sending other notifications
- If the seen store is unavailable, log the error and return a `CycleResult` with zero state-change counts and the error in `errors`

At no point must `run_cycle` raise an exception for any condition other than a programming bug. All expected failure modes produce a valid `CycleResult`.

## AC-03: Scheduled Run Loop

A function `run_watcher(config: RefurbConfig) -> None` must execute `run_cycle` repeatedly at `config.poll_interval_seconds` intervals. Between cycles, the function must sleep (not busy-wait). On SIGINT or SIGTERM, the function must complete the current cycle (if running), persist any pending state, and exit cleanly.

## AC-04: Run Now

A function `run_once(config: RefurbConfig) -> CycleResult` must execute a single `run_cycle` and return. This is the programmatic entry point for testing and one-shot execution.

## AC-05: Dedup Across Cycles

After two consecutive cycles where the same item appears on the page:
- First cycle: item is `new`, notification is sent, `mark_seen` returns `True`
- Second cycle: item is `unchanged`, no notification is sent, `mark_seen` returns `False`
- No duplicate notifications for the same available item across cycles.

After a cycle where an item disappears from the page (sold out), then reappears in a later cycle:
- Cycle N: item appears, `mark_seen` returns `True`, notification sent
- Cycle N+1: item not on page, `mark_sold_out` called, `reconcile.sold_out_keys` contains the key
- Cycle N+2: item reappears, `mark_seen` returns `True` (re_available), notification sent as "restocked"

This is a combinatorial AC interaction across the run_cycle orchestrator, seen_store state transitions, and notifier dedup. Each component's behavior is individually specifiable, but the interaction across cycles is where subtle bugs emerge.

## AC-06: Config Reload

The watcher must reload `RefurbConfig` from disk at the start of each cycle. If the config file has changed between cycles, the new predicates, webhook URL, and poll interval take effect immediately. If the config file is missing or invalid, the watcher must log an error and continue using the previous valid configuration — it must not crash or stop polling.