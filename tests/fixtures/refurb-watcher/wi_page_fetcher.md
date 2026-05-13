# Interface Specification: Page Fetcher

## Dependencies

- `interface_ref`: `refurb_config`

## AC-01: Fetch Page

A function `fetch_page(url: str, config: RefurbConfig) -> PageResult` must perform an HTTP GET request to `url` and return the response body as a `PageResult` dataclass with:
- `html: str` — the response body
- `status_code: int` — the HTTP status code
- `fetched_at: datetime` — UTC timestamp of when the request completed
- `url: str` — the final URL (after any redirects)

## AC-02: Timeout

The function must enforce a connection timeout of 10 seconds and a read timeout of 30 seconds. If either timeout is exceeded, it must return `FetchError` with `error_type="timeout"`, not raise an exception.

## AC-03: Retry on Transient Failure

A function `fetch_with_retry(url: str, config: RefurbConfig, max_retries: int = 3) -> PageResult | FetchError` must retry on transient failures:
- Status codes 429, 502, 503, 504 are transient — retry after `2 ** attempt` seconds (1s, 2s, 4s)
- Connection timeouts and DNS failures are transient — same retry schedule
- Status codes 4xx other than 429 are permanent — return `FetchError` immediately, no retry
- After `max_retries` exhausted, return `FetchError` with `error_type="retry_exhausted"`

The response from any successful retry is returned as `PageResult`; the caller never sees the intermediate failures.

## AC-04: Rate Limiting

The function must include `config.user_agent` as the User-Agent header. If the server responds with 429 (rate limited), the retry schedule in AC-03 applies. The system must not send more than one request per `config.poll_interval_seconds` to the same host — this is the caller's contract, but `fetch_page` must not bypass it.

## AC-05: Fetch Error Type

`FetchError` must be a dataclass with:
- `url: str`
- `error_type: str` — one of `"timeout"`, `"http_error"`, `"retry_exhausted"`, `"connection"`
- `status_code: int | None` — the last HTTP status code, or None for connection-level errors
- `message: str` — human-readable error description

## AC-06: Empty Response

If the response body is empty (zero bytes, or only whitespace) and the status code is 200, `fetch_page` must return `PageResult` with `html=""` and `status_code=200`. The caller (not the fetcher) decides whether an empty page is an error — the fetcher reports what it got, it does not interpret.

## AC-07: Malformed Response Handling

If the response has a non-200 status code and an empty or non-UTF-8-decodable body, `fetch_page` must return `FetchError` with `error_type="http_error"`, the status code, and `message` describing the error. The function must never raise an exception for any network condition — all failures are returned as `FetchError`.