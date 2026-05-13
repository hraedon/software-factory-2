# Interface Specification: Notifier

## Dependencies

- `interface_ref`: `refurb_config`
- `interface_ref`: `matcher`
- `interface_ref`: `seen_store`

## AC-01: Send Discord Notification

A function `send_notification(match: MatchResult, config: RefurbConfig) -> bool` must POST a JSON payload to `config.webhook_url`. If `config.webhook_url` is None, the function must log the notification at INFO level and return `True` (dry-run mode, not an error). The payload must be a Discord webhook embed with:
- `title`: the `match.predicate.label`
- `description`: a human-readable summary including the config string, price, and normalized category
- `url`: the `match.listing.product_url`
- `color`: green (0x00FF00) for new items, yellow (0xFFFF00) for restocked items
- `footer`: "refurb-watcher"

The function must return `True` on successful delivery and `False` on any failure (network error, non-2xx response). It must not raise exceptions for any failure condition.

This is a judgment-laden output AC. The test can verify that the embed contains the required fields, but cannot mechanically verify that the summary is "good" for a human reader. The spec deliberately does not prescribe the exact wording of the description — only that it includes config string, price, and category.

## AC-02: Format Price

A function `format_price(price_cents: int) -> str` must format a price in cents as a human-readable dollar string:
- `139900` → `"$1,399"` (whole dollars, comma-separated)
- `139999` → `"$1,399.99"` (includes cents only when non-zero)
- `-1` → `"Price unknown"` (sentinel value from parser)
- `0` → `"Free"` (edge case)

This is a judgment-laden formatting AC. The implementation must handle the edge cases correctly — there is no single "right" format, but there are wrong formats (raw cents, scientific notation, missing currency symbol).

## AC-03: Format Summary

A function `format_summary(matches: list[MatchResult], reconciled: ReconcileResult) -> str` must produce a plain-text summary of all changes in a polling cycle. The summary must include:
- Number of new items found
- Number of restocked items found
- Number of items sold out since last check
- For each new/restocked item: the config string, price, and predicate label

The summary must be human-readable. This AC tests that the system can compose multiple pieces of state (new matches, restocked items, sold-out items) into a coherent narrative, not just a data dump.

## AC-04: Batch Notification

A function `notify_all(matches: list[MatchResult], reconciled: ReconcileResult, config: RefurbConfig) -> dict[str, int]` must send one notification per new or restocked item and return counts: `{"sent": N, "failed": M}`. Items that are `unchanged` must not generate notifications. Items that are `sold_out` must not generate notifications (sell-out is not an alert condition in the current design — only visibility and restocking are alert-worthy).

If `send_notification` returns `False` for any item, `notify_all` must increment the `failed` count and continue — it must not stop sending on first failure.

## AC-05: Rate Limit Handling

If the Discord API returns a 429 response, `send_notification` must extract the `Retry-After` header value and wait that many seconds before retrying once. If the retry also fails, return `False`. This must not interact with the page fetcher's rate limiting — these are independent rate limit domains.

## AC-06: Notification Dedup

Within a single `notify_all` call, if the same `dedup_key` appears in both `new_keys` and `restocked_keys` (which should not happen given correct reconcile semantics, but the system must be resilient), `notify_all` must send only one notification marked as "restocked" (the more informative status), not two.