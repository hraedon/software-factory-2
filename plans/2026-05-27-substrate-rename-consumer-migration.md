# Consumer migration: regista → regista

**Status:** Phase 2 of the cross-project rename. **Blocked until regista Plan 018 completes** and `v0.4.0` is tagged.
**Scope:** software-factory-2 specifically. See `/projects/RENAME-regista-to-regista.md` for orchestration.
**Regista refs in this repo:** 279 — by far the largest consumer surface. Expect this to take ~60 minutes of focused work.

This is the consumer migration most likely to surface real problems. sf2 is regista's primary application; the coupling is deep. Read this whole plan before starting.

---

## Pre-flight

- [ ] Regista has tagged `v0.4.0` with the rename complete.
- [ ] Tests pass on current main: `pytest -q`. Capture the test count as a baseline.
- [ ] Fresh branch: `git checkout -b rename/regista-to-regista`.
- [ ] Any locally-running sf2 daemons or workers stopped.

## What changes for sf2

Three categories of touch, in order of risk:

### Category A — Runtime imports (highest risk)

sf2 directly imports regista. Every `from regista import …` becomes `from regista import …`. Mechanical, but you'll touch ~50+ files.

### Category B — Env vars

sf2 reads `SUBSTRATE_DSN`, `SUBSTRATE_HMAC_KEY_*`, etc. All become `REGISTA_*`. Any deployment manifest, docker-compose, systemd unit, or `.env.example` needs updating.

### Category C — Documentation, plans, AGENTS.md

279 refs include many doc references. Most sed-clean; some need framing review.

## Steps

### 1. Inventory and categorize

```bash
grep -rln '\bsubstrate\b\|\bSUBSTRATE\b\|\bSubstrate\b' \
  --include='*.py' --include='*.md' --include='*.toml' --include='*.yaml' --include='*.json' --include='*.sh' --include='Dockerfile*' \
  . \
  | grep -v -E 'reflections/|\.venv/|\.git/|node_modules/|dist/|\.claude/worktrees/'
```

Split the resulting list mentally into Categories A / B / C above. The Python sources will dominate.

### 2. Update pyproject and lockfiles

```bash
grep -n 'regista' pyproject.toml uv.lock requirements*.txt 2>/dev/null
```

Change dependency declarations: `regista >= …` → `regista >= 0.4.0`. Refresh the lockfile: `uv lock` (or `pip-compile`, whatever sf2 uses).

### 3. Run the sed pass

```bash
LIVE=$(grep -rln '\bsubstrate\b\|\bSUBSTRATE\b\|\bSubstrate\b' \
  --include='*.py' --include='*.md' --include='*.toml' --include='*.yaml' --include='*.json' --include='*.sh' \
  . \
  | grep -v -E 'reflections/|\.venv/|\.git/|node_modules/|dist/|\.claude/worktrees/|plans/phase[1-5]-|plans/gr006|plans/rfc023')

sed -i \
  -e 's/\bsubstrate\b/regista/g' \
  -e 's/\bSUBSTRATE\b/REGISTA/g' \
  -e 's/\bSubstrate\b/Regista/g' \
  $LIVE
```

Excluded plan files (`phase[1-5]-`, `gr006*`, `rfc023*`) are the early-phase historical plans. The 2026-05-24 phase 6 plan is live and the sed will catch it.

### 4. Verify no `regista` strings remain in code

```bash
grep -rn 'regista\|REGISTA\|Regista' \
  --include='*.py' --include='*.toml' --include='*.yaml' \
  src/ tests/ pyproject.toml \
  | grep -v -E '\.venv/|\.git/|node_modules/'
```

Should be 0. Any hits are either misses to fix or intentional historical references.

### 5. Run the test suite

```bash
.venv/bin/pytest -q 2>&1 | tail -20
```

Expected: substantially the same test count as the pre-flight baseline. Failures will most often come from:

- **String assertions:** `assert "regista" in error_message` — fix expected strings.
- **Mock import paths:** `mock.patch('regista.X')` — change to `regista.X`.
- **Fixture configurations:** YAML/JSON fixtures that name "regista" as a key — those are data, not code; sed already touched them.
- **Migration tests:** if sf2 has integration tests that run regista migrations, ensure migration 029 (regista's column rename) is applied in the test setup.

Iterate until green.

### 6. Update deployment artifacts

Check these specifically:

- `Dockerfile*` — `ENV SUBSTRATE_DSN=…` lines
- `docker-compose*.yml` — env blocks
- `deploy/` directory — systemd units, k8s manifests, helm values
- `.env.example` or equivalent template
- CI workflow files in `.github/workflows/` — env vars and secret names

For each, rename `SUBSTRATE_*` to `REGISTA_*`. If GitHub Actions secrets are named `SUBSTRATE_*`, those need renaming in GitHub Settings → Secrets too (not in code).

### 7. Hand-review key docs

After sed, read these:

- `AGENTS.md` — sf2's agent orientation. Regista references should now read sensibly as regista.
- `README.md` — positioning.
- `plans/2026-05-24-phase6-second-domain-and-decomposer-b.md` — the live phase 6 plan.
- Any architecture diagram (ASCII or otherwise) that names regista as a component.

### 8. Commit

```bash
git add -A
git commit -m "rename: regista → regista (sf2 consumer migration)"
git push -u origin rename/regista-to-regista
```

Single atomic commit. The diff will be large (200+ files); review by category (imports, env, docs) rather than file-by-file.

## Exit criteria

- [ ] `grep -rn 'regista\|REGISTA\|Regista' --include='*.py' --include='*.toml' src/ tests/ pyproject.toml` returns 0 hits.
- [ ] Pre-flight test count matches post-rename test count, both green.
- [ ] Deployment artifacts updated (Dockerfile, compose, k8s, systemd, .env).
- [ ] GitHub Actions secrets renamed if any were `SUBSTRATE_*`.
- [ ] PR merged.
- [ ] One live sf2 worker started against `REGISTA_DSN` to confirm runtime works end-to-end.

## Intentionally not touched

- `reflections/*.md` — historical
- `plans/phase[1-5]-*.md`, `plans/gr006*.md`, `plans/phase2-close*.md`, `plans/phase3-exit*.md`, `plans/phase4-implementation.md`, `plans/phase5-exit*.md`, `plans/rfc023-phaseb-contract.md` — early-phase historical plans
- Any `.claude/worktrees/` — stale agent worktrees

## Rollback

`git revert <merge-commit>` restores pre-rename source.

The bigger concern: if a worker has been running against `REGISTA_DSN`, its written events have `regista` as the source string. Reverting the source code does not revert events written to the DB. This is fine — the DB just has both names appearing in `actor_metadata` or similar. No functional breakage.
