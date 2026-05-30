# Interface Specification: FR 04

## Dependencies

- `interface_ref`: `link_creator`

## FR-04

Given a GET request to /links with optional offset and limit query params, return a paginated JSON array of link objects ordered by created_at descending.

## AC-06

Given 25 links in the database, GET /links returns 20 links (default limit) and GET /links?offset=20 returns the remaining 5

## AC-09

Given GET /links?limit=5, at most 5 links are returned even if more exist
