from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from regista._testing import drop_project_schema

TESTS_DIR = Path(__file__).parent
DSN = "postgresql://regista_test:regista_test@localhost:5432/regista_test"
KEY_PATH = str(TESTS_DIR / "test_keys.json")
PHASE2_PATH = str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")


@pytest.fixture(scope="function")
def regista():
    from regista import Regista

    project = f"sf2_p2rt_{uuid.uuid4().hex[:8]}"
    sub = Regista.create_project(DSN, project, KEY_PATH)
    sub.register_workflow_file(PHASE2_PATH)
    yield sub
    sub.close()
    drop_project_schema(DSN, project)


class TestPhase2WorkflowRoundtrip:
    def test_phase2_yaml_registers_cleanly(self, regista):
        v = regista.register_workflow_file(PHASE2_PATH)
        assert v.name == "software_factory"
        assert v.version == 2

    def test_interface_spec_lifecycle(self, regista):
        regista.register_actor_role("arch", "interface_architect")
        regista.register_actor_role("gate", "mechanical_gate")

        wi, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={
                "spec_section": "3.1",
                "ac_ids": ["AC-01", "AC-02"],
                "artifact_path": "/tmp/spec.md",
            },
        )
        assert wi.current_state == "new"
        assert wi.workflow_version == 2

        regista.transition(
            wi.work_item_id,
            "claim",
            "arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
        )
        assert regista.get_work_item(wi.work_item_id).current_state == "in_progress"

        regista.transition(
            wi.work_item_id,
            "submit",
            "arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"artifact_hash": "sha256:abc"},
        )
        assert regista.get_work_item(wi.work_item_id).current_state == "gating"

        regista.transition(
            wi.work_item_id,
            "gate_pass",
            "gate",
            actor_kind="agent",
            actor_metadata={"role": "mechanical_gate"},
        )
        assert regista.get_work_item(wi.work_item_id).current_state == "locked"

    def test_channel_fail_is_a_real_transition(self, regista):
        regista.register_actor_role("arch", "interface_architect")

        wi, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"spec_section": "3.1", "ac_ids": ["AC-01"]},
        )
        regista.transition(
            wi.work_item_id,
            "claim",
            "arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
        )
        assert regista.get_work_item(wi.work_item_id).current_state == "in_progress"

        regista.transition(
            wi.work_item_id,
            "channel_fail",
            "arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            payload={"diagnostics": {"error_message": "timeout", "timed_out": True}},
        )
        assert regista.get_work_item(wi.work_item_id).current_state == "new"

    def test_test_suite_references_valid_interface_spec(self, regista):
        regista.register_actor_role("arch", "interface_architect")
        regista.register_actor_role("tester", "test_author")

        iface, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"spec_section": "3.1", "ac_ids": ["AC-01"]},
        )

        ts, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="tester",
            actor_kind="agent",
            actor_metadata={"role": "test_author"},
            custom_fields={
                "spec_section": "3.1",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
            },
        )
        assert ts.current_state == "new"
        assert ts.work_item_type == "test_suite"
        assert ts.custom_fields.get("interface_ref") == str(iface.work_item_id)

    def test_test_suite_rejects_wrong_type_ref(self, regista):
        regista.register_actor_role("arch", "interface_architect")
        regista.register_actor_role("tester", "test_author")

        iface, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"spec_section": "3.1", "ac_ids": ["AC-01"]},
        )

        with pytest.raises(Exception, match="CUSTOM_FIELD_VIOLATION"):
            regista.create_work_item(
                workflow_name="software_factory",
                work_item_type="implementation",
                actor_id="tester",
                actor_kind="agent",
                actor_metadata={"role": "implementer"},
                custom_fields={
                    "spec_section": "3.1",
                    "ac_ids": ["AC-01"],
                    "interface_ref": str(iface.work_item_id),
                    "test_suite_ref": str(iface.work_item_id),
                },
            )

    def test_full_chain_with_links(self, regista):
        regista.register_actor_role("arch", "interface_architect")
        regista.register_actor_role("tester", "test_author")
        regista.register_actor_role("impl", "implementer")
        regista.register_actor_role("gate", "mechanical_gate")

        iface, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"spec_section": "4.1 Range parser", "ac_ids": ["AC-01"]},
        )
        regista.transition(
            iface.work_item_id,
            "claim",
            "arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
        )
        regista.transition(
            iface.work_item_id,
            "submit",
            "arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"artifact_hash": "sha256:abc"},
        )
        regista.transition(
            iface.work_item_id,
            "gate_pass",
            "gate",
            actor_kind="agent",
            actor_metadata={"role": "mechanical_gate"},
        )
        assert regista.get_work_item(iface.work_item_id).current_state == "locked"

        ts, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="tester",
            actor_kind="agent",
            actor_metadata={"role": "test_author"},
            custom_fields={
                "spec_section": "4.1 Range parser",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
            },
        )
        link1 = regista.create_link(
            from_work_item_id=ts.work_item_id,
            to_work_item_id=iface.work_item_id,
            link_type="derived_from",
            actor_id="tester",
            actor_kind="agent",
        )
        assert link1.link_type == "derived_from"

        impl, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="implementation",
            actor_id="impl",
            actor_kind="agent",
            actor_metadata={"role": "implementer"},
            custom_fields={
                "spec_section": "4.1 Range parser",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "test_suite_ref": str(ts.work_item_id),
            },
        )
        link2 = regista.create_link(
            from_work_item_id=impl.work_item_id,
            to_work_item_id=iface.work_item_id,
            link_type="implements",
            actor_id="impl",
            actor_kind="agent",
        )
        link3 = regista.create_link(
            from_work_item_id=impl.work_item_id,
            to_work_item_id=ts.work_item_id,
            link_type="tested_by",
            actor_id="impl",
            actor_kind="agent",
        )
        assert link2.link_type == "implements"
        assert link3.link_type == "tested_by"

    def test_wrong_role_cannot_claim(self, regista):
        regista.register_actor_role("arch", "interface_architect")
        regista.register_actor_role("gate", "mechanical_gate")

        iface, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"spec_section": "3.1", "ac_ids": ["AC-01"]},
        )

        with pytest.raises(Exception, match="ROLE_NOT_PERMITTED"):
            regista.transition(
                iface.work_item_id,
                "claim",
                "gate",
                actor_kind="agent",
                actor_metadata={"role": "mechanical_gate"},
            )

    def test_attempt_threshold_three(self, regista):
        regista.register_actor_role("a1", "interface_architect")
        regista.register_actor_role("a2", "interface_architect")
        regista.register_actor_role("a3", "interface_architect")

        wi, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="a1",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"spec_section": "3.1", "ac_ids": ["AC-01"]},
        )
        regista.acquire_claim(wi.work_item_id, "a1", ttl_seconds=1)
        import time

        time.sleep(1.1)

        regista.acquire_claim(wi.work_item_id, "a2", ttl_seconds=1)
        time.sleep(1.1)

        regista.acquire_claim(wi.work_item_id, "a3", ttl_seconds=1)
        assert regista.get_work_item(wi.work_item_id).needs_review is True
