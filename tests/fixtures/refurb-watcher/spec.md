# Specification: Refurb Watcher

**Spec Level:** 2
**Desired Level:** 3
**Date:** 2026-05-12
**Extensions active:** None

---

## 1. Problem Statement

**Problem:** Apple's refurb store offers limited-quantity hardware at significant discounts, but stock turns over in minutes. There's no API and no push notification — the only signal is the HTML of the refurb page, which changes without notice. Manual refreshing isn't fast enough, and the listing format requires judgment to match against preferences like "M4+ Mac mini" or "Mac Studio with 128GB+ RAM."

**User/Operator:** A single operator running this as a personal tool on a schedule. Low operational overhead — the system should be cheap to run continuously and require no maintenance beyond what Apple's DOM changes force. Not multi-user, not production SaaS.

**Success condition:** The system reliably detects new and restocked refurb items matching configured predicates, deduplicates across polling cycles (including sell-out-and-return), and posts human-readable alerts to a Discord webhook — all despite Apple changing their HTML layout silently. A missed alert the user would have acted on is a correctness failure; a false alert is an annoyance but not a failure.

---

## 2. Glossary

| Term | Definition |
|---|---|
| dedup key | A stable, deterministic string uniquely identifying a product configuration across polling cycles. Format: `{normalized_category}::{config_string}`. Price changes do not change the dedup key. |
| config string | The full configuration text as presented on Apple's refurb page (e.g., "Apple M4 Pro chip with 14-core CPU and 20-core GPU, 24GB unified memory, 1TB SSD"). Two listings with the same config string are the same item. |
| restocked | An item previously seen with status "sold_out" has reappeared. Re-alert-worthy, distinct from "new." |
| M4-family chip | Any chip whose name starts with "M4" — includes M4, M4 Pro, M4 Max. "M4" in the spec means the entire family. |
| normalized category | Canonical form of a raw HTML category string. "Mac mini" → "mac_mini", "Mac Studio" → "mac_studio". |
| price_cents | Price in integer cents. $1,399.00 = 139900. Sentinel -1 = unknown price. |
| cycle | One complete polling iteration: fetch → parse → match → reconcile → notify → mark seen/sold out. |

---

## 3. Scope

**In scope:**
- Polling Apple's refurb page at a configurable interval
- Parsing product listings from arbitrary HTML
- Matching listings against configurable predicates with M4-family expansion
- Deduplication across cycles, including sell-out and restock detection
- Discord webhook notification for new and restocked items
- Human-readable formatting of notifications and summaries
- Graceful handling of network failures, empty pages, and DOM changes

**Out of scope:**
- Authentication or authorization
- Payment or checkout integration
- Multi-user state or account management
- Historical analytics or trend tracking
- Automated purchasing
- Monitoring non-Apple refurb sources

---

## 4. MVP Definition

**MVP is:** A single-operator tool that polls Apple's refurb page, detects M4+ Mac minis and 128GB+ Mac Studios, deduplicates across cycles, and posts new/restocked alerts to a Discord webhook.

**MVP functional requirements:** FR-01 through FR-06 (all)

**Rationale:** All FRs are required for the tool to be useful. Skipping dedup means spam; skipping matching means irrelevant alerts; skipping notification means no value delivery.

**Note to implementing agent:** FR-01 (config) and FR-04 (state store) are invisible infrastructure — you must build them before the user-facing features can function.

**Architectural prerequisites:**
- FR-01 requires config loading infrastructure → resolution: invisible_infrastructure
- FR-04 requires persistent state store (SQLite/Postgres) → resolution: invisible_infrastructure

---

## 5. Functional Requirements

- FR-01 **[MVP]**: Given a config file or defaults, the system loads watch predicates, poll interval, webhook URL, and state path. M4-family chip expansion is built into the predicate model.
- FR-02 **[MVP]**: Given a URL, the system fetches page HTML with timeout, retry on transient failure, and rate limiting. All failure modes return structured errors, not exceptions.
- FR-03 **[MVP]**: Given HTML from the refurb page, the system extracts product listings with config strings, prices, categories, and URLs. The parser must be resilient to DOM changes and return empty (not crash) when it cannot parse.
- FR-04 **[MVP]**: Given current listings and prior seen state, the system reconciles new, restocked, sold-out, and unchanged items. Identity is the dedup key; presence is the status. A sold-out item that reappears is restocked and re-alerted.
- FR-05 **[MVP]**: Given match results and reconcile output, the system sends Discord webhook notifications for new and restocked items. Unknown prices are formatted as "Price unknown", not excluded.
- FR-06 **[MVP]**: Given a configuration, the system runs repeated polling cycles at the configured interval, with clean shutdown on signal, config reload between cycles, and graceful degradation on any step failure.

---

## 6. Data

**Inputs:**
- Refurb page HTML (format: HTML, source: HTTP GET to Apple's refurb store, validation: non-empty string; parse_listings handles all content)
- Config file (format: YAML, source: local filesystem `~/.config/refurb-watcher/config.yaml`, validation: load_config validates required fields and ranges)

**Outputs:**
- Discord webhook payloads (format: JSON Discord embed, destination: config.webhook_url via HTTP POST)
- Cycle result log (format: structured log lines, destination: stdout/stderr)

**Persisted state:**
- Seen items with dedup key, config string, price, status, timestamps (location: SQLite or Postgres at config.state_db_path, retention: indefinite until manually pruned)

---

## 7. Business Rules

- BR-01: M4-family chip expansion — predicate with `chip="M4"` matches "M4", "M4 Pro", and "M4 Max". Family matching, not substring.
- BR-02: Dedup key is `(normalized_category, config_string)`. Price is mutable. Different prices on the same dedup key = same item, not a new item.
- BR-03: Re-alert only for new items and sold-out → available transitions. Price changes on an available item do not trigger re-alert.
- BR-04: Unknown price (`price_cents=-1`) does not exclude from matching. Optimistic inclusion when price is unknown and max_price is set.
- BR-05: Poll interval minimum 60 seconds. Default 300 seconds (5 minutes).

---

## 8. Error and Failure Handling

| Failure | Trigger | Response | Notification |
|---|---|---|---|
| Page fetch timeout | Connection or read timeout | FetchError with error_type="timeout"; skip cycle | CycleResult.errors |
| Page fetch HTTP error | Non-2xx after retries | FetchError; skip cycle | CycleResult.errors |
| Empty parse result | No listings found (could be DOM change or genuine empty) | Proceed with empty listings; reconcile marks items as sold_out | None |
| Malformed price | Parser can't extract price | Set price_cents=-1; include listing | None |
| Discord webhook failure | HTTP error or timeout on POST | Return False; increment failed; continue others | None (individual) |
| State store unavailable | SQLite/Postgres connection fails | Log error; CycleResult with zero counts | CycleResult.errors |
| Config file invalid/missing after first load | File deleted or corrupted between cycles | Log error; continue with last valid config | None |

---

## 9. Non-Functional Requirements

- **Performance:** Page fetch and parse under 30 seconds total — derived from: "refurb stock turns over in minutes, the system must not lose events"
- **Reliability:** Recovers from any single-step failure within one cycle — derived from: "if the fetch fails, try again next cycle, don't crash"
- **Operability:** Single-process background service with configurable cadence — derived from: "cheap to run continuously on a tight cadence"

---

## 10. High-Coupling Decisions

| Decision | Status | Notes |
|---|---|---|
| Dedup key format and identity semantics | Decided | `normalized_category::config_string`. Price mutable. Sold-out-then-restock = re-alert. |
| Parsing strategy | Deferred with flexibility | Spec says "extract from arbitrary HTML"; implementer chooses technique. Empty result is valid. |
| State persistence backend | Deferred with flexibility | SQLite or Postgres. Config provides path/DSN. ACs test behavior, not storage. |
| HTML test corpus | Deferred with flexibility | Lives in fixture, not spec. Implementer handles any valid HTML. |

---

## 11. Acceptance Criteria and Test Plan

**Testable items:**

- AC-RW-01 [FR-01]: Given no config file, load_config returns RefurbConfig with default predicates, poll_interval_seconds=300, webhook_url=None
- AC-RW-02 [FR-01]: Given predicate with chip="M4", matches returns True for listings with chip "M4", "M4 Pro", and "M4 Max"
- AC-RW-03 [FR-01]: Given predicate with min_ram_gb=128, matches returns True for listings with ram_gb=128 and ram_gb=192
- AC-RW-04 [FR-02]: Given a URL that times out, fetch_with_retry returns FetchError with error_type="retry_exhausted" after 3 retries
- AC-RW-05 [FR-03]: Given empty HTML string, parse_listings returns empty list without raising
- AC-RW-06 [FR-03]: Given HTML with no recognizable product structure, parse_listings returns empty list without raising
- AC-RW-07 [FR-04]: Given sold-out item that reappears in current_keys, reconcile returns it in restocked_keys
- AC-RW-08 [FR-04]: Given mark_seen called twice for same dedup_key with status available, second call returns False
- AC-RW-09 [FR-05]: Given price_cents=-1, format_price returns "Price unknown"
- AC-RW-10 [FR-05]: Given a notification failure, notify_all continues sending remaining and returns incremented failed count
- AC-RW-11 [FR-06]: Given page fetch failure, run_cycle returns CycleResult with errors containing the failure and zero counts

**Untestable items:**

| Item | Reason untestable |
|---|---|
| Human readability of notification summaries | No mechanical gate distinguishes good from passable prose |
| Resilience to future DOM changes not in test corpus | Non-deterministic; corpus covers known cases only |

---

## 12. Work Decomposition

### Value Phases — owned by the human

- **Phase 1 (MVP):** FR-01 through FR-06 — full system that polls, matches, deduplicates, and alerts

### Implementation Phasing — agent-owned

The agent must derive build order from architectural dependencies. Known prerequisites:
- FR-01 (config) is invisible infrastructure required by all other FRs
- FR-04 (state store) requires FR-01's config to know where to persist
- FR-06 (orchestrator) depends on all other FRs

**Dependency hints** (intent-level, not authoritative):
- FR-01: no prerequisites
- FR-02: requires FR-01 (config for URL, timeout, user agent)
- FR-03: requires FR-01 (config for category normalization)
- FR-04: requires FR-01 (config for state path)
- FR-05: requires FR-01, FR-03 (parsed listings), FR-04 (reconcile results)
- FR-06: requires all other FRs

---

## 13. Open Questions

| Question | Category | Owner |
|---|---|---|
| What if Apple's page returns a different content type (e.g., JSON API)? | Unknowable | Implementer |
| Should sold-out items trigger a notification? | Indifferent | Principal |
| What is the max concurrent listings on Apple's page? | Needs research | Implementer |

---

## 14. Assumptions

- Apple's refurb page is publicly accessible without authentication — principal stated at scoping.
- Apple's refurb page returns valid UTF-8 HTML — industry standard; if not, fetcher returns FetchError.
- Discord webhook API is stable and documented — documented, versioned API.
- A single process can handle one poll cycle within the 5-minute default interval — fetch+parse+notify completes in seconds.

---

## 15. Handoff State

**Decisions made:**
- Dedup key is `category::config_string` (not including price) — price changes on an available item are not re-alert-worthy.
- Unknown price (-1) is optimistically included in matching — never lose a potential match because the parser couldn't read the price.
- M4-family expansion is in the predicate model, not the parser — parser extracts what's on the page; matcher interprets it.

**Pending / deferred:**
- HTML test corpus — needs real Apple refurb page captures. Impact if wrong: low (parser ACs are behavioral).

**Intent signals:**
- "Refurb stock turns over in minutes" — system must not lose events. Drives reliability NFR and poll cadence.
- "Will use this personally" — higher quality bar than synthetic fixture; correctness failures have real consequence.
- "Respect Apple's ToS" — default user-agent identifies the tool; default 5-min interval is conservative.