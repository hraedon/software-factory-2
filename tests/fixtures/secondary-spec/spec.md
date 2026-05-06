# Date-Range Parser — Spec

**Status:** stable
**Domain:** line-of-business utility library
**Purpose:** parse human-written date-range expressions into structured `(start, end)` tuples for downstream filtering.

This spec is the secondary test set for SF2 Phase 1 (per `plans/phase1-implementation.md` Wave 6). It is intentionally domain-disjoint from substrate and unambiguously LoB-flavored — exactly the kind of small utility a non-developer might describe in a Slack message.

---

## 1. Purpose

Operators in a back-office tool type date ranges as free-form English: "last week", "Q1 2026", "March 1–March 15", "since Tuesday". A library that converts these into `(start: date, end: date)` tuples lets the rest of the application filter records uniformly. Today this conversion is done by a `if/elif` chain that has accumulated ten years of bugs.

## 2. Non-goals

- Time-of-day precision. Output is always whole-day inclusive ranges.
- Time zones. All parsing happens in the operator's local time.
- Recurring ranges ("every Monday in March"). Single contiguous ranges only.
- Natural language beyond the patterns enumerated below. Unrecognized input returns a structured error, not a guess.

## 3. Functional requirements

### FR-01: Relative-period parsing

The library MUST parse the following relative-period expressions, anchored to a `today: date` parameter:

- `"today"` → `(today, today)`
- `"yesterday"` → `(today - 1, today - 1)`
- `"last week"` → previous Monday through previous Sunday
- `"this week"` → current Monday through current Sunday
- `"last month"` → first through last day of previous calendar month
- `"this month"` → first through last day of current calendar month
- `"last quarter"` → first through last day of previous calendar quarter (Q1=Jan–Mar, etc.)
- `"this quarter"` → first through last day of current calendar quarter
- `"year to date"` → January 1 of current year through `today`

Case-insensitive. Leading/trailing whitespace tolerated.

### FR-02: Explicit-range parsing

The library MUST parse explicit date ranges in these forms:

- `"YYYY-MM-DD to YYYY-MM-DD"` (ISO, with `to` separator)
- `"YYYY-MM-DD..YYYY-MM-DD"` (ISO, with `..` separator)
- `"Month D, YYYY – Month D, YYYY"` (e.g., `"March 1, 2026 – March 15, 2026"`, en-dash or hyphen)
- `"QN YYYY"` (e.g., `"Q1 2026"`) → first through last day of that quarter

Month names: full English (`"January"`) or three-letter abbreviation (`"Jan"`), case-insensitive.

### FR-03: Structured errors

Unparseable input MUST return a structured error with:

- An `ErrorCode` enum value (`UNRECOGNIZED_FORMAT`, `INVALID_DATE`, `INVERTED_RANGE`, `OUT_OF_BOUNDS`).
- A human-readable `message`.
- The original input string verbatim, for logging.

Errors are returned, not raised. The library never raises on user input.

## 4. Acceptance criteria

### AC-01 (FR-01): Relative-period parsing — pure function, deterministic on (input, today)

Given a `today` of `2026-05-06` (Wednesday), `parse_range("last week", today)` returns `(2026-04-27, 2026-05-03)`. All nine relative-period patterns return correct ranges for at least three distinct `today` values spanning quarter and year boundaries. Case and whitespace variants of each pattern resolve identically.

**Work-item shape:** pure-interface. Single function, signature + types only.

### AC-02 (FR-02): Explicit-range parsing — error taxonomy on bad input

`parse_range("2026-03-15 to 2026-03-01", today)` returns an error with `code == INVERTED_RANGE`. `parse_range("2026-13-40 to 2026-12-01", today)` returns `INVALID_DATE`. `parse_range("Q5 2026", today)` returns `INVALID_DATE`. `parse_range("sometime in March", today)` returns `UNRECOGNIZED_FORMAT`. Valid inputs across all four explicit-range forms parse correctly. The function never raises on string input.

**Work-item shape:** interface-with-error-taxonomy. The contract centrally features the `ErrorCode` enum and the structured-error return type.

### AC-03 (FR-03): Result type carries enough structure for downstream filtering

The return type is a tagged union (or equivalent) such that callers can pattern-match on success vs. error without inspecting attribute presence. The success variant carries `start: date`, `end: date`, and a `pattern_matched: str` field naming which FR-01/FR-02 pattern fired (for telemetry). The error variant carries the fields enumerated in FR-03. Inclusive range semantics are documented on the type, not implicit.

**Work-item shape:** interface-with-ADT-validation. The contract requires defining a structured payload (the `Result` ADT) that downstream code consumes.

## 5. Glossary

- **Range** — a `(start, end)` pair of `date` values, inclusive on both ends.
- **Anchor** — the `today` parameter, used for resolving relative-period expressions.
- **Pattern** — one of the enumerated FR-01 or FR-02 input forms.
- **Inclusive** — both endpoints are part of the range. `(2026-03-01, 2026-03-15)` includes both March 1 and March 15.

## 6. Out of scope (explicit)

- Arbitrary natural-language fuzzy matching ("a couple weeks ago"). Unrecognized → error.
- Locale variants (German month names, French separators). English only.
- Calendar variants (fiscal years that don't align to Q1=Jan–Mar). Standard calendar quarters only.
- Performance. Inputs are short strings; an `O(n)` regex sweep is fine.
