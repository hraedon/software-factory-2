from __future__ import annotations

from pathlib import Path

from factory.config import FactoryConfig
from factory.scheduler import _ensure_downstream_item


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

        _ensure_downstream_item(mock_substrate, config, source_a, handoff)

        ts_a = mock_substrate.query_work_items(
            work_item_types=["test_suite"],
            page_size=100,
        )
        assert len(ts_a.items) == 1
        assert ts_a.items[0].custom_fields["interface_ref"] == str(source_a.work_item_id)

        _ensure_downstream_item(mock_substrate, config, source_b, handoff)

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

        _ensure_downstream_item(mock_substrate, config, source, handoff)
        _ensure_downstream_item(mock_substrate, config, source, handoff)
        _ensure_downstream_item(mock_substrate, config, source, handoff)

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

        iface_handoff = {
            "next_type": "test_suite",
            "link_type": "derived_from",
            "next_role": "test_author",
        }
        _ensure_downstream_item(mock_substrate, config, iface, iface_handoff)

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
        _ensure_downstream_item(mock_substrate, config, ts_wi, impl_handoff)

        impl_page = mock_substrate.query_work_items(
            work_item_types=["implementation"],
            page_size=10,
        )
        assert len(impl_page.items) == 1
        impl = impl_page.items[0]
        assert impl.custom_fields["interface_ref"] == str(iface.work_item_id)
        assert impl.custom_fields["test_suite_ref"] == str(ts_wi.work_item_id)
