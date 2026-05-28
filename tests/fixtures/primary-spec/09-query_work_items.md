# query_work_items — ADT Validation

## Source
regista spec §5, FR-05b

## Spec excerpt

**FR-05b:** Structured work-item query against `work_items_current` (not the event log). Filter shapes (combinable, AND semantics):

- `workflow_name`, `workflow_version` (the latter optional; absent = any pinned version)
- `work_item_type` (one or many)
- `current_state` (one or many)
- `claimed_by` (actor_id) — work-items currently held by a specific actor
- `claimable_now` (bool) — unclaimed-or-expired AND `not_before <= now()`
- `needs_review` (bool)
- `has_link_type` (link type) — work-items that are the source of a link of given type

Pagination via stable `work_item_id` cursor (ordered ascending); default page size 100, max 1000. The cursor is `work_item_id`-only rather than `(last_event_seq, work_item_id)` so that ordering is fixed regardless of concurrent appends.

Indexes required to satisfy NFR-perf-1: `(workflow_name, workflow_version, current_state)`, `(claimed_by)`, `(needs_review) WHERE needs_review`.

**AC-05b:** A query with multiple filters returns exactly the work-items satisfying all filters. Pagination with the stable `work_item_id` cursor returns subsequent pages with no overlap and no skip, even when work-items matching the filter are concurrently appended-to during the scan.

## Work-item shape
ADT-validation — function whose contract requires defining QueryFilter dataclass, QueryPage return type, QueryParams (filter + cursor + page_size), and the query function signature

## AC IDs
AC-05b
