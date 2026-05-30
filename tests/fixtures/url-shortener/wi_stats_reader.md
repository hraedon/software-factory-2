# Interface Specification: FR 03

## Dependencies

- `interface_ref`: `link_resolver`

## FR-03

Given a GET request to /links/:slug/stats, return a JSON object with slug, target_url, created_at, total_hits, and up to 10 recent hits.

## AC-05

Given a GET to /links/abc123/stats where abc123 has 5 hits, the response contains total_hits=5 and a hits array with up to 10 entries
