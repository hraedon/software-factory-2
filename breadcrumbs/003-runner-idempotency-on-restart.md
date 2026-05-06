---
number: "003"
title: "Runner idempotency on restart"
severity: high
status: implemented
kind: design
author: opencode
date: "2026-05-06"
tags: [runner, phase-1, idempotency, spec-amendment]
related: ["002"]
---

## Decision Required

When the runner crashes after a channel produces an artifact but before the corresponding `submit` transition is written to substrate, what happens on restart?

This is a load-bearing correctness question for the runner. Without a decision, Phase 1 code will diverge across implementations.

## Chosen resolution

**Re-claim detects existing artifact via manifest hash and resumes; never overwrites.**

## Five corrections from review

### 1. Attempt-number / directory mapping (was internally inconsistent)

**Original (wrong):** The mechanics had attempt 2's claim reusing directory `1/`, but the spec amendment asserted "each substrate attempt_number maps to exactly one attempt directory." These contradicted each other.

**Corrected:** Option (a) — resume reuses the directory from the earlier attempt. The invariant is rewritten:

> "Each attempt directory maps to the substrate attempt that produced it; later attempts may resume from earlier directories."

Attempt 2's claim event is substrate state. The filesystem state (artifact in `attempt-001/`) is substrate state from attempt 1. They are linked by the manifest, not by directory naming.

This preserves the audit trail (artifact in `attempt-001/` is exactly what attempt 1's channel invocation produced) without burning directories or re-invoking.

### 2. Starting state on restart (was wrong)

**Original (wrong):** "W is in `new` (no submit was recorded)."

**Corrected:** W is in `in_progress`. The original `claim` transition moved it from `new → in_progress`. The crash means the `submit` was never written. W stays in `in_progress` until:
- The claim's TTL expires and substrate's `sweep_expired_claims` (per BC-006) moves it back to `new`, OR
- An operator force-expires the claim.

This is a real wall-clock delay (default TTL in substrate is claim-configurable, default 5 minutes). The runner cannot restart and immediately reclaim W. It must either:
- Wait out the TTL (normal ops), or
- Be restarted with a force-expire flag (operator intervention).

This delay must be stated in the spec amendment, not skipped.

### 3. `find_valid_attempt` signature (was wrong)

**Original (wrong):** `find_valid_attempt(work_item_id, attempt_number) -> Optional[ArtifactManifest]`

**Corrected:** `find_resumable_artifact(work_item_id) -> Optional[(attempt_number, ArtifactManifest)]`

On re-claim, the runner does not know which prior attempt might have left a valid artifact. It scans all prior attempt directories and picks the highest-numbered one with a valid manifest. The function name reflects the intent: finding a resumable artifact, not validating a specific attempt.

**Multi-crash behavior resolved:**

| Scenario | 1/ manifest | 2/ manifest | 3/ reclaiming | Action |
|----------|------------|------------|---------------|--------|
| 1 valid, 2 partial | valid | missing/invalid | attempt 3 | Scans all; 1/ wins (highest valid). Resumes from 1/. |
| 1 valid, 2 valid, 3 crashed | valid | valid | attempt 4 | Highest valid is 2/. Resumes from 2/. 1/ is orphaned audit material. |
| 1 corrupt, 2 valid, 3 crashed | INVALID | valid | attempt 4 | Highest valid is 2/. Resumes from 2/. 1/ is quarantined. |

The rule is simple: **pick the highest-numbered attempt directory with a valid manifest; quarantine everything else.**

### 4. Actor metadata on resumed submit (was missing)

**Original (missing):** The resumer's actor_id and channel would be recorded as the producer of the artifact.

**Corrected:** The `submit` event's actor metadata must carry the **original attempt's** actor metadata, read from the manifest. The manifest (written at the time of channel invocation) records: `actor_id`, `channel`, `channel_family`, `model`, `attempt_number`. On a resume, the runner copies these fields into the `submit` event verbatim.

This preserves per-(role, channel) pass-rate telemetry (spec §7). A Claude-produced artifact is credited to Claude, not to whichever process happened to restart the runner.

### 5. "Discard" contradicted audit-trail argument (was contradictory)

**Original (contradictory):** The same paragraph ruling out overwriting ("principal may need to inspect first-attempt output") then said corrupt attempts get deleted.

**Corrected:** Corrupt attempts are **quarantined**, not deleted. Rename `attempt-001/` to `.corrupt/attempt-001-20260506-143022/` (timestamped). The forensic trail survives. The directory is excluded from future scans (prefix `.corrupt/`). Cheap, removes the contradiction.

## Detailed mechanics (corrected)

### Path naming reconciliation

Spec §9.11 uses the template `.factory/work/<work_item_id>/<attempt_id>/<artifact_name>`.

This breadcrumb uses `attempt-NNNN` for directory names (zero-padded, 4 digits). `attempt_id` in the spec and `attempt_number` from substrate are the same thing, zero-padded for filesystem sorting. No ambiguity.

**Path examples:**
- `.factory/work/wi-7f3a/attempt-0001/artifact.pyi`
- `.factory/work/wi-7f3a/attempt-0001/manifest.json`
- `.factory/work/wi-7f3a/.corrupt/attempt-0001-20260506-143022/` (quarantined)

### Happy path (no crash)

1. Runner claims work-item W (substrate attempt 1).
2. Runner derives context, invokes channel adapter.
3. Channel adapter writes artifact to `.factory/work/W/attempt-0001/artifact.pyi`.
4. Runner computes manifest hash, writes `.factory/work/W/attempt-0001/manifest.json` (atomically via temp+rename).
5. Runner calls `submit` on substrate; work-item transitions `in_progress → gating`.
   - `submit` event actor metadata: `actor_id`, `channel`, `channel_family`, `model` from manifest.
6. Mechanical gate claims W, evaluates artifact, transitions `gating → locked` (or `new`).

### Crash after step 3, before step 4 or 5

On restart:

1. Runner polls substrate for claimable work-items in `new` or after TTL expiry.
2. W may still be in `in_progress` (claim not expired). Runner waits or operator force-expires.
3. Once W returns to `new`, runner claims W again (substrate attempt 2).
4. Before invoking channel, runner calls `find_resumable_artifact(W)`.
5. `find_resumable_artifact` scans `.factory/work/W/attempt-*/manifest.json`, returns the highest-numbered valid manifest.
6. **If valid manifest found:** Runner reads the artifact path from manifest. Skips channel invocation. Proceeds directly to `submit` with the existing artifact path and manifest hash. `submit` event carries original attempt's actor metadata from manifest.
7. **If no valid manifest found:** All found directories are quarantined to `.corrupt/`. Runner invokes channel fresh for attempt 2.

### Multi-crash scenario (attempt 1 valid, attempt 2 partial, attempt 3 claiming)

1. Attempt 1: wrote artifact + manifest, crashed before submit. Directory `attempt-0001/` valid.
2. Attempt 2: crashed during write (partial file, no manifest). Directory `attempt-0002/` invalid.
3. Runner restarts, claims attempt 3.
4. `find_resumable_artifact(W)` scans: `attempt-0001/` valid, `attempt-0002/` invalid.
5. Returns `(1, manifest_0001)`. Runner resumes from `attempt-0001/`.
6. Concurrently, `attempt-0002/` is quarantined to `.corrupt/attempt-0002-20260506-143022/`.
7. Runner submits with original actor metadata (attempt 1's channel info).

### Why "never overwrites"

- Overwriting destroys the audit trail. The principal may need to inspect what the channel produced on the first attempt.
- Content-addressed paths (spec §9.11) make overwriting unnecessary.
- Resume from an earlier directory is not overwriting; earlier directories are read-only once written.

### Race condition: what if the channel is still writing?

The manifest is written atomically (rename over temp file). A partial manifest is never observed. Observable states fall into two categories by cause:

**Crash during write** (channel was still running when runner died):
- Manifest absent → no valid manifest → quarantine directory, re-invoke channel.
- This is the expected case: the channel had not yet closed the file and the runner had not yet written the manifest.

**Post-write corruption** (manifest was written but artifact was subsequently damaged):
- Manifest present but hash mismatches artifact on disk → quarantine directory, re-invoke channel.
- Causes: disk corruption, manual tampering, or a competing writer. Not a race condition; a forensic signal.

Only "manifest present + hash matches content" resumes.

### Substrate contract

The runner does NOT rely on substrate for artifact storage. Substrate stores the event log and custom fields (`artifact_path`, `artifact_hash`). The runner stores the bytes. On re-claim, the runner bridges the two by checking: "does the filesystem state for the highest prior attempt match what a valid manifest claims?"

## Spec amendment (corrected)

Add §9.12 to `spec.md`:

> ### 9.12 Runner idempotency on restart
> The runner must be safe to restart at any point. On re-claiming a work-item, the runner scans all prior attempt directories for a valid manifest. If a valid manifest is found (SHA-256 matches artifact on disk), the runner resumes from the highest-numbered valid attempt without re-invoking the channel. The `submit` event carries the original attempt's actor metadata (`channel`, `model`, `family`) from the manifest. If no valid manifest is found, all prior attempt directories are quarantined (renamed to `.corrupt/attempt-NNNN-YYYYmmdd-HHMMSS/`) and the runner invokes the channel fresh. The runner never overwrites an existing attempt directory. Each attempt directory maps to the substrate attempt that produced it; later attempts may resume from earlier directories.
>
> If the work-item is still in `in_progress` because the prior claim's TTL has not expired, the runner must wait for substrate's `sweep_expired_claims` to return it to `new`, or an operator must force-expire the claim. The runner does not force-expire claims automatically.

## Acceptance criteria (corrected)

- [ ] `workspace.py` exposes `find_resumable_artifact(work_item_id) -> Optional[tuple[int, ArtifactManifest]]`.
- [ ] `runner.py` calls `find_resumable_artifact` before channel invocation on every claim.
- [ ] `runner.py` writes original attempt's actor metadata (from manifest) into the `submit` event, not its own process identity.
- [ ] `tests/test_runner_idempotency.py` covers:
  - Crash-before-submit (resumes from prior attempt, submits with original actor metadata).
  - Crash-during-write (quarantines partial attempt, re-invokes channel).
  - Manifest tampering (quarantines corrupted attempt, re-invokes channel).
  - Multi-crash with partial intermediate (resumes from highest valid, quarantines intermediates).
  - Claim still in_progress on restart (runner waits or force-expires per config).
- [ ] `spec.md` updated with §9.12 as corrected above.

## Related

- spec §9.11 (Artifact addressing)
- spec §9.2 (Context derivation)
- substrate dedup semantics (`event_id` uniqueness)
- substrate BC-006 (sweep_expired_claims / heartbeat TTL)
- BC-002 (Runner skeleton complexity risk)
