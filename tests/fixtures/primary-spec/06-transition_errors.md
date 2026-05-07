# transition — Error Taxonomy

## Source
substrate spec §5, FR-11, FR-12, §8 error table

## Spec excerpt

**FR-11:** Validate state transitions against the work-item's pinned workflow version (not the latest); reject invalid transitions.

**FR-12:** Validate role-gating per transition against the work-item's pinned workflow version; reject if actor's declared role isn't permitted for that transition. If actor has registered roles (FR-24), the declared role must also be in the actor's registered set.

**§8 Error table:**
| Failure | Trigger | Response |
|---|---|---|
| Invalid transition | Transition not declared in workflow for source state | Reject |
| Role-gating violation | Actor's role not permitted for transition | Reject |
| Invalid YAML at registration | Workflow file fails YAML parse | Reject; error includes line number |
| Schema-invalid workflow | Workflow file fails JSON Schema | Reject; error includes JSON pointer |
| Semantically broken workflow | Reachability / terminal / role-binding check fails | Reject |

The work-item's pinned workflow version is authoritative for transition validation, not the latest registered version.

**AC-11:** A transition not in the work-item's pinned workflow version is rejected, even if it exists in a newer registered version.

**AC-12:** A transition by an actor whose role is not in the workflow's role-gating list for that transition is rejected.

## Work-item shape
error-taxonomy — function whose contract includes these enumerated error conditions:
- `INVALID_TRANSITION` — transition not in pinned workflow for current state
- `ROLE_NOT_PERMITTED` — actor's role not permitted for this transition
- `WORKFLOW_NOT_REGISTERED` — referenced workflow not registered
- `TYPE_NOT_DECLARED` — work-item-type not in registered workflow

## AC IDs
AC-11, AC-12
