---
number: "140"
title: No standard invocation process for agent-mediated factory runs
severity: high
status: proposed
kind: design
author: agent
date: "2026-05-14"
tags: [process, runner, gate, telemetry, agent-safety, golden-run]
related: [139", "027", "055", "062", "106"]
---

## Summary

There is no documented protocol for how an AI agent (e.g., OpenCode, GLM, Claude Code) should safely execute a software-factory golden run on behalf of the principal. The absence of this protocol led to three concrete failures during GR-026 (GLM-attempted):

1. **Context pollution:** The agent launched runner/gate/scheduler from the factory repo directory (`/projects/software-factory-2`). Every opencode subprocess invocation was associated with that directory, polluting `~/.local/share/opencode/opencode.db` with hundreds of junk sessions.

2. **Unbounded budget burn:** The agent did not recognize the infinite retry loop (BC-139) and allowed it to consume 340+ model invocations before manual kill.

3. **Data loss during cleanup:** When asked to clean junk sessions, the agent used a broad deletion that wiped the principal's working session, destroying its conversation history.

## Root cause

The factory has excellent documentation for *human* execution (AGENTS.md § "Golden runs"), but nothing for *agent* execution. Agents do not have the same safety instincts as humans: they don't notice log files growing, they don't recognize exponential attempt counts as suspicious, and they treat databases as disposable state stores.

## Proposed standard process

A documented `AGENT_RUNBOOK.md` or AGENTS.md appendix should specify:

### 1. Workspace isolation
- Agent must `cd /tmp` or a dedicated scratch directory before launching any factory process.
- Never launch from the project repo root. Subprocess channels inherit the parent's cwd and associate sessions with it.

### 2. Pre-flight checklist
- Verify the config YAML passes schema validation.
- Check `breadcrumbs/README.md` for **critical** and **high** open items that could block the run.
- Confirm `attempt_threshold` is set to a sane value (≤3).
- Verify workspace root is outside the project directory and will be cleaned up post-run.

### 3. Monitoring guardrails
- Agent must tail runner/gate logs every N seconds and look for:
  - `claim_near_budget` warnings
  - `attempt_number` exceeding `attempt_threshold`
  - Any work item cycling `new → in_progress → new` more than 3×
- If any guardrail trips, the agent must **pause and ask the principal** before continuing.

### 4. Cleanup protocol
- Agent must not touch `~/.local/share/opencode/opencode.db` or any other application state store.
- Workspace cleanup is `rm -rf /tmp/sf2-golden-NNN` only.
- Log cleanup is `rm /tmp/grNNN-*.log` only.
- If the principal asks for DB cleanup, the agent must refuse and suggest manual steps instead.

### 5. Post-run artifacts
- Agent must commit the config YAML, any new breadcrumbs, and a worklog entry before considering the run complete.
- Telemetry output must be captured and committed as a run log.

## Blast radius

Affects every future golden run executed by an agent. Without this protocol, any agent-mediated run risks the same three failure modes. The factory pipeline is not self-guarding enough to compensate for an agent's lack of situational awareness.

## Related work

- BC-106 (`make golden-run` lacks process supervision) — partially addresses run orchestration, but not agent-specific safety.
- BC-139 (infinite retry loop) — the proximate cause of the GR-026 budget burn; would have been caught by monitoring guardrails.
- BC-027 (escalation routing), BC-055 (stage contracts), BC-062 (resume-on-gate-fail) — all related to runner/gate safety but assume a human operator.
