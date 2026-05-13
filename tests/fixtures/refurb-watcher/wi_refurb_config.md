# Interface Specification: Refurb Config

## Dependencies

None.

## AC-01: Predicate Model

A `WatchPredicate` dataclass must contain:
- `category: str` — product category (e.g., `"mac_mini"`, `"mac_studio"`)
- `chip: str | None` — chip family constraint (e.g., `"M4"`, `None` for any)
- `min_ram_gb: int | None` — minimum RAM in GB (e.g., `128`, `None` for any)
- `max_price_cents: int | None` — maximum price in cents (e.g., `150000`, `None` for any)
- `label: str` — human-readable description for notifications

## AC-02: Default Predicates

A function `default_predicates() -> list[WatchPredicate]` must return:

1. `WatchPredicate(category="mac_mini", chip="M4", min_ram_gb=None, max_price_cents=None, label="M4+ Mac mini (any config)")`
2. `WatchPredicate(category="mac_studio", chip=None, min_ram_gb=128, max_price_cents=None, label="Mac Studio with 128GB+ RAM")`

The "M4" chip value must match any chip string beginning with "M4" — i.e., "M4", "M4 Pro", and "M4 Max" are all M4-family chips. This is the first "except when" rule: `chip="M4"` means "M4 or any M4 variant", not strict equality.

## AC-03: Config Loading

A function `load_config(config_path: Path | None = None) -> RefurbConfig` must load YAML configuration from a file. If `config_path` is `None`, it uses `~/.config/refurb-watcher/config.yaml`. If the file does not exist, it returns a `RefurbConfig` with default predicates and default notification settings.

`RefurbConfig` must expose:
- `predicates: list[WatchPredicate]`
- `poll_interval_seconds: int` (default 300)
- `webhook_url: str | None` (default None)
- `state_db_path: str` (default `~/.config/refurb-watcher/seen.db`)
- `user_agent: str` (default `"refurb-watcher/1.0"`)

## AC-04: Config Validation

`load_config` must raise `ConfigError` with a descriptive message if:
- `poll_interval_seconds` is less than 60
- `webhook_url` is not None and is not a valid URL (must start with `http://` or `https://`)
- `predicates` list is empty

If `webhook_url` is None, the system must still run and log notifications instead of sending them. This is not an error condition — it is a valid configuration for dry-run mode.

## AC-05: Config Error Type

`ConfigError` must be a dataclass with `message: str` and `field: str | None`. The `field` value identifies which config key caused the error, or is `None` for multi-field errors.

## AC-06: Category Normalization

A function `normalize_category(raw_category: str) -> str` must map raw HTML category strings to canonical category names. At minimum, it must handle:
- `"Mac mini"` → `"mac_mini"`
- `"Mac Studio"` → `"mac_studio"`
- `"MacBook Pro"` → `"macbook_pro"`
- `"Mac Pro"` → `"mac_pro"`
- Any string containing `"Mac mini"` (case insensitive) → `"mac_mini"`

This is an "except when" rule: `"Refurbished Mac mini"` and `"Mac mini"` both normalize to `"mac_mini"`, but `"Mac Pro"` must not normalize to `"mac_mini"`. The implementer must handle substring matching without false positives.

## AC-07: Predicate Matching Logic

A function `matches(predicate: WatchPredicate, listing: RefurbListing) -> bool` must return `True` if and only if all non-None constraints in the predicate are satisfied by the listing:
- If `predicate.chip` is not None, the listing's chip family must start with `predicate.chip` (the "except when" M4-family rule from AC-02)
- If `predicate.min_ram_gb` is not None, the listing's RAM must be >= `predicate.min_ram_gb`
- If `predicate.max_price_cents` is not None, the listing's price must be <= `predicate.max_price_cents`
- Category matching uses the normalized category from AC-06

A predicate with all `None` constraints matches any listing in that category. A predicate with all `None` constraints and `category="*"` matches any listing regardless of category.