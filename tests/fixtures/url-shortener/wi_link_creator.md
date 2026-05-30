# Interface Specification: FR 01

## Dependencies

None.

## FR-01

Given a valid URL in a JSON POST body, generate a unique 6-character base62 slug, store the mapping in SQLite, and return the slug with HTTP 201.

## AC-01

Given a POST to /links with {"url": "https://example.com"}, the response is HTTP 201 with {"slug": "<6-char>", "url": "https://example.com", "short_url": "http://host/<6-char>"}

## AC-02

Given a POST to /links with {"url": "not-a-url"}, the response is HTTP 422 with error code 'invalid_url'

## AC-08

Given two POSTs with the same target URL, both succeed with different slugs
