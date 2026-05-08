# RS-02: Chunked Processor — Routing Stress (pytest)

**Purpose:** A function that splits a list into fixed-size chunks and processes
each chunk through a callback. The boundary conditions (empty list, last chunk
shorter than size, chunk_size equal to list length) are easy to get wrong.

## Acceptance Criteria

### AC-RS2: chunked_process handles all boundary cases correctly

`chunked_process(items: Sequence[T], chunk_size: int, callback: Callable[[list[T]], R]) -> list[R]`

- If `items` is empty, return an empty list (do NOT call the callback).
- If `chunk_size <= 0`, raise `ValueError` with message `"chunk_size must be positive"`.
- Split `items` into chunks of exactly `chunk_size`, except the last chunk may
  be shorter if the list length is not a multiple of `chunk_size`.
- Call `callback` once per chunk, in order, collecting results.
- The last chunk must contain the remaining elements even if shorter than
  `chunk_size`. A list of 5 items with `chunk_size=3` produces chunks of
  sizes `[3, 2]`, NOT `[3]` (dropping the remainder).
- If `chunk_size == len(items)`, produce exactly one chunk containing all items.

The function is generic over `T` (item type) and `R` (callback return type).

**Work-item shape:** pure-interface with boundary-case stress. The contract's
AC enumerates exact expected behavior for empty, exact-multiple, non-multiple,
and single-chunk cases.

## Glossary

- **Chunk** — a contiguous sublist of `items` with length `<= chunk_size`.
- **Callback** — a pure function called once per chunk.
- **Boundary case** — an input where the list length and `chunk_size` have a
  specific arithmetic relationship (empty, exact multiple, off-by-one, equal).
