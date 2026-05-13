# Interface Specification: Seen Store

## Dependencies

- `interface_ref`: `refurb_config`

## AC-01: Persist Seen Items

A `SeenStore` class must persist information about previously seen refurb listings across application restarts. The store must use SQLite or Postgres (implementer's choice) as the backing store, configured by `RefurbConfig.state_db_path`.

## AC-02: Mark as Seen

A method `mark_seen(dedup_key: str, listing_snapshot: SeenItem) -> bool` must record that a dedup key has been seen. `SeenItem` is a dataclass with:
- `dedup_key: str`
- `config_string: str`
- `price_cents: int`
- `status: str` — one of `"available"`, `"sold_out"`, `"re_available"`
- `seen_at: datetime`
- `first_seen_at: datetime`

If the dedup key has not been seen before, `mark_seen` must create a new record with `first_seen_at = seen_at` and `status = "available"`, and return `True` (indicating this is a new item).

If the dedup key has been seen before with `status = "sold_out"`, `mark_seen` must update the record to `status = "re_available"` and update `price_cents` and `seen_at`, and return `True` (indicating a restocked item that should be re-alerted).

If the dedup key has been seen before with `status = "available"`, `mark_seen` must update `seen_at` and `price_cents` (if changed) but preserve `status = "available"`, and return `False` (indicating no state change — no re-alert needed).

If the dedup key has been seen before with `status = "re_available"`, `mark_seen` must update `seen_at` and `price_cents` (if changed) but preserve `status = "re_available"`, and return `False`.

This is the core statefulness challenge: identity is the dedup key (stable across restocks), but presence is the status (available, sold out, re-available). A price change on an available item is not a re-alert event. A sell-out-then-restock IS a re-alert event.

## AC-03: Mark as Sold Out

A method `mark_sold_out(dedup_key: str) -> bool` must update the status of a seen item to `"sold_out"`. Returns `True` if the item's status changed (was `"available"` or `"re_available"`), `False` if the item was already `"sold_out"` or not found.

## AC-04: Query Seen Status

A method `get_status(dedup_key: str) -> SeenItem | None` must return the current record for a dedup key, or `None` if never seen.

A method `list_all() -> list[SeenItem]` must return all seen items ordered by `first_seen_at` ascending.

A method `list_available() -> list[SeenItem]` must return only items with `status in ("available", "re_available")`.

## AC-05: Idempotency

`mark_seen` and `mark_sold_out` must be idempotent. Calling `mark_seen` twice with the same dedup key and same data must produce the same result as calling it once. Calling `mark_sold_out` on an already-sold-out item must return `False` and not modify the record.

## AC-06: Reconcile Against Current Listings

A method `reconcile(current_keys: set[str]) -> ReconcileResult` must compare the current set of dedup keys against the store and produce a `ReconcileResult`:
- `new_keys: set[str]` — keys in `current_keys` but not in the store (genuinely new items)
- `restocked_keys: set[str]` — keys in `current_keys` that were previously `"sold_out"` (will be updated by `mark_seen`)
- `sold_out_keys: set[str]` — keys in the store with `status in ("available", "re_available")` that are not in `current_keys` (items that disappeared from the page)
- `unchanged_keys: set[str]` — keys in `current_keys` that are in the store with `status in ("available", "re_available")` (no state change)

This is a combinatorial AC interaction: the reconcile method must correctly handle the four-way intersection/intersection of current listings, previous availability, previous sold-out status, and new items. Getting any of these wrong cascades into missed alerts or false alerts.

## AC-07: Schema Initialization

A function `init_store(db_path: str | Path) -> None` must create the database schema if it does not exist. Must be idempotent — safe to call on an already-initialized database.