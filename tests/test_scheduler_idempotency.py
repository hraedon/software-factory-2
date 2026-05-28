from __future__ import annotations

from pathlib import Path

from factory.config import FactoryConfig, StageHandoff
from factory.constants import (
    CUSTOM_FIELD_INTERFACE_REF,
    LINK_TYPE_DERIVED_FROM,
    STATE_LOCKED,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
    WORK_ITEM_TYPE_TEST_SUITE,
)
from factory.runtime import PipelineRuntime
from factory.scheduler import _ensure_downstream_item


def _lock_interface_spec(sub, wi):
    sub.transition(
        wi.work_item_id,
        "claim",
        "test",
        actor_kind="agent",
        actor_metadata={"role": "interface_architect"},
    )
    sub.transition(
        wi.work_item_id,
        "submit",
        "test",
        actor_kind="agent",
        actor_metadata={"role": "interface_architect"},
    )
    sub.transition(
        wi.work_item_id,
        "gate_pass",
        "mechanical_gate",
        actor_kind="agent",
        actor_metadata={"role": "mechanical_gate"},
    )


class TestSchedulerIdempotency:
    def test_second_source_still_gets_downstream(self, mock_regista, workspace_root):
        mock_regista.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig.phase2(workspace_root=workspace_root)

        source_a, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Source A",
                "ac_ids": ["AC-01"],
            },
        )
        source_b, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Source B",
                "ac_ids": ["AC-02"],
            },
        )

        handoff = StageHandoff(
            source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            source_state=STATE_LOCKED,
            target_type=WORK_ITEM_TYPE_TEST_SUITE,
            link_type=LINK_TYPE_DERIVED_FROM,
            ref_field=CUSTOM_FIELD_INTERFACE_REF,
        )

        sched_runtime = PipelineRuntime(sub=mock_regista, config=config)
        _ensure_downstream_item(sched_runtime, source_a, handoff)

        ts_a = mock_regista.query_work_items(
            work_item_types=["test_suite"],
            page_size=100,
        )
        assert len(ts_a.items) == 1
        assert ts_a.items[0].custom_fields["interface_ref"] == str(source_a.work_item_id)

        _ensure_downstream_item(sched_runtime, source_b, handoff)

        ts_all = mock_regista.query_work_items(
            work_item_types=["test_suite"],
            page_size=100,
        )
        assert len(ts_all.items) == 2
        refs = {item.custom_fields["interface_ref"] for item in ts_all.items}
        assert str(source_a.work_item_id) in refs
        assert str(source_b.work_item_id) in refs

    def test_duplicate_handoff_is_idempotent(self, mock_regista, workspace_root):
        mock_regista.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig.phase2(workspace_root=workspace_root)

        source, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Source",
                "ac_ids": ["AC-01"],
            },
        )

        handoff = StageHandoff(
            source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            source_state=STATE_LOCKED,
            target_type=WORK_ITEM_TYPE_TEST_SUITE,
            link_type=LINK_TYPE_DERIVED_FROM,
            ref_field=CUSTOM_FIELD_INTERFACE_REF,
        )

        sched_runtime = PipelineRuntime(sub=mock_regista, config=config)
        _ensure_downstream_item(sched_runtime, source, handoff)
        _ensure_downstream_item(sched_runtime, source, handoff)
        _ensure_downstream_item(sched_runtime, source, handoff)

        ts_all = mock_regista.query_work_items(
            work_item_types=["test_suite"],
            page_size=100,
        )
        assert len(ts_all.items) == 1

    def test_implementation_handoff_with_interface_ref_propagation(
        self, mock_regista, workspace_root
    ):
        mock_regista.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig.phase2(workspace_root=workspace_root)

        iface, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Section",
                "ac_ids": ["AC-01"],
            },
        )

        sched_runtime = PipelineRuntime(sub=mock_regista, config=config)
        iface_handoff = StageHandoff(
            source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            source_state=STATE_LOCKED,
            target_type=WORK_ITEM_TYPE_TEST_SUITE,
            link_type=LINK_TYPE_DERIVED_FROM,
            ref_field=CUSTOM_FIELD_INTERFACE_REF,
        )
        _ensure_downstream_item(sched_runtime, iface, iface_handoff)

        ts_page = mock_regista.query_work_items(
            work_item_types=["test_suite"],
            page_size=10,
        )
        assert len(ts_page.items) == 1

    def test_pagination_walks_all_pages_to_find_existing(self, mock_regista, workspace_root):
        mock_regista.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig.phase2(workspace_root=workspace_root, query_page_size=2)

        source, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Source",
                "ac_ids": ["AC-01"],
            },
        )
        _lock_interface_spec(mock_regista, source)

        # Create 3 other interface_specs + their test_suites
        for i in range(3):
            other, _ = mock_regista.create_work_item(
                workflow_name="software_factory",
                work_item_type="interface_spec",
                actor_id="test",
                custom_fields={
                    "spec_section": f"Other {i}",
                    "ac_ids": [f"AC-{i}"],
                },
            )
            _lock_interface_spec(mock_regista, other)
            mock_regista.create_work_item(
                workflow_name="software_factory",
                work_item_type="test_suite",
                actor_id="test",
                custom_fields={
                    "spec_section": f"Tests {i}",
                    "ac_ids": [f"AC-{i}"],
                    "interface_ref": str(other.work_item_id),
                },
            )

        handoff = StageHandoff(
            source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            source_state=STATE_LOCKED,
            target_type=WORK_ITEM_TYPE_TEST_SUITE,
            link_type=LINK_TYPE_DERIVED_FROM,
            ref_field=CUSTOM_FIELD_INTERFACE_REF,
        )

        sched_runtime = PipelineRuntime(sub=mock_regista, config=config)
        _ensure_downstream_item(sched_runtime, source, handoff)

        # 3 existing + 1 new for source = 4 total; proves scheduler paginated
        ts_all = mock_regista.query_work_items(
            work_item_types=["test_suite"],
            page_size=100,
        )
        assert len(ts_all.items) == 4
        refs = {item.custom_fields["interface_ref"] for item in ts_all.items}
        assert str(source.work_item_id) in refs

    def test_no_dep_items_created_immediately(self, mock_regista, workspace_root):
        mock_regista.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig.phase2(workspace_root=workspace_root)

        iface, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "No deps",
                "ac_ids": ["AC-01"],
            },
        )
        _lock_interface_spec(mock_regista, iface)

        handoff = StageHandoff(
            source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            source_state=STATE_LOCKED,
            target_type=WORK_ITEM_TYPE_TEST_SUITE,
            link_type=LINK_TYPE_DERIVED_FROM,
            ref_field=CUSTOM_FIELD_INTERFACE_REF,
        )
        sched_runtime = PipelineRuntime(sub=mock_regista, config=config)
        _ensure_downstream_item(sched_runtime, iface, handoff)

        ts_page = mock_regista.query_work_items(
            work_item_types=["test_suite"],
            page_size=10,
        )
        assert len(ts_page.items) == 1
