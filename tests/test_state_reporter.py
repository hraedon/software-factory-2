from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

from factory.config import FactoryConfig, RoleConfig
from factory.constants import (
    STATE_CANNOT_PROCEED,
    STATE_IN_PROGRESS,
    STATE_LOCKED,
    STATE_NEW,
)
from factory.state_reporter import StateReporter


def _make_sub(items=None, events=None):
    sub = MagicMock()
    page = MagicMock()
    page.items = items or []
    sub.query_work_items.return_value = page
    sub.read_events.return_value = events or []
    return sub


def _make_wi(wi_id="w1", wi_type="implementation", state="locked", custom_fields=None):
    wi = MagicMock()
    wi.work_item_id = wi_id
    wi.work_item_type = wi_type
    wi.current_state = state
    wi.custom_fields = custom_fields or {}
    return wi


def _make_event(timestamp=None, payload=None):
    ev = MagicMock()
    ev.timestamp = timestamp or datetime.now(UTC).isoformat()
    ev.payload = payload or {}
    return ev


def _make_config(**overrides):
    defaults = {
        "workflow_name": "test-workflow",
        "workflow_version": 2,
        "project_name": "test-project",
        "workspace_root": None,
        "query_page_size": 200,
    }
    defaults.update(overrides)
    return FactoryConfig(**defaults)


class TestProgressSummary:
    def test_empty_workspace(self):
        sub = _make_sub(items=[])
        config = _make_config()
        reporter = StateReporter(sub, config)
        snap = reporter.snapshot()
        assert snap.progress.total == 0
        assert snap.progress.completion_percent == 0.0

    def test_locked_items_completion(self):
        items = [
            _make_wi("w1", "implementation", STATE_LOCKED),
            _make_wi("w2", "test_suite", STATE_LOCKED),
            _make_wi("w3", "interface_spec", STATE_NEW),
        ]
        sub = _make_sub(items=items)
        config = _make_config()
        reporter = StateReporter(sub, config)
        snap = reporter.snapshot()
        assert snap.progress.total == 3
        assert snap.progress.completion_percent == 66.7

    def test_all_locked_100_percent(self):
        items = [_make_wi("w1", "implementation", STATE_LOCKED)]
        sub = _make_sub(items=items)
        config = _make_config()
        reporter = StateReporter(sub, config)
        snap = reporter.snapshot()
        assert snap.progress.completion_percent == 100.0

    def test_by_type_counts(self):
        items = [
            _make_wi("w1", "interface_spec", STATE_LOCKED),
            _make_wi("w2", "interface_spec", STATE_NEW),
            _make_wi("w3", "implementation", STATE_IN_PROGRESS),
        ]
        sub = _make_sub(items=items)
        config = _make_config()
        reporter = StateReporter(sub, config)
        snap = reporter.snapshot()
        assert snap.progress.by_type["interface_spec"][STATE_LOCKED] == 1
        assert snap.progress.by_type["interface_spec"][STATE_NEW] == 1
        assert snap.progress.by_type["implementation"][STATE_IN_PROGRESS] == 1


class TestRecentFailures:
    def test_no_failures(self):
        sub = _make_sub(items=[], events=[])
        config = _make_config()
        reporter = StateReporter(sub, config)
        snap = reporter.snapshot()
        assert snap.recent_failures == []

    def test_failure_grouped_by_kind(self):
        events = [
            _make_event(
                payload={
                    "diagnostics": {
                        "diagnostic_kind": "impl_mypy",
                        "gate_name": "implementation_mypy",
                        "message": "type error on line 5",
                    }
                }
            ),
            _make_event(
                payload={
                    "diagnostics": {
                        "diagnostic_kind": "impl_mypy",
                        "gate_name": "implementation_mypy",
                        "message": "type error on line 10",
                    }
                }
            ),
            _make_event(
                payload={
                    "diagnostics": {
                        "diagnostic_kind": "impl_pytest",
                        "gate_name": "implementation_pytest",
                        "message": "test failed",
                    }
                }
            ),
        ]
        sub = _make_sub(items=[], events=events)
        config = _make_config()
        reporter = StateReporter(sub, config)
        snap = reporter.snapshot()
        assert len(snap.recent_failures) == 2
        assert snap.recent_failures[0].diagnostic_kind == "impl_mypy"
        assert snap.recent_failures[0].count == 2
        assert snap.recent_failures[1].diagnostic_kind == "impl_pytest"
        assert snap.recent_failures[1].count == 1


class TestChannelHealth:
    def test_channel_bindings(self):
        config = _make_config(
            roles=(
                RoleConfig(role="implementer", channel="opencode", model="k2"),
                RoleConfig(role="test_author", channel="opencode", model="k2"),
            )
        )
        sub = _make_sub(items=[])
        reporter = StateReporter(sub, config)
        snap = reporter.snapshot()
        assert len(snap.channel_health) == 2
        roles = {ch.role for ch in snap.channel_health}
        assert "implementer" in roles
        assert "test_author" in roles


class TestRenderFormats:
    def test_render_markdown(self):
        items = [
            _make_wi("w1", "implementation", STATE_LOCKED),
            _make_wi("w2", "implementation", STATE_NEW),
        ]
        sub = _make_sub(items=items)
        config = _make_config()
        reporter = StateReporter(sub, config)
        snap = reporter.snapshot()
        md = reporter.render_markdown(snap)
        assert "Pipeline State" in md
        assert "test-project" in md
        assert "locked" in md

    def test_render_brief(self):
        items = [
            _make_wi("w1", "implementation", STATE_LOCKED),
            _make_wi("w2", "test_suite", STATE_CANNOT_PROCEED),
        ]
        sub = _make_sub(items=items)
        config = _make_config()
        reporter = StateReporter(sub, config)
        snap = reporter.snapshot()
        brief = reporter.render_brief(snap)
        assert "1/2 locked" in brief
        assert "1 cannot_proceed" in brief

    def test_render_json(self):
        items = [_make_wi("w1", "implementation", STATE_LOCKED)]
        sub = _make_sub(items=items)
        config = _make_config()
        reporter = StateReporter(sub, config)
        snap = reporter.snapshot()
        j = reporter.render_json(snap)
        data = json.loads(j)
        assert data["project_name"] == "test-project"
        assert data["progress"]["total"] == 1


class TestDiskPressure:
    def test_no_workspace_root(self, tmp_path):
        sub = _make_sub(items=[])
        config = _make_config(workspace_root=None)
        reporter = StateReporter(sub, config)
        snap = reporter.snapshot()
        assert snap.disk_pressure is None

    def test_workspace_root_exists(self, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "test.py").write_text("pass")
        sub = _make_sub(items=[])
        config = _make_config(workspace_root=str(ws))
        reporter = StateReporter(sub, config)
        snap = reporter.snapshot()
        assert snap.disk_pressure is not None
        assert snap.disk_pressure.workspace_root == str(ws)


class TestMainEntry:
    def test_main_imports(self):
        from factory.state_reporter import _main, main

        assert callable(_main)
        assert callable(main)
