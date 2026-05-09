# Active Debate

Structured positions on architectural and design questions that are not yet resolved to a breadcrumb or RFC. One file per topic. These are arguments and recommendations, not defects.

When a debate item is resolved (accepted or rejected), it should be:
- Accepted → move to a spec amendment, breadcrumb, or RFC with resolution note
- Rejected → move to `debate/resolved/` with rejection rationale
- Stale → close if no activity for 60 days

## Index

| # | Title | Position | Blocking |
|---|---|---|---|
| 001 | UI/UX validation first pass | Implement playwright-driven behavioral gate before Phase 5 | Phase 5 (first real workload) |
| 002 | Telemetry data quality | Fix event-matching before any fleet integration | Phase 3 (fleet integration) |
| 003 | Channel adapter deduplication | Extract `SubprocessChannel` base class before adding K2/GLM/DeepSeek/Gemini | Phase 3 (fleet integration) |
| 004 | Pipeline checkpoints | Implement checkpoint system before multi-channel runs | Phase 3 (fleet integration) |
| 005 | Test efficacy / mutation testing | Add lightweight mutation-testing gate before jury gates | Phase 4 (jury gates) |
| 006 | Per-project venv isolation | Build per-project venv before real workloads with external deps | Phase 5 (first real workload) |
| 007 | Credential management for Phase 3 multi-channel | Add `CredentialManager` and `credentials.yaml` schema before fleet integration | Phase 3 (fleet integration) |
| 008 | Golden-run fixture representativeness | Run an adversarial multi-module+stateful+UI fixture before declaring Phase 2 done | Phase 2 exit criteria |
| 009 | Event schema evolution | Add optional versioned payload schemas to prevent producer/consumer drift | Phase 3 (fleet integration) |
| 010 | Unbounded event log growth | Define hot/cold retention policy before missions exceed 7 days | Phase 5+ |
