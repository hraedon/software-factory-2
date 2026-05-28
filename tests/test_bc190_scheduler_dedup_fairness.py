"""BC-190: scheduler dedup lock, existence cache, and handoff fairness tests."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from factory.config import FactoryConfig, StageHandoff
from factory.constants import (
    CUSTOM_FIELD_INTERFACE_REF,
    LINK_TYPE_DERIVED_FROM,
    STATE_LOCKED,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
    WORK_ITEM_TYPE_TEST_SUITE,
)
from factory.runtime import PipelineRuntime
from factory.scheduler import (
    _ensure_downstream_item,
    _existence_cache,
    _existence_cache_lock,
    _poll_handoffs,
)


@pytest.fixture(autouse=True)
def clear_existence_cache():
    """Wipe the module-level cache before every test."""
    with _existence_cache_lock:
        _existence_cache.clear()
    yield
    with _existence_cache_lock:
        _existence_cache.clear()


@pytest.fixture()
def mock_regista():
    from regista.testing import InMemoryRegista

    sub = InMemoryRegista()
    sub.register_workflow_file(str(Path(__file__).parent.parent / "workflows" / "phase2.yaml"))
    yield sub
    sub.close()


@pytest.fixture()
def workspace_root(tmp_path):
    return tmp_path / "factory" / "work"


@pytest.fixture()
def handoff():
    return StageHandoff(
        source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
        source_state=STATE_LOCKED,
        target_type=WORK_ITEM_TYPE_TEST_SUITE,
        link_type=LINK_TYPE_DERIVED_FROM,
        ref_field=CUSTOM_FIELD_INTERFACE_REF,
    )


# ---------------------------------------------------------------------------
# 1. Dedup lock — concurrent calls must produce exactly one downstream item
# ---------------------------------------------------------------------------


class TestDedupLock:
    def test_concurrent_calls_produce_exactly_one_downstream(
        self, mock_regista, workspace_root, handoff
    ):
        """Two threads calling _ensure_downstream_item for the same source
        concurrently must result in exactly one downstream item created."""
        config = FactoryConfig.phase2(workspace_root=workspace_root)
        source, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={"spec_section": "S1", "ac_ids": ["AC-01"]},
        )
        runtime = PipelineRuntime(sub=mock_regista, config=config)

        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def call():
            try:
                barrier.wait()  # synchronise so both threads hit the check together
                _ensure_downstream_item(runtime, source, handoff)
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=call)
        t2 = threading.Thread(target=call)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"

        page = mock_regista.query_work_items(
            work_item_types=["test_suite"],
            page_size=100,
        )
        assert len(page.items) == 1, f"Expected exactly 1 downstream item, got {len(page.items)}"
        assert page.items[0].custom_fields["interface_ref"] == str(source.work_item_id)

    def test_sequential_duplicate_calls_still_idempotent(
        self, mock_regista, workspace_root, handoff
    ):
        """Existing behaviour preserved: sequential duplicates are idempotent."""
        config = FactoryConfig.phase2(workspace_root=workspace_root)
        source, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={"spec_section": "S2", "ac_ids": ["AC-02"]},
        )
        runtime = PipelineRuntime(sub=mock_regista, config=config)

        _ensure_downstream_item(runtime, source, handoff)
        _ensure_downstream_item(runtime, source, handoff)
        _ensure_downstream_item(runtime, source, handoff)

        page = mock_regista.query_work_items(
            work_item_types=["test_suite"],
            page_size=100,
        )
        assert len(page.items) == 1


# ---------------------------------------------------------------------------
# 2. Existence cache — second call must skip paginated scan
# ---------------------------------------------------------------------------


class TestExistenceCache:
    def test_cache_hit_skips_scan(self, mock_regista, workspace_root, handoff):
        """After the first successful create the cache is populated; a second
        call must return without touching query_work_items."""
        config = FactoryConfig.phase2(workspace_root=workspace_root)
        source, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={"spec_section": "S3", "ac_ids": ["AC-03"]},
        )
        runtime = PipelineRuntime(sub=mock_regista, config=config)

        _ensure_downstream_item(runtime, source, handoff)

        # After the first call the cache entry should be set.
        from factory.scheduler import _cache_exists

        assert _cache_exists(str(source.work_item_id), WORK_ITEM_TYPE_TEST_SUITE)

        # Second call: patch query_work_items to track invocations
        original_query = mock_regista.query_work_items
        query_call_count = 0

        def counting_query(**kwargs):
            nonlocal query_call_count
            query_call_count += 1
            return original_query(**kwargs)

        mock_regista.query_work_items = counting_query
        _ensure_downstream_item(runtime, source, handoff)
        mock_regista.query_work_items = original_query

        assert query_call_count == 0, (
            f"Expected 0 query_work_items calls on cache hit, got {query_call_count}"
        )

    def test_cache_miss_still_creates(self, mock_regista, workspace_root, handoff):
        """A source with no cache entry falls through to create exactly one item."""
        config = FactoryConfig.phase2(workspace_root=workspace_root)
        source, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={"spec_section": "S4", "ac_ids": ["AC-04"]},
        )
        runtime = PipelineRuntime(sub=mock_regista, config=config)

        _ensure_downstream_item(runtime, source, handoff)

        page = mock_regista.query_work_items(
            work_item_types=["test_suite"],
            page_size=100,
        )
        assert len(page.items) == 1


# ---------------------------------------------------------------------------
# 3. Fairness — iteration order must vary across poll cycles
# ---------------------------------------------------------------------------


class TestHandoffFairness:
    def test_poll_order_varies(self, mock_regista, workspace_root):
        """_poll_handoffs must not always visit handoffs in declaration order."""
        config = FactoryConfig.phase2(workspace_root=workspace_root)
        runtime = PipelineRuntime(sub=mock_regista, config=config)

        # Intercept at _poll_handoffs level by patching random.shuffle with a
        # recorder that still does the shuffle, then sampling the order via the
        # per-handoff query calls.
        #
        # Capture the handoff list order inside the loop by patching the
        # scheduler's random.shuffle to record what was passed in.
        import random as random_mod

        import factory.scheduler as sched_mod

        shuffled_orders: list[list[str]] = []
        original_shuffle = random_mod.shuffle

        def recording_shuffle(lst, *args, **kwargs):
            original_shuffle(lst, *args, **kwargs)
            shuffled_orders.append([h.target_type for h in lst])

        with patch.object(sched_mod.random, "shuffle", side_effect=recording_shuffle):
            for _ in range(20):
                try:
                    _poll_handoffs(runtime)
                except Exception:
                    pass

        assert len(shuffled_orders) == 20

        # Across 20 shuffles the order should not be identical every time
        # (probability of all 20 being the same is negligible for len > 1).
        if len(config.stage_topology) > 1:
            unique_orders = {tuple(o) for o in shuffled_orders}
            assert len(unique_orders) > 1, (
                "Expected handoff iteration order to vary across poll cycles; "
                f"got only one unique order across 20 cycles: {unique_orders}"
            )
