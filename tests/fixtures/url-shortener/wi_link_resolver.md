# Interface Specification: FR 02

## Dependencies

- `interface_ref`: `link_creator`

## FR-02

Given a GET request to /:slug, look up the slug in SQLite, record a hit (timestamp, source IP, user-agent), and return an HTTP 307 redirect to the target URL or 404 if not found.

## AC-03

Given a GET to /abc123 where abc123 maps to https://example.com, the response is HTTP 307 with Location: https://example.com

## AC-04

Given a GET to /nonexistent, the response is HTTP 404 with error code 'not_found'

## AC-10

After resolving /abc123 once, GET /links/abc123/stats shows total_hits incremented by 1
