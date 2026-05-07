from __future__ import annotations


class TestSubstratePrivateApiCoupling:
    """Smoke test for substrate private API imports that factory relies on.

    If substrate reorganizes _types, these imports will break the factory.
    This test gives an early, fast failure before integration tests run.
    """

    def test_actor_metadata_importable(self):
        from substrate._types import ActorMetadata

        assert ActorMetadata is not None

    def test_in_memory_substrate_importable(self):
        from substrate.testing import InMemorySubstrate

        assert InMemorySubstrate is not None

    def test_drop_project_schema_importable(self):
        from substrate._testing import drop_project_schema

        assert callable(drop_project_schema)
