from __future__ import annotations

from factory.catalog import load_archetype
from factory.context import (
    PromptContext,
    _resolve_archetype_from_ref,
    _serialize_bundle,
    derive_context,
    render_prompt,
)


def _make_wi(mock_regista, custom_fields):
    wi, _ = mock_regista.create_work_item(
        workflow_name="software_factory",
        work_item_type="interface_spec",
        actor_id="test-creator",
        custom_fields=custom_fields,
    )
    return wi


class TestArchetypePlumbing:
    def test_archetype_loaded_from_custom_field(self, mock_regista):
        wi = _make_wi(
            mock_regista,
            {"spec_section": "s", "ac_ids": ["AC-01"], "archetype": "web-service"},
        )
        ctx = derive_context(mock_regista, wi.work_item_id, "interface_architect")
        assert ctx.archetype == "web-service"
        assert ctx.archetype_addendum
        assert "ASGI" in ctx.archetype_addendum

    def test_absent_archetype_is_backcompat(self, mock_regista):
        wi = _make_wi(mock_regista, {"spec_section": "s", "ac_ids": ["AC-01"]})
        ctx = derive_context(mock_regista, wi.work_item_id, "interface_architect")
        assert ctx.archetype == ""
        assert ctx.archetype_addendum == ""
        # The render-only injected block (distinct from the role template's prose
        # that merely references the section name) must be absent.
        assert "The contract shape below governs" not in render_prompt(ctx)

    def test_unknown_archetype_is_graceful(self, mock_regista):
        wi = _make_wi(
            mock_regista,
            {"spec_section": "s", "ac_ids": ["AC-01"], "archetype": "not-a-real-archetype"},
        )
        ctx = derive_context(mock_regista, wi.work_item_id, "interface_architect")
        assert ctx.archetype == "not-a-real-archetype"
        assert ctx.archetype_addendum == ""

    def test_archetype_addendum_changes_context_hash(self, mock_regista):
        base = _make_wi(mock_regista, {"spec_section": "s", "ac_ids": ["AC-01"]})
        web = _make_wi(
            mock_regista,
            {"spec_section": "s", "ac_ids": ["AC-01"], "archetype": "web-service"},
        )
        base_ctx = derive_context(mock_regista, base.work_item_id, "interface_architect")
        web_ctx = derive_context(mock_regista, web.work_item_id, "interface_architect")
        assert base_ctx.context_hash != web_ctx.context_hash

    def test_serialize_bundle_includes_addendum(self):
        without = _serialize_bundle(
            spec_section="s", ac_ids=["AC-01"], glossary={}, failures=[], prompt_template="t"
        )
        with_addendum = _serialize_bundle(
            spec_section="s",
            ac_ids=["AC-01"],
            glossary={},
            failures=[],
            prompt_template="t",
            archetype_addendum="expose an ASGI app",
        )
        assert without != with_addendum


class TestArchetypeFromRef:
    """Downstream roles (test_author, implementer) resolve archetype from the
    interface_spec they reference, so it need not be propagated onto every
    downstream work item."""

    def test_resolves_archetype_from_referenced_interface_spec(self, mock_regista):
        iface = _make_wi(
            mock_regista,
            {"spec_section": "s", "ac_ids": ["AC-01"], "archetype": "web-service"},
        )
        assert _resolve_archetype_from_ref(mock_regista, str(iface.work_item_id)) == "web-service"

    def test_none_when_no_ref(self, mock_regista):
        assert _resolve_archetype_from_ref(mock_regista, None) is None

    def test_none_when_ref_has_no_archetype(self, mock_regista):
        iface = _make_wi(mock_regista, {"spec_section": "s", "ac_ids": ["AC-01"]})
        assert _resolve_archetype_from_ref(mock_regista, str(iface.work_item_id)) is None


class TestRenderArchetypeContract:
    def test_contract_rendered_before_spec_section(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="interface_architect",
            spec_section="the spec",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="template",
            context_hash="h",
            prompt_template_hash="",
            extra_artifacts={},
            stub_only_deps=[],
            archetype="web-service",
            archetype_addendum="This module is a web-service deliverable. Expose an ASGI app.",
        )
        rendered = render_prompt(ctx)
        assert "## archetype_contract" in rendered
        assert "web-service" in rendered
        assert rendered.index("## archetype_contract") < rendered.index("## spec_section")


class TestWebServiceAddendumNeutrality:
    """Guards against re-coupling the contract to a named framework."""

    def test_web_service_requires_asgi_app_not_a_framework(self):
        text = load_archetype("web-service").prompt_addendum
        assert "ASGI" in text
        assert "app" in text
        # Framework neutrality sentinel — must remain a free choice, not a mandate.
        assert "Framework is your choice" in text
        assert "must use FastAPI" not in text
        assert "use `FastAPI`" not in text
