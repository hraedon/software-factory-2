# Refurb Watcher HTML Snapshots

Frozen test corpus for the page_parser work item. These snapshots represent
the extraction contract: the parser must handle all of these correctly or
return empty results gracefully. They are NOT part of the spec — the spec
describes what to extract, not how to extract it.

## Real Apple page structure

The actual Apple refurb page at https://www.apple.com/shop/refurbished/mac
embeds product data in two places:

1. **JSON-LD** (`<script type="application/ld+json">`) — Schema.org `Product`
   type with `name`, `url`, `offers.price`, `offers.sku`, and `description`.
   This is the most structured and most resilient extraction path.

2. **Visible HTML** — Product cards in `div.rf-refurb-category > ul.rf-product-list > li.rf-product`
   with `rf-product-title`, `rf-product-config`, `rf-product-price` classes.
   Apple uses en-dash (&#8209; / U+2011) in core counts like "14‑Core".

The implementer may use either path or combine both. The spec does not
prescribe which, only that the ACs are satisfied.

## Files

- `normal_page.html` — Standard refurbished Apple product page with Mac mini,
  Mac Studio, and MacBook Pro categories. Contains both JSON-LD and visible
  HTML. All prices in clean `$X,XXX.XX` format. En-dash in core counts.
  8 products across 3 categories.

- `empty_result.html` — Page with no listings (only an empty-message paragraph).
  Parser must return empty list, not crash or return stale data.

- `layout_shifted.html` — Same products but different HTML structure:
  `div.category-section` instead of `div.rf-refurb-category`, `div.product-card`
  instead of `li.product`, `div.specs` instead of `span.rf-product-config`,
  `div.cost` instead of `span.rf-product-price`. Prices in varied formats
  (bare number, dollar prefix, etc.). Tests that the parser doesn't rely on
  a single CSS selector structure. Also tests price parsing edge cases.

- `malformed_prices.html` — Products with deliberately tricky price formats:
  - Normal price: `$499.00`
  - Non-parseable price: `See price in cart` → price_cents = -1
  - Price with prefix: `Price: $1,599.00` → must still extract 159900
  - Missing price element entirely → price_cents = -1
  - Bare number (no dollar sign): `5,599` → 559900
  Also includes config strings with partially omitted core counts
  (`Apple M4 chip, 16GB unified memory, 256GB SSD` — no core spec).
  No JSON-LD in this snapshot — HTML-only extraction required.

- `structural_change_v2.html` — Apple changed their page structure. Same
  products but some config strings omit core/GPU specs entirely:
  - `Apple M4 chip, 16GB unified memory, 256GB SSD` (no cores)
  - `Apple M4 Pro chip, 24GB unified memory, 1TB SSD` (no cores)
  Tests that the parser handles config strings with missing optional fields.
  No JSON-LD in this snapshot.

- `jsonld_only_page.html` — Products exist only in JSON-LD `<script>` tags,
  the visible HTML has no product listings. Tests that the parser can
  extract from structured data when visible HTML is empty. This is actually
  the closest to Apple's real page structure, where JSON-LD is authoritative.

## Usage in the factory pipeline

These files are referenced by the fixture's acceptance criteria. The
page_parser ACs describe expected behavior for each case. The implementer
must write a parser that handles all of these without crashing, and the
gate tests should validate extraction against them.

They are NOT referenced in spec.md or spec.yaml — those documents describe
the extraction contract abstractly.