# Interface Specification: Page Parser

## Dependencies

- `interface_ref`: `refurb_config`

## AC-01: Parse Listings

A function `parse_listings(html: str, source_url: str) -> list[RefurbListing]` must extract all product listings from the refurb page HTML and return them as a list of `RefurbListing` dataclass instances with:
- `config_string: str` — the full configuration description as it appears on the page (e.g., "Apple M4 Pro chip with 14-core CPU and 20-core GPU, 24GB unified memory, 1TB SSD")
- `price_cents: int` — the listing price in cents (e.g., $1,399 → 139900)
- `category: str` — the raw category string as extracted from the page (e.g., "Mac mini")
- `product_url: str` — the URL of the product detail page
- `source_url: str` — the URL of the page this listing was parsed from
- `parsed_at: datetime` — UTC timestamp of when parsing completed

## AC-07: Unicode Handling

Apple's refurb page uses en-dash (U+2011, `‑`) in core counts like "14‑Core CPU" and hyphen-minus (U+002D, `-`) interchangeably. The parser must treat both as equivalent for the purposes of `config_string` extraction and downstream matching. A `config_string` containing "14‑Core" and one containing "14-Core" are the same configuration and must produce the same dedup key.

## AC-02: Config String Extraction

The `config_string` must be the complete configuration text as presented on the page — chip, cores, RAM, storage, display — concatenated into a single string that uniquely identifies the configuration. The parser must not truncate or summarize the config string. Two listings with the same `config_string` after `normalize_category` are the same item for dedup purposes.

This is a judgment-laden extraction: the parser must identify which text on the page constitutes the "configuration" as opposed to the marketing copy, the price, the "Add to Cart" label, etc. The spec does not prescribe which HTML elements contain this information — that is the implementer's challenge. Apple's real refurb page embeds product data as JSON-LD (`<script type="application/ld+json">`) alongside visible HTML. Either extraction path is valid provided the ACs are satisfied. The implementer may find JSON-LD more resilient than CSS selectors, but is not required to use it.

## AC-03: Price Parsing

The parser must handle all of the following price formats:
- `"$1,399.00"` → 139900
- `"$1,399"` → 139900
- `"1399"` → 139900 (interpret bare numbers as dollars)
- `"$1,399.99"` → 139999

If a listing has no parseable price, the `RefurbListing` must have `price_cents = -1` (sentinel value for "unknown price"). A price of `-1` is not zero, not free, and not default — it means "the parser could not extract a price from this listing."

## AC-04: Resilience to Layout Changes

If the parser encounters HTML where it cannot find any product listings, it must return an empty list — not raise an exception and not return stale/cached data. An empty list from the parser is a valid, unambiguous signal meaning "nothing was found on this page."

Similarly, if the parser finds a listing element but cannot extract a `config_string` from it, that listing must be omitted from the results (not included with `config_string=""`). Partial extraction is preferred over missing the extractable listings.

## AC-05: Empty or Malformed HTML

If `parse_listings` receives an empty string, it must return an empty list. If it receives HTML with no recognizable product structure, it must return an empty list. The function must never raise an exception for any input — all inputs produce either a list of listings or an empty list.

## AC-06: Category Extraction

The parser must extract the category label as it appears on the page. The raw category is stored in `RefurbListing.category` for downstream normalization by `normalize_category` (defined in the `refurb_config` module). The parser does not normalize — it preserves what it found.