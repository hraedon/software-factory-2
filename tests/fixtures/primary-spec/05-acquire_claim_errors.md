# acquire_claim — Error Taxonomy

## Source
regista spec §5, FR-06, §8 error table

## Spec excerpt

**FR-06:** Acquire a claim on a work-item. Respects `not_before` (rejects if in future); rejects if work-item is already claimed and unexpired (Postgres row lock — first wins, second receives "claim contested" rejection, not an error). Auto-steal expired claims on next acquire; increment `attempt_number`; preserve prior claim history in event log.

**§8 Error table:**
| Failure | Trigger | Response |
|---|---|---|
| Concurrent claim contention | Two acquires on same work-item | First wins atomically; second receives "claim contested" | Caller sees rejection; not logged as error |

**AC-06:** Given a work-item with `not_before` in the future, claim acquisition rejects. Given an unclaimed work-item, two concurrent acquires result in exactly one success and one "claim contested" rejection. Given an expired claim, auto-steal increments attempt_number.

## Work-item shape
error-taxonomy — function whose contract includes these enumerated error conditions:
- `CLAIM_CONTESTED` — concurrent acquire, another actor holds the claim
- `NOT_BEFORE_FUTURE` — work-item's `not_before` timestamp is still in the future
- `STALE_HEARTBEAT` — heartbeat from agent who lost the lease

## AC IDs
AC-06
