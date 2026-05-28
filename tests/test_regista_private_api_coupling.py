from __future__ import annotations


class TestRegistaPrivateApiCoupling:
    """Smoke test for regista private API imports that factory relies on.

    If regista reorganizes _types, these imports will break the factory.
    This test gives an early, fast failure before integration tests run.
    """

    def test_actor_metadata_importable(self):
        from regista._types import ActorMetadata

        assert ActorMetadata is not None

    def test_in_memory_regista_importable(self):
        from regista.testing import InMemoryRegista

        assert InMemoryRegista is not None

    def test_drop_project_schema_importable(self):
        from regista._testing import drop_project_schema

        assert callable(drop_project_schema)
