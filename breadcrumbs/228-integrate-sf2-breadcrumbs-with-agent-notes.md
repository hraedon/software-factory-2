---
number: "228"
title: "Migrate sf2 breadcrumbs to agent-notes (DB-canonical); retire md files as source of truth"
severity: medium
status: proposed
kind: improvement
author: claude-opus (GR-055 review session)
date: "2026-05-31"
tags: [tooling, breadcrumbs, agent-notes, dev-ergonomics]
related: ["227"]
---

## Problem

sf2's breadcrumbs live as numbered markdown in `breadcrumbs/` and are
**load-bearing for the running pipeline**: `scripts/agent_golden_run.py` and
`scripts/check_class_block_rule.py` read the files directly (the GR launcher's
"Open HIGH/MEDIUM breadcrumbs" preflight). The shared `agent-notes` DB holds
only a **stale one-shot import** of sf2 (project id 4): breadcrumbs 1..195 from
the old breadcrumb-mcp store, no sync. Current files (120, 198–227) are absent,
and the project's `repo_root` is **NULL**, so `agent-notes breadcrumb find
--path /projects/software-factory-2` cannot resolve sf2 at all. The CLI/skills
either fail to resolve sf2 or return stale data; during GR-055 review this
nearly caused a duplicate filing.

Already fixed (agent-notes, `main` @ 07780af): `find`/`query`/`search` no longer
fail **silently** — they emit `{"error","code"}` JSON on stdout (exit 3) instead
of empty output. So the CLI now reports sf2 as unresolved rather than implying
"no breadcrumbs." This breadcrumb is the remaining migration.

## Decision / direction (updated 2026-05-31 per principal)

**DB-canonical. Retire the md files as source of truth.** Maintaining md as the
source while syncing to a store was rejected earlier — *that* sync was itself the
thing that kept drifting (md breadcrumbs routinely going out of date is the
original reason for the MCP→CLI move). So sf2 joins the shared agent-notes store
as a first-class DB project; the md files are retired (kept only as a read-only
export, if at all).

This is the **sf2 instance of the broader agent-notes lifecycle redesign**
(agent-notes `plans/007` — DB-canonical, one-command instantiation, hook-enforced
lifecycle, tier-one on both Claude Code and opencode). Sequence sf2 *after* that
plan's error-contract + instantiation pieces land, so the migration lands onto a
system that can keep it current without manual sync.

> Execute **after the current GR completes**. The launcher rewire (step 3) edits
> live pipeline code — do not touch it during a run.

## Plan — what needs to happen

1. **Final one-time migration of the md corpus into the DB.** Import current
   files (`breadcrumbs/*.md` incl. `resolved/`) into project `sf2`, parsing the
   frontmatter (`number`→identifier, title, severity, status, kind, tags,
   related) + body, generating embeddings, **upserting** by
   `(project_id, identifier)`. First clear the stale 1..195 legacy rows so the DB
   reflects reality (check for `links`/`change_log` rows referencing them). Uses
   the files→DB importer built in agent-notes `plans/007`.
2. **Set `repo_root` = `/projects/software-factory-2`** so `--path` and the
   skills resolve sf2.
3. **Rewire the launcher to read breadcrumbs from agent-notes.** Point
   `agent_golden_run.py`'s preflight and `check_class_block_rule.py` at the
   `agent-notes` CLI/lib (open breadcrumbs by severity) instead of globbing
   `breadcrumbs/*.md`.
4. **Retire the md files.** After 1–3 verify, stop treating `breadcrumbs/*.md` as
   the source of truth; filing henceforth goes through agent-notes (CLI/skills),
   with the lifecycle enforced by the `plans/007` hooks. Optionally keep a
   generated read-only export for git-grep convenience.
5. **Verify:** launcher preflight produces the same open-breadcrumb list from the
   DB as the files did; counts reconcile; `/find-breadcrumb` on sf2 returns
   current data.

## Hazard / watch-item

Steps 1–3 must land **together** — do not leave a half state where the launcher
still reads files but new breadcrumbs go to the DB (or vice-versa). That
half-migrated state is exactly the current friction. Same null-`repo_root`
applies to projects `substrate` and `v1`; fold them into the `plans/007` rollout.

## Rejected alternatives (for the record)

- **Files canonical + DB read-mirror.** Rejected: it reintroduces the md↔store
  sync that was the original drift problem.
- **File-only, fix skills to degrade.** Rejected: leaves sf2 outside the shared
  system, contrary to making it work *with* agent-notes.
