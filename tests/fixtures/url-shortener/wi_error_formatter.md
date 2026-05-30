# Interface Specification: FR 05

## Dependencies

None.

## FR-05

Given any request with invalid JSON body, missing required fields, or malformed URL, return HTTP 422 with a structured JSON error body containing a machine-readable code and human-readable message.

## AC-07

Given a POST to /links with {"url": 123}, the response is HTTP 422 with error code 'invalid_url'
