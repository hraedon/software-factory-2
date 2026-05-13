# Interface Specification: Matcher

## Dependencies

- `interface_ref`: `refurb_config`
- `interface_ref`: `page_parser`

## AC-01: Match Listings to Predicates

A function `match_listings(listings: list[RefurbListing], predicates: list[WatchPredicate]) -> list[MatchResult]` must return one `MatchResult` per (listing, predicate) pair where the predicate matches the listing. A listing that matches zero predicates produces no results. A listing that matches multiple predicates produces one `MatchResult` per matching predicate.

`MatchResult` must be a dataclass with:
- `listing: RefurbListing`
- `predicate: WatchPredicate`
- `config_string: str` — from the listing (duplicated for convenience)
- `normalized_category: str` — the result of `normalize_category(listing.category)`

## AC-02: Config String Parsing

A function `parse_config_string(config_string: str) -> ParsedConfig` must decompose a raw config string into structured attributes. `ParsedConfig` must be a dataclass with:
- `chip: str | None` — chip family (e.g., "M4 Pro", "M4 Max", "M2 Ultra"), or None if no chip is mentioned
- `ram_gb: int | None` — unified memory in GB (e.g., 24, 128, 192), or None if not specified
- `storage_tb: float | None` — storage in TB (e.g., 1.0, 2.0), or None if not specified
- `cores: str | None` — core description as a string (e.g., "14-core CPU and 20-core GPU"), or None
- `raw: str` — the original config string

This is the most judgment-laden function in the system. The config strings on Apple's refurb page are natural language ("Apple M4 Pro chip with 14-core CPU and 20-core GPU, 24GB unified memory, 1TB SSD") and the parser must handle:
- Chip names: "M4", "M4 Pro", "M4 Max", "M2", "M2 Ultra", etc.
- RAM: "24GB unified memory", "24GB", "192GB unified memory"
- Storage: "1TB SSD", "2TB SSD", "512GB SSD"
- Missing fields: a listing might not mention cores, or might not mention storage
- Ambiguity: "M4 Pro Mac mini" — is "Pro" part of the chip name or the product name?

The test does not prescribe a parsing algorithm — it tests whether the structured output matches the semantic content of the input.

## AC-03: Predicate Matching with Parsed Config

The `matches` function from the `refurb_config` module must work correctly when given a `RefurbListing` whose `config_string` has been parsed by `parse_config_string`. Specifically:
- If `predicate.chip` is `"M4"`, it must match any listing whose parsed `chip` starts with `"M4"` (i.e., "M4", "M4 Pro", "M4 Max")
- If `predicate.min_ram_gb` is `128`, it must match listings where `parsed.ram_gb >= 128`, including `ram_gb=192`
- If `predicate.max_price_cents` is `150000`, it must match listings where `price_cents <= 150000`, including `price_cents=-1` (unknown price) — ambiguous listings should not be excluded by price filtering

This AC is a combinatorial interaction between AC-02 (parsing) and `refurb_config` AC-07 (matching). The system must compose these correctly.

## AC-04: Dedup Key Generation

A function `make_dedup_key(listing: RefurbListing) -> str` must produce a stable, deterministic string that uniquely identifies a product configuration across polling cycles. Two listings with the same dedup key are the same item. The key must be based on the normalized category and the full config string, not on price (which can change).

Format: `"{normalized_category}::{config_string}"` where `normalized_category` comes from `normalize_category(listing.category)`.

Price changes, URL changes, and position-on-page changes must NOT change the dedup key. A product that sells out and comes back at a different price must produce the same dedup key.