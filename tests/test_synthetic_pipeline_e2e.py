"""Synthetic end-to-end pipeline tests.

Covers the full claim → invoke → gate → route → schedule cycle deterministically,
with no PostgreSQL dependency and no live model API calls.

What this covers
----------------
- Happy path (gate pass): interface_spec work item is claimed, a mock channel
  returns a valid artifact, the gate evaluates it, the work item advances to
  ``locked``, and the scheduler creates the downstream ``test_suite`` work item.
- Failure path (gate fail): interface_spec work item is claimed, the mock channel
  returns an artifact that cannot satisfy the gate (empty file), the gate fails,
  the work item routes back to ``new`` with the correct diagnostic kind, and no
  downstream work item is created.

What this intentionally does NOT cover
---------------------------------------
- Later pipeline stages (test_author, implementer, review, jury, integrator,
  outcome_verifier).  Those are exercised by ``test_pipeline_smoke.py``.
- Real model channels (Claude Code, OpenCode, Gemini).  A FakeChannel is used
  throughout.
- PostgreSQL-backed Regista.  InMemoryRegista is used throughout.
- Inner-gate retry loops (``inner_gate_retries > 0`` requires real pre-gate
  tooling; retries are disabled here via ``inner_gate_retries=0``).
- Concurrent scheduler races or multi-process dedup.
- The full worker_loop / gate_loop daemon loops (only the per-item functions
  ``process_work_item``, ``process_gate_item``, and ``_ensure_downstream_item``
  are called).

The tests deliberately call the real routing and scheduling logic rather than
mocking them, so a code change that breaks the claim→gate→schedule seam will
be caught here even if all unit tests pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from regista.testing import InMemoryRegista

from factory.channel import InvocationResult
from factory.config import FactoryConfig, StageHandoff
from factory.constants import (
    CUSTOM_FIELD_INTERFACE_REF,
    LINK_TYPE_DERIVED_FROM,
    STATE_LOCKED,
    STATE_NEW,
    TRANSITION_CLAIM,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
    WORK_ITEM_TYPE_TEST_SUITE,
)
from factory.gate_process import process_gate_item
from factory.runner import process_work_item
from factory.runtime import PipelineRuntime
from factory.scheduler import _ensure_downstream_item

WORKFLOW_PATH = str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")

# ---------------------------------------------------------------------------
# Handoff descriptor used by the scheduler in this test.
# Mirrors the first entry of FactoryConfig.stage_topology (interface_spec →
# test_suite) so the scheduler call is not importing internal state.
# ---------------------------------------------------------------------------
_IFACE_TO_TEST_HANDOFF = StageHandoff(
    source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
    source_state=STATE_LOCKED,
    target_type=WORK_ITEM_TYPE_TEST_SUITE,
    link_type=LINK_TYPE_DERIVED_FROM,
    ref_field=CUSTOM_FIELD_INTERFACE_REF,
)


# ---------------------------------------------------------------------------
# Fake channels
# ---------------------------------------------------------------------------


class _GoodChannel:
    """Returns a syntactically valid .pyi artifact that satisfies AC-01."""

    name = "fake-good"
    family = "test"

    def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None, model_override=None):
        outputs_dir.mkdir(parents=True, exist_ok=True)
        content = 'def parse(x: int) -> str:\n    """Satisfies AC-01."""\n    ...\n'
        (outputs_dir / "artifact.pyi").write_text(content)
        return InvocationResult(success=True, artifact_name="artifact.pyi", model="fake-model")


class _BadChannel:
    """Returns an empty artifact — guaranteed to fail the not_empty gate check."""

    name = "fake-bad"
    family = "test"

    def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None, model_override=None):
        outputs_dir.mkdir(parents=True, exist_ok=True)
        (outputs_dir / "artifact.pyi").write_text("")
        return InvocationResult(success=True, artifact_name="artifact.pyi", model="fake-model")


# ---------------------------------------------------------------------------
# Fixture: an InMemoryRegista wired to the phase2 workflow, with all
# actors pre-registered.
# ---------------------------------------------------------------------------


@pytest.fixture()
def e2e_regista():
    sub = InMemoryRegista()
    sub.register_workflow_file(WORKFLOW_PATH)
    sub.register_actor_role("worker-fake", "interface_architect")
    sub.register_actor_role("gate-fake", "mechanical_gate")
    yield sub
    sub.close()


@pytest.fixture()
def e2e_config(tmp_path):
    # inner_gate_retries=0 avoids the real pre-gate subprocess tooling;
    # the gate is exercised by process_gate_item which uses the canonical
    # evaluate_* functions (the structural gate, not the pre-gate loop).
    return FactoryConfig.phase2(workspace_root=tmp_path / "work", inner_gate_retries=0)


# ---------------------------------------------------------------------------
# Helper: create and claim a fresh interface_spec work item.
# ---------------------------------------------------------------------------


def _create_and_claim_iface(sub, config, actor_id="worker-fake"):
    wi, _ = sub.create_work_item(
        workflow_name="software_factory",
        work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
        actor_id="test-creator",
        custom_fields={
            "spec_section": "parse(x: int) -> str",
            "ac_ids": ["AC-01"],
        },
    )
    claim = sub.acquire_claim(wi.work_item_id, actor_id)
    sub.transition(
        wi.work_item_id,
        TRANSITION_CLAIM,
        actor_id,
        actor_metadata={"role": "interface_architect"},
    )
    return wi, claim


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSyntheticPipelineE2E:
    def test_happy_path_gate_pass_routes_to_locked_and_schedules_downstream(
        self, e2e_regista, e2e_config
    ):
        """Happy path: gate passes → work item reaches 'locked' → scheduler creates test_suite.

        Exercises the full sequence:
          claim → model invoke → submit → gate evaluate → gate_pass →
          locked → _ensure_downstream_item → test_suite created in 'new'
        """
        sub = e2e_regista
        config = e2e_config
        wi, claim = _create_and_claim_iface(sub, config)

        runtime = PipelineRuntime(
            sub=sub,
            config=config,
            spec_content="parse(x: int) -> str",
            channel=_GoodChannel(),
        )

        # --- Invoke: worker claims item and submits artifact ---
        process_work_item(runtime, wi, "worker-fake", claim, "interface_architect")

        after_invoke = sub.get_work_item(wi.work_item_id)
        assert after_invoke.current_state == "gating", (
            f"Expected 'gating' after process_work_item; got {after_invoke.current_state!r}"
        )

        # --- Gate: evaluate the submitted artifact ---
        gate_claim = sub.acquire_claim(after_invoke.work_item_id, "gate-fake")
        gate_runtime = PipelineRuntime(sub=sub, config=config)
        process_gate_item(gate_runtime, after_invoke, "gate-fake", gate_claim)

        after_gate = sub.get_work_item(wi.work_item_id)
        assert after_gate.current_state == STATE_LOCKED, (
            f"Expected 'locked' after gate pass; got {after_gate.current_state!r}"
        )

        # --- Scheduler: ensure a test_suite work item is created ---
        sched_runtime = PipelineRuntime(sub=sub, config=config)
        _ensure_downstream_item(sched_runtime, after_gate, _IFACE_TO_TEST_HANDOFF)

        ts_page = sub.query_work_items(
            workflow_name="software_factory",
            workflow_version=2,
            work_item_types=[WORK_ITEM_TYPE_TEST_SUITE],
            page_size=10,
        )
        assert len(ts_page.items) == 1, (
            f"Expected exactly 1 test_suite work item; got {len(ts_page.items)}"
        )
        ts_wi = ts_page.items[0]
        assert ts_wi.current_state == STATE_NEW, (
            f"Scheduled test_suite should start in 'new'; got {ts_wi.current_state!r}"
        )
        # The scheduler must propagate interface_ref so the downstream gate can
        # locate the locked interface artifact.
        ts_custom = ts_wi.custom_fields or {}
        assert ts_custom.get(CUSTOM_FIELD_INTERFACE_REF) == str(wi.work_item_id), (
            f"test_suite.interface_ref should point to the locked interface_spec; "
            f"got {ts_custom.get(CUSTOM_FIELD_INTERFACE_REF)!r}"
        )

    def test_failure_path_gate_fail_routes_back_to_new_no_downstream(self, e2e_regista, e2e_config):
        """Failure path: gate fails → work item returns to 'new' → no test_suite created.

        Exercises the full sequence:
          claim → model invoke (returns empty artifact) → submit → gate evaluate →
          gate_fail → 'new' (diagnostic_kind='not_empty') →
          _ensure_downstream_item is a no-op because source is not 'locked'
        """
        sub = e2e_regista
        config = e2e_config
        wi, claim = _create_and_claim_iface(sub, config)

        runtime = PipelineRuntime(
            sub=sub,
            config=config,
            spec_content="parse(x: int) -> str",
            channel=_BadChannel(),
        )

        # --- Invoke: worker submits an empty artifact ---
        process_work_item(runtime, wi, "worker-fake", claim, "interface_architect")

        after_invoke = sub.get_work_item(wi.work_item_id)
        assert after_invoke.current_state == "gating", (
            f"Expected 'gating' after process_work_item; got {after_invoke.current_state!r}"
        )

        # --- Gate: evaluate the empty artifact → should fail ---
        gate_claim = sub.acquire_claim(after_invoke.work_item_id, "gate-fake")
        gate_runtime = PipelineRuntime(sub=sub, config=config)
        process_gate_item(gate_runtime, after_invoke, "gate-fake", gate_claim)

        after_gate = sub.get_work_item(wi.work_item_id)
        assert after_gate.current_state == STATE_NEW, (
            f"Expected 'new' after gate fail; got {after_gate.current_state!r}"
        )

        # Routing must attach the correct diagnostic kind so the worker knows
        # what went wrong (this is the data that drives re-prompting).
        diagnostics = (after_gate.custom_fields or {}).get("diagnostics", {})
        assert diagnostics.get("diagnostic_kind") == "not_empty", (
            f"Expected diagnostic_kind='not_empty'; got {diagnostics!r}"
        )

        # --- Scheduler: source is 'new', not 'locked' — must NOT create test_suite ---
        # The handoff only matches source_state=STATE_LOCKED; the scheduler loop
        # only calls _ensure_downstream_item for items already in source_state, so
        # the scheduler would not have been triggered in this failure scenario.
        # Verify directly that no downstream work item was created.
        ts_page = sub.query_work_items(
            workflow_name="software_factory",
            workflow_version=2,
            work_item_types=[WORK_ITEM_TYPE_TEST_SUITE],
            page_size=10,
        )
        assert len(ts_page.items) == 0, (
            f"No test_suite should be created after a gate failure; "
            f"got {len(ts_page.items)} item(s)"
        )
