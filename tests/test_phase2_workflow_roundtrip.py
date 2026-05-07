from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from substrate._testing import drop_project_schema

TESTS_DIR = Path(__file__).parent
DSN = "postgresql://substrate_test:substrate_test@localhost:5432/substrate_test"
KEY_PATH = str(TESTS_DIR / "test_keys.json")
PHASE2_PATH = str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")


@pytest.fixture(scope="function")
def substrate():
    from substrate import Substrate

    project = f"sf2_p2rt_{uuid.uuid4().hex[:8]}"
    sub = Substrate.create_project(DSN, project, KEY_PATH)
    sub.register_workflow_file(PHASE2_PATH)
    yield sub
    sub.close()
    drop_project_schema(DSN, project)


class TestPhase2WorkflowRoundtrip:
    def test_phase2_yaml_registers_cleanly(self, substrate):
        v = substrate.register_workflow_file(PHASE2_PATH)
        assert v.name == "software_factory"
        assert v.version == 2

    def test_interface_spec_lifecycle(self, substrate):
        substrate.register_actor_role("arch", "interface_architect")
        substrate.register_actor_role("gate", "mechanical_gate")

        wi, _ = substrate.create_work_item(
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

        substrate.transition(
            wi.work_item_id, "claim", "arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
        )
        assert substrate.get_work_item(wi.work_item_id).current_state == "in_progress"

        substrate.transition(
            wi.work_item_id,
            "submit",
            "arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"artifact_hash": "sha256:abc"},
        )
        assert substrate.get_work_item(wi.work_item_id).current_state == "gating"

        substrate.transition(
            wi.work_item_id, "gate_pass", "gate",
            actor_kind="agent",
            actor_metadata={"role": "mechanical_gate"},
        )
        assert substrate.get_work_item(wi.work_item_id).current_state == "locked"

    def test_channel_fail_is_a_real_transition(self, substrate):
        substrate.register_actor_role("arch", "interface_architect")

        wi, _ = substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"spec_section": "3.1", "ac_ids": ["AC-01"]},
        )
        substrate.transition(
            wi.work_item_id, "claim", "arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
        )
        assert substrate.get_work_item(wi.work_item_id).current_state == "in_progress"

        substrate.transition(
            wi.work_item_id,
            "channel_fail",
            "arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            payload={"diagnostics": {"error_message": "timeout", "timed_out": True}},
        )
        assert substrate.get_work_item(wi.work_item_id).current_state == "new"

    def test_test_suite_references_valid_interface_spec(self, substrate):
        substrate.register_actor_role("arch", "interface_architect")
        substrate.register_actor_role("tester", "test_author")

        iface, _ = substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"spec_section": "3.1", "ac_ids": ["AC-01"]},
        )

        ts, _ = substrate.create_work_item(
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

    def test_test_suite_rejects_wrong_type_ref(self, substrate):
        substrate.register_actor_role("arch", "interface_architect")
        substrate.register_actor_role("tester", "test_author")

        iface, _ = substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"spec_section": "3.1", "ac_ids": ["AC-01"]},
        )

        with pytest.raises(Exception, match="CUSTOM_FIELD_VIOLATION"):
            substrate.create_work_item(
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

    def test_full_chain_with_links(self, substrate):
        substrate.register_actor_role("arch", "interface_architect")
        substrate.register_actor_role("tester", "test_author")
        substrate.register_actor_role("impl", "implementer")
        substrate.register_actor_role("gate", "mechanical_gate")

        iface, _ = substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"spec_section": "4.1 Range parser", "ac_ids": ["AC-01"]},
        )
        substrate.transition(
            iface.work_item_id, "claim", "arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
        )
        substrate.transition(
            iface.work_item_id,
            "submit",
            "arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"artifact_hash": "sha256:abc"},
        )
        substrate.transition(
            iface.work_item_id, "gate_pass", "gate",
            actor_kind="agent",
            actor_metadata={"role": "mechanical_gate"},
        )
        assert substrate.get_work_item(iface.work_item_id).current_state == "locked"

        ts, _ = substrate.create_work_item(
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
        link1 = substrate.create_link(
            from_work_item_id=ts.work_item_id,
            to_work_item_id=iface.work_item_id,
            link_type="derived_from",
            actor_id="tester",
            actor_kind="agent",
        )
        assert link1.link_type == "derived_from"

        impl, _ = substrate.create_work_item(
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
        link2 = substrate.create_link(
            from_work_item_id=impl.work_item_id,
            to_work_item_id=iface.work_item_id,
            link_type="implements",
            actor_id="impl",
            actor_kind="agent",
        )
        link3 = substrate.create_link(
            from_work_item_id=impl.work_item_id,
            to_work_item_id=ts.work_item_id,
            link_type="tested_by",
            actor_id="impl",
            actor_kind="agent",
        )
        assert link2.link_type == "implements"
        assert link3.link_type == "tested_by"

    def test_wrong_role_cannot_claim(self, substrate):
        substrate.register_actor_role("arch", "interface_architect")
        substrate.register_actor_role("gate", "mechanical_gate")

        iface, _ = substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"spec_section": "3.1", "ac_ids": ["AC-01"]},
        )

        with pytest.raises(Exception, match="ROLE_NOT_PERMITTED"):
            substrate.transition(
                iface.work_item_id, "claim", "gate",
                actor_kind="agent",
                actor_metadata={"role": "mechanical_gate"},
            )

    def test_attempt_threshold_three(self, substrate):
        substrate.register_actor_role("a1", "interface_architect")
        substrate.register_actor_role("a2", "interface_architect")
        substrate.register_actor_role("a3", "interface_architect")

        wi, _ = substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="a1",
            actor_kind="agent",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"spec_section": "3.1", "ac_ids": ["AC-01"]},
        )
        substrate.acquire_claim(wi.work_item_id, "a1", ttl_seconds=1)
        import time
        time.sleep(1.1)

        substrate.acquire_claim(wi.work_item_id, "a2", ttl_seconds=1)
        time.sleep(1.1)

        substrate.acquire_claim(wi.work_item_id, "a3", ttl_seconds=1)
        assert substrate.get_work_item(wi.work_item_id).needs_review is True
