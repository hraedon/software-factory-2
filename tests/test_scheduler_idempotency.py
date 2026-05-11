from __future__ import annotations

from pathlib import Path

from factory.config import FactoryConfig
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
    def test_second_source_still_gets_downstream(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig(
            workspace_root=workspace_root,
            workflow_version=2,
        )

        source_a, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Source A",
                "ac_ids": ["AC-01"],
            },
        )
        source_b, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Source B",
                "ac_ids": ["AC-02"],
            },
        )

        handoff = {
            "next_type": "test_suite",
            "link_type": "derived_from",
            "next_role": "test_author",
        }

        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        _ensure_downstream_item(sched_runtime, source_a, handoff)

        ts_a = mock_substrate.query_work_items(
            work_item_types=["test_suite"],
            page_size=100,
        )
        assert len(ts_a.items) == 1
        assert ts_a.items[0].custom_fields["interface_ref"] == str(source_a.work_item_id)

        _ensure_downstream_item(sched_runtime, source_b, handoff)

        ts_all = mock_substrate.query_work_items(
            work_item_types=["test_suite"],
            page_size=100,
        )
        assert len(ts_all.items) == 2
        refs = {item.custom_fields["interface_ref"] for item in ts_all.items}
        assert str(source_a.work_item_id) in refs
        assert str(source_b.work_item_id) in refs

    def test_duplicate_handoff_is_idempotent(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig(
            workspace_root=workspace_root,
            workflow_version=2,
        )

        source, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Source",
                "ac_ids": ["AC-01"],
            },
        )

        handoff = {
            "next_type": "test_suite",
            "link_type": "derived_from",
            "next_role": "test_author",
        }

        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        _ensure_downstream_item(sched_runtime, source, handoff)
        _ensure_downstream_item(sched_runtime, source, handoff)
        _ensure_downstream_item(sched_runtime, source, handoff)

        ts_all = mock_substrate.query_work_items(
            work_item_types=["test_suite"],
            page_size=100,
        )
        assert len(ts_all.items) == 1

    def test_implementation_handoff_with_interface_ref_propagation(
        self, mock_substrate, workspace_root
    ):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig(
            workspace_root=workspace_root,
            workflow_version=2,
        )

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Section",
                "ac_ids": ["AC-01"],
            },
        )

        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        iface_handoff = {
            "next_type": "test_suite",
            "link_type": "derived_from",
            "next_role": "test_author",
        }
        _ensure_downstream_item(sched_runtime, iface, iface_handoff)

        ts_page = mock_substrate.query_work_items(
            work_item_types=["test_suite"],
            page_size=10,
        )
        ts_wi = ts_page.items[0]

        impl_handoff = {
            "next_type": "implementation",
            "link_type": "tested_by",
            "additional_links": ["implements"],
            "next_role": "implementer",
        }
        _ensure_downstream_item(sched_runtime, ts_wi, impl_handoff)

        impl_page = mock_substrate.query_work_items(
            work_item_types=["implementation"],
            page_size=10,
        )
        assert len(impl_page.items) == 1
        impl = impl_page.items[0]
        assert impl.custom_fields["interface_ref"] == str(iface.work_item_id)
        assert impl.custom_fields["test_suite_ref"] == str(ts_wi.work_item_id)

    def test_defers_test_suite_when_dep_not_locked(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig(
            workspace_root=workspace_root,
            workflow_version=2,
        )

        root, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Root",
                "ac_ids": ["AC-01"],
            },
        )

        dep, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Dependent",
                "ac_ids": ["AC-02"],
                "dependency_refs": [str(root.work_item_id)],
            },
        )

        _lock_interface_spec(mock_substrate, dep)

        handoff = {
            "next_type": "test_suite",
            "link_type": "derived_from",
            "next_role": "test_author",
        }
        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        _ensure_downstream_item(sched_runtime, dep, handoff)

        ts_page = mock_substrate.query_work_items(
            work_item_types=["test_suite"],
            page_size=10,
        )
        assert len(ts_page.items) == 0

        _lock_interface_spec(mock_substrate, root)
        _ensure_downstream_item(sched_runtime, dep, handoff)

        ts_page = mock_substrate.query_work_items(
            work_item_types=["test_suite"],
            page_size=10,
        )
        assert len(ts_page.items) == 1
        assert ts_page.items[0].custom_fields["interface_ref"] == str(dep.work_item_id)

    def test_no_dep_items_created_immediately(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig(
            workspace_root=workspace_root,
            workflow_version=2,
        )

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "No deps",
                "ac_ids": ["AC-01"],
            },
        )
        _lock_interface_spec(mock_substrate, iface)

        handoff = {
            "next_type": "test_suite",
            "link_type": "derived_from",
            "next_role": "test_author",
        }
        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        _ensure_downstream_item(sched_runtime, iface, handoff)

        ts_page = mock_substrate.query_work_items(
            work_item_types=["test_suite"],
            page_size=10,
        )
        assert len(ts_page.items) == 1
