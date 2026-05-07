# verify_event — Error Taxonomy

## Source
substrate spec §5, FR-15

## Spec excerpt

**FR-15:** Verify actor identity via pluggable verifier before recording any event. Algorithm: HMAC-SHA256 (default verifier).

Key set: per-actor, with status `active` / `deprecated` / `revoked`. Each event carries `key_id`. Hot-reload via mtime polling at default 30s interval.

Behavior:
- Unknown `key_id`: reject; structured log with `actor_id_claim`, `key_id_claim`, `event_id`; signature contents NOT logged.
- Revoked `key_id`: reject (including retroactively, where re-verification occurs).
- Deprecated `key_id`: accept; emit structured warning.

Canonical signing envelope: the bytes signed are RFC 8785 (JCS) canonical JSON serialization of `{event_id, work_item_id, actor_id, transition, payload}`. Lexicographically sorted keys, no whitespace. Server-stamped fields (`timestamp`, `event_seq`, `key_id`-derived metadata) are explicitly NOT in the signed envelope.

The library is the sole sanctioned signer. The public API accepts unsigned event field tuples; the library performs RFC 8785 canonicalization, computes the HMAC, and persists.

`payload_canonical_hash` — SHA-256 of the canonical signing envelope. Stored to enable retroactive verification independent of jsonb round-trip behavior across Postgres versions.

**AC-15:** `verify_event` rejects with structured error for unknown keys (`UNKNOWN_KEY_ID`), revoked keys (`REVOKED_KEY_ID`), and signature mismatches (`SIGNATURE_MISMATCH`). Every rejection carries `actor_id_claim`, `key_id_claim`, `event_id` but never raw signature bytes. Deprecated keys are accepted with a structured warning flag. All three rejection paths are enumerated in an `ErrorCode` enum; no other rejection causes exist.

**AC-26:** Re-verifying a stored event's signature uses the stored `canonical_envelope` bytes, not jsonb re-serialization. A simulated jsonb-formatting change does NOT invalidate previously verified events.

## Work-item shape
error-taxonomy — function whose contract centrally includes an enumerated error set (ErrorCode enum)

## AC IDs
AC-15, AC-26
