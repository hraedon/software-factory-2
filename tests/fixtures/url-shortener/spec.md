# url-shortener — Level-2 Spec

## Overview

A lightweight URL shortener web service. Accepts URLs via POST, returns short slugs, resolves them via redirect, and tracks hit statistics.

## Glossary

- **short link**: A mapping from a unique slug (alphanumeric string) to a target URL. Created via POST, resolved via GET.
- **slug**: The unique identifier in a short link. 6 characters, base62-encoded. Generated server-side; never user-chosen.
- **hit**: A recorded access to a short link via the resolve endpoint. Each hit stores timestamp, source IP, and user-agent.
- **link store**: The SQLite database backing the service. Stores links and hits. Single-file, no external database server.

## Scope

### In Scope
- Creating short links from target URLs (POST /links)
- Resolving short links to target URLs (GET /:slug)
- Recording hits on resolution (metadata: timestamp, IP, user-agent)
- Retrieving link statistics (GET /links/:slug/stats)
- Listing all links with pagination (GET /links)
- Input validation (valid URL format, non-empty slug)
- Structured error responses (JSON error body with code and message)
- SQLite persistence with WAL mode

### Out of Scope
- Authentication or authorization (open service)
- Custom slug selection (slugs are server-generated)
- Rate limiting or abuse prevention
- HTTPS termination (runs behind a reverse proxy)
- Link expiration or TTL
- Bulk import/export
- Admin interface or dashboard

## MVP

A lightweight URL shortener web service. Accepts URLs via POST, returns short slugs, resolves them via redirect, and tracks hit statistics.

**FR IDs:** FR-01, FR-02, FR-03, FR-04, FR-05

**Rationale:** All FRs are required for a coherent service. Skipping link creation means no data; skipping resolution means no redirects; skipping hit tracking means no stats; skipping stats endpoint means no visibility; skipping list endpoint means no management.

## Functional Requirements

### FR-01: Create Short Link

Given a valid URL in a JSON POST body, create_link generates a unique 6-character slug, stores the mapping in SQLite, and returns the slug with HTTP 201. Duplicate target URLs get new slugs (no dedup).

### FR-02: Resolve Short Link

Given a GET request to /:slug, resolve_link looks up the slug in SQLite. If found, records a hit (timestamp, source IP, user-agent) and returns an HTTP 307 redirect to the target URL. If not found, returns HTTP 404 with a JSON error body.

### FR-03: Get Link Statistics

Given a GET request to /links/:slug/stats, get_stats returns a JSON object with: slug, target_url, created_at, total_hits, and a list of recent hits (last 10, each with timestamp, ip, user_agent). Returns 404 if slug not found.

### FR-04: List Links

Given a GET request to /links with optional query params offset (default 0) and limit (default 20, max 100), list_links returns a JSON array of link objects (slug, target_url, created_at, total_hits) ordered by created_at descending.

### FR-05: Input Validation

Given any request with invalid JSON body, missing required fields, or malformed URL, the service returns HTTP 422 with a JSON error body containing a machine-readable code and a human-readable message.

## Data

### Inputs
- **HTTP requests**: JSON over HTTP from any client. Validated via Pydantic models.

### Outputs
- **HTTP responses**: JSON (success and error) or HTTP redirect (307).

### Persisted State
- **SQLite database**: links and hits tables. Configurable via --db-path, default ./url-shortener.db. Retention: indefinite.

## Business Rules

- **BR-01**: Slugs are 6 characters, base62 (a-z, A-Z, 0-9). Generated via secrets.token_urlsafe and truncated.
- **BR-02**: Target URLs must be valid HTTP or HTTPS URLs. Reject file://, ftp://, javascript:, etc.
- **BR-03**: Hits are recorded asynchronously — the redirect response is returned immediately; hit recording is best-effort.
- **BR-04**: The list endpoint returns links in reverse chronological order (newest first).
- **BR-05**: All error responses have the shape: {"error": {"code": "STRING", "message": "STRING"}}

## Failure Modes

- **Database locked**: Concurrent writes overwhelm SQLite. Response: HTTP 503 with error code 'database_locked'.
- **Invalid URL**: POST body contains a non-HTTP URL or malformed URL. Response: HTTP 422 with error code 'invalid_url'.
- **Slug collision**: Generated slug already exists (astronomically unlikely with base62^6). Response: Retry generation up to 3 times, then HTTP 500 with error code 'slug_generation_failed'.

## Non-Functional Requirements

- **Performance**: Resolve a short link in under 50ms (P99).
- **Reliability**: WAL mode ensures reads are never blocked by writes.
- **Operability**: Single process, no daemon manager, no config file beyond --db-path.

## Dependencies

- Python 3.12+
- FastAPI (HTTP framework)
- Pydantic v2 (request/response models)
- uvicorn (ASGI server)
- SQLite (bundled with Python)

## Acceptance Criteria

- `AC-01`: Given a POST to /links with {"url": "https://example.com"}, the response is HTTP 201 with {"slug": "<6-char>", "url": "https://example.com", "short_url": "http://host/<6-char>"}
- `AC-02`: Given a POST to /links with {"url": "not-a-url"}, the response is HTTP 422 with error code 'invalid_url'
- `AC-03`: Given a GET to /abc123 where abc123 maps to https://example.com, the response is HTTP 307 with Location: https://example.com
- `AC-04`: Given a GET to /nonexistent, the response is HTTP 404 with error code 'not_found'
- `AC-05`: Given a GET to /links/abc123/stats where abc123 has 5 hits, the response contains total_hits=5 and a hits array with up to 10 entries
- `AC-06`: Given 25 links in the database, GET /links returns 20 links (default limit) and GET /links?offset=20 returns the remaining 5
- `AC-07`: Given a POST to /links with {"url": 123}, the response is HTTP 422 with error code 'invalid_url'
- `AC-08`: Given two POSTs with the same target URL, both succeed with different slugs
- `AC-09`: Given GET /links?limit=5, at most 5 links are returned even if more exist
- `AC-10`: After resolving /abc123 once, GET /links/abc123/stats shows total_hits incremented by 1
