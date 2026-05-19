"""Phase-specific default constants for FactoryConfig.

These module-level constants are intentionally kept separate from the
FactoryConfig dataclass so that the schema (what fields exist) and the
defaults (what values they should hold) live in different places.  Adding a
new phase or changing a model string only requires editing this file, not the
dataclass definition.
"""

from __future__ import annotations

from factory.config import RoleConfig, StageHandoff
from factory.constants import (
    CHANNEL_CLAUDE_CODE,
    CHANNEL_CODE,
    CHANNEL_OPENCODE,
    CUSTOM_FIELD_IMPLEMENTATION_REF,
    CUSTOM_FIELD_INTEGRATION_REF,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_REVIEW_REF,
    CUSTOM_FIELD_TEST_SUITE_REF,
    LINK_TYPE_DERIVED_FROM,
    LINK_TYPE_IMPLEMENTS,
    LINK_TYPE_INTEGRATES,
    LINK_TYPE_JUDGES,
    LINK_TYPE_REVIEWS,
    LINK_TYPE_TESTED_BY,
    LINK_TYPE_VERIFIED_BY,
    ROLE_CROSS_FAMILY_REVIEWER,
    ROLE_FRONTIER_JUDGE,
    ROLE_IMPLEMENTER,
    ROLE_INTEGRATOR,
    ROLE_INTERFACE_ARCHITECT,
    ROLE_MECHANICAL_GATE,
    ROLE_OUTCOME_VERIFIER,
    ROLE_TEST_AUTHOR,
    STATE_LOCKED,
    WORK_ITEM_TYPE_IMPLEMENTATION,
    WORK_ITEM_TYPE_INTEGRATION,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
    WORK_ITEM_TYPE_JURY,
    WORK_ITEM_TYPE_OUTCOME_VERIFICATION,
    WORK_ITEM_TYPE_REVIEW,
    WORK_ITEM_TYPE_TEST_SUITE,
)

# ---------------------------------------------------------------------------
# Phase 2
# ---------------------------------------------------------------------------

PHASE2_WORKER_ROLES: tuple[str, ...] = (
    ROLE_INTERFACE_ARCHITECT,
    ROLE_TEST_AUTHOR,
    ROLE_IMPLEMENTER,
)
PHASE2_TYPE_TO_ROLE: tuple[tuple[str, str], ...] = (
    (WORK_ITEM_TYPE_INTERFACE_SPEC, ROLE_INTERFACE_ARCHITECT),
    (WORK_ITEM_TYPE_TEST_SUITE, ROLE_TEST_AUTHOR),
    (WORK_ITEM_TYPE_IMPLEMENTATION, ROLE_IMPLEMENTER),
)
PHASE2_ROLES: tuple[RoleConfig, ...] = (
    RoleConfig(role=ROLE_INTERFACE_ARCHITECT, channel=CHANNEL_CLAUDE_CODE),
    RoleConfig(role=ROLE_TEST_AUTHOR, channel=CHANNEL_CLAUDE_CODE),
    RoleConfig(role=ROLE_IMPLEMENTER, channel=CHANNEL_CLAUDE_CODE),
    RoleConfig(role=ROLE_MECHANICAL_GATE, channel=CHANNEL_CODE),
)

# ---------------------------------------------------------------------------
# Phase 3  (same worker roles / type mapping as phase 2, different models)
# ---------------------------------------------------------------------------

PHASE3_WORKER_ROLES: tuple[str, ...] = PHASE2_WORKER_ROLES
PHASE3_TYPE_TO_ROLE: tuple[tuple[str, str], ...] = PHASE2_TYPE_TO_ROLE
PHASE3_ROLES: tuple[RoleConfig, ...] = (
    RoleConfig(
        role=ROLE_INTERFACE_ARCHITECT,
        channel=CHANNEL_OPENCODE,
        model="fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo",
    ),
    RoleConfig(
        role=ROLE_TEST_AUTHOR,
        channel=CHANNEL_OPENCODE,
        model="fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo",
    ),
    RoleConfig(
        role=ROLE_IMPLEMENTER,
        channel=CHANNEL_OPENCODE,
        model="fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo",
    ),
    RoleConfig(role=ROLE_MECHANICAL_GATE, channel=CHANNEL_CODE),
)

# ---------------------------------------------------------------------------
# Phase 4
# ---------------------------------------------------------------------------

PHASE4_WORKER_ROLES: tuple[str, ...] = (
    ROLE_INTERFACE_ARCHITECT,
    ROLE_TEST_AUTHOR,
    ROLE_IMPLEMENTER,
    ROLE_CROSS_FAMILY_REVIEWER,
    ROLE_FRONTIER_JUDGE,
)
PHASE4_TYPE_TO_ROLE: tuple[tuple[str, str], ...] = (
    (WORK_ITEM_TYPE_INTERFACE_SPEC, ROLE_INTERFACE_ARCHITECT),
    (WORK_ITEM_TYPE_TEST_SUITE, ROLE_TEST_AUTHOR),
    (WORK_ITEM_TYPE_IMPLEMENTATION, ROLE_IMPLEMENTER),
    (WORK_ITEM_TYPE_REVIEW, ROLE_CROSS_FAMILY_REVIEWER),
    (WORK_ITEM_TYPE_JURY, ROLE_FRONTIER_JUDGE),
)
PHASE4_ROLES: tuple[RoleConfig, ...] = (
    RoleConfig(
        role=ROLE_INTERFACE_ARCHITECT,
        channel=CHANNEL_OPENCODE,
        model="fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo",
    ),
    RoleConfig(
        role=ROLE_TEST_AUTHOR,
        channel=CHANNEL_OPENCODE,
        model="fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo",
    ),
    RoleConfig(
        role=ROLE_IMPLEMENTER,
        channel=CHANNEL_OPENCODE,
        model="fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo",
    ),
    RoleConfig(
        role=ROLE_CROSS_FAMILY_REVIEWER,
        channel=CHANNEL_OPENCODE,
        model="fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo",
    ),
    RoleConfig(role=ROLE_FRONTIER_JUDGE, channel=CHANNEL_CLAUDE_CODE),
    RoleConfig(role=ROLE_MECHANICAL_GATE, channel=CHANNEL_CODE),
)
PHASE4_STAGE_TOPOLOGY: tuple[StageHandoff, ...] = (
    StageHandoff(
        source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
        source_state=STATE_LOCKED,
        target_type=WORK_ITEM_TYPE_TEST_SUITE,
        link_type=LINK_TYPE_DERIVED_FROM,
        ref_field=CUSTOM_FIELD_INTERFACE_REF,
    ),
    StageHandoff(
        source_type=WORK_ITEM_TYPE_TEST_SUITE,
        source_state=STATE_LOCKED,
        target_type=WORK_ITEM_TYPE_IMPLEMENTATION,
        link_type=LINK_TYPE_TESTED_BY,
        additional_links=(LINK_TYPE_IMPLEMENTS,),
        ref_field=CUSTOM_FIELD_TEST_SUITE_REF,
        propagate_fields=(CUSTOM_FIELD_INTERFACE_REF,),
    ),
    StageHandoff(
        source_type=WORK_ITEM_TYPE_IMPLEMENTATION,
        source_state=STATE_LOCKED,
        target_type=WORK_ITEM_TYPE_REVIEW,
        link_type=LINK_TYPE_REVIEWS,
        ref_field=CUSTOM_FIELD_IMPLEMENTATION_REF,
        propagate_fields=(
            CUSTOM_FIELD_INTERFACE_REF,
            CUSTOM_FIELD_TEST_SUITE_REF,
        ),
    ),
    StageHandoff(
        source_type=WORK_ITEM_TYPE_REVIEW,
        source_state=STATE_LOCKED,
        target_type=WORK_ITEM_TYPE_JURY,
        link_type=LINK_TYPE_JUDGES,
        ref_field=CUSTOM_FIELD_REVIEW_REF,
    ),
)

# ---------------------------------------------------------------------------
# Phase 5
# ---------------------------------------------------------------------------

PHASE5_WORKER_ROLES: tuple[str, ...] = (
    ROLE_INTERFACE_ARCHITECT,
    ROLE_TEST_AUTHOR,
    ROLE_IMPLEMENTER,
    ROLE_CROSS_FAMILY_REVIEWER,
    ROLE_FRONTIER_JUDGE,
    ROLE_INTEGRATOR,
    ROLE_OUTCOME_VERIFIER,
)
PHASE5_TYPE_TO_ROLE: tuple[tuple[str, str], ...] = (
    (WORK_ITEM_TYPE_INTERFACE_SPEC, ROLE_INTERFACE_ARCHITECT),
    (WORK_ITEM_TYPE_TEST_SUITE, ROLE_TEST_AUTHOR),
    (WORK_ITEM_TYPE_IMPLEMENTATION, ROLE_IMPLEMENTER),
    (WORK_ITEM_TYPE_REVIEW, ROLE_CROSS_FAMILY_REVIEWER),
    (WORK_ITEM_TYPE_JURY, ROLE_FRONTIER_JUDGE),
    (WORK_ITEM_TYPE_INTEGRATION, ROLE_INTEGRATOR),
    (WORK_ITEM_TYPE_OUTCOME_VERIFICATION, ROLE_OUTCOME_VERIFIER),
)
PHASE5_ROLES: tuple[RoleConfig, ...] = (
    RoleConfig(
        role=ROLE_INTERFACE_ARCHITECT,
        channel=CHANNEL_OPENCODE,
        model="fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo",
    ),
    RoleConfig(
        role=ROLE_TEST_AUTHOR,
        channel=CHANNEL_OPENCODE,
        model="fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo",
    ),
    RoleConfig(
        role=ROLE_IMPLEMENTER,
        channel=CHANNEL_OPENCODE,
        model="fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo",
    ),
    RoleConfig(
        role=ROLE_CROSS_FAMILY_REVIEWER,
        channel=CHANNEL_OPENCODE,
        model="ollama-cloud/deepseek-v4-pro",
    ),
    RoleConfig(role=ROLE_FRONTIER_JUDGE, channel=CHANNEL_CLAUDE_CODE),
    RoleConfig(
        role=ROLE_INTEGRATOR,
        channel=CHANNEL_OPENCODE,
        model="fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo",
    ),
    RoleConfig(
        role=ROLE_OUTCOME_VERIFIER,
        channel=CHANNEL_OPENCODE,
        model="fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo",
    ),
    RoleConfig(role=ROLE_MECHANICAL_GATE, channel=CHANNEL_CODE),
)
PHASE5_STAGE_TOPOLOGY: tuple[StageHandoff, ...] = (
    StageHandoff(
        source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
        source_state=STATE_LOCKED,
        target_type=WORK_ITEM_TYPE_TEST_SUITE,
        link_type=LINK_TYPE_DERIVED_FROM,
        ref_field=CUSTOM_FIELD_INTERFACE_REF,
    ),
    StageHandoff(
        source_type=WORK_ITEM_TYPE_TEST_SUITE,
        source_state=STATE_LOCKED,
        target_type=WORK_ITEM_TYPE_IMPLEMENTATION,
        link_type=LINK_TYPE_TESTED_BY,
        additional_links=(LINK_TYPE_IMPLEMENTS,),
        ref_field=CUSTOM_FIELD_TEST_SUITE_REF,
        propagate_fields=(CUSTOM_FIELD_INTERFACE_REF,),
    ),
    StageHandoff(
        source_type=WORK_ITEM_TYPE_IMPLEMENTATION,
        source_state=STATE_LOCKED,
        target_type=WORK_ITEM_TYPE_REVIEW,
        link_type=LINK_TYPE_REVIEWS,
        ref_field=CUSTOM_FIELD_IMPLEMENTATION_REF,
        propagate_fields=(
            CUSTOM_FIELD_INTERFACE_REF,
            CUSTOM_FIELD_TEST_SUITE_REF,
        ),
    ),
    StageHandoff(
        source_type=WORK_ITEM_TYPE_REVIEW,
        source_state=STATE_LOCKED,
        target_type=WORK_ITEM_TYPE_JURY,
        link_type=LINK_TYPE_JUDGES,
        ref_field=CUSTOM_FIELD_REVIEW_REF,
    ),
    StageHandoff(
        source_type=WORK_ITEM_TYPE_JURY,
        source_state=STATE_LOCKED,
        target_type=WORK_ITEM_TYPE_INTEGRATION,
        link_type=LINK_TYPE_INTEGRATES,
        ref_field=CUSTOM_FIELD_INTEGRATION_REF,
    ),
    StageHandoff(
        source_type=WORK_ITEM_TYPE_INTEGRATION,
        source_state=STATE_LOCKED,
        target_type=WORK_ITEM_TYPE_OUTCOME_VERIFICATION,
        link_type=LINK_TYPE_VERIFIED_BY,
        ref_field=CUSTOM_FIELD_INTEGRATION_REF,
    ),
)
