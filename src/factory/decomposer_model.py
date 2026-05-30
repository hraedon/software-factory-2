from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
import yaml

from factory.channel import Channel
from factory.config import FactoryConfig
from factory.constants import ROLE_INTERFACE_ARCHITECT
from factory.decomposer import AC_BOOT_ID, DecomposedModule, DecompositionResult


@dataclass(frozen=True)
class DecompositionGateResult:
    passed: bool
    gate_name: str
    diagnostic_kind: str = ""
    diagnostic: str = ""


class DecomposeError(Exception):
    """Raised when model-driven decomposition fails irrevocably."""


log = structlog.get_logger()


def _load_spec_text(spec_path: Path, spec_yaml_path: Path | None) -> str:
    """Load spec text from Markdown or YAML path."""
    if not spec_path.exists():
        return "# Test spec\n\nNo content.\n"
    if spec_path.suffix in (".yaml", ".yml"):
        text = spec_path.read_text()
        data = yaml.safe_load(text)
        return json.dumps(data, indent=2, ensure_ascii=False)
    return spec_path.read_text()


def _invoke_decomposer_channel(
    channel: Channel,
    config: FactoryConfig,
    spec_path: Path,
    spec_yaml_path: Path | None,
    workspace_root: Path,
    prior_failures: list[DecompositionGateResult] | None = None,
    model_override: str | None = None,
) -> str:
    """Invoke the model channel for decomposition; return raw output text."""
    spec_data: dict[str, Any] | None = None
    spec_md_text: str | None = None
    if spec_yaml_path is not None and spec_yaml_path.exists():
        spec_data = _render_yaml_for_prompt(spec_yaml_path)
    elif spec_path.suffix in (".yaml", ".yml") and spec_path.exists():
        spec_data = _render_yaml_for_prompt(spec_path)
    else:
        spec_md_text = spec_path.read_text() if spec_path.exists() else ""

    prompt = _build_structured_prompt(spec_data, spec_md_text, prior_failures=prior_failures)

    outputs_dir = workspace_root / ".decomposed" / "attempts"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    timeout = 120

    log.info(
        "decomposer.invoke",
        spec=str(spec_path),
        channel=channel.name,
        timeout=timeout,
        model=model_override,
    )
    result = channel.invoke(
        role=ROLE_INTERFACE_ARCHITECT,
        prompt=prompt,
        outputs_dir=outputs_dir,
        timeout=timeout,
        model_override=model_override,
    )

    if not result.success:
        raise DecomposeError(
            f"Decomposer channel failed: {result.error_message} "
            f"(exit_code={result.exit_code}, timed_out={result.timed_out})"
        )

    # Discover artifact in outputs_dir
    candidates = (
        list(outputs_dir.glob("*.json"))
        + list(outputs_dir.glob("*.md"))
        + list(outputs_dir.glob("*.txt"))
    )
    if candidates:
        # Prefer files named decomposer or artifact
        for c in candidates:
            if "decomposer" in c.name.lower() or "artifact" in c.name.lower():
                return c.read_text()
        return candidates[0].read_text()

    # Fallback: look for a stdout capture if the channel didn't produce a file
    stdout_path = outputs_dir / "raw_stdout.txt"
    if stdout_path.exists():
        return stdout_path.read_text()

    # Last resort: the channel's artifact_path is a directory; list and return empty
    raise DecomposeError(f"Decomposer channel succeeded but no artifact found in {outputs_dir}")


def _extract_decomposition_json(raw_text: str) -> dict:
    """Extract JSON object from model output, or raise DecomposeError."""
    # Try last fenced JSON block
    json_match = re.findall(r"```(?:json)?\s*\n(.*?)\n```", raw_text, re.DOTALL)
    if json_match:
        last = json_match[-1].strip()
    else:
        last = raw_text.strip()

    # Try to find the first `{` that starts a valid JSON object
    try:
        data = json.loads(last)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Try scanning via raw_decode
    decoder = json.JSONDecoder()
    idx = 0
    text = last
    while idx < len(text):
        char = text[idx]
        if char in " \t\n\r":
            idx += 1
            continue
        if char == "{":
            try:
                obj, end = decoder.raw_decode(text, idx)
                if isinstance(obj, dict):
                    return obj
                idx = end
                continue
            except json.JSONDecodeError:
                pass
        idx += 1

    raise DecomposeError("Could not extract JSON decomposition from model output")


def _validate_decomposition(data: dict, *, phase_b: bool = True) -> list[DecompositionGateResult]:
    """Run mechanical gates on the decomposition result.

    When ``phase_b=True`` the semantic naming gate is enforced.
    When ``phase_b=False`` (Phase A fallback) only structural gates run.
    """
    results: list[DecompositionGateResult] = []

    # Gate 1: schema shape
    if not isinstance(data, dict):
        results.append(
            DecompositionGateResult(
                passed=False,
                gate_name="decomposition_schema",
                diagnostic_kind="schema",
                diagnostic="Top-level value is not a JSON object",
            )
        )
        return results

    modules = data.get("modules")
    if not isinstance(modules, list) or len(modules) == 0:
        results.append(
            DecompositionGateResult(
                passed=False,
                gate_name="decomposition_schema",
                diagnostic_kind="schema",
                diagnostic="'modules' must be a non-empty list",
            )
        )
        return results

    # Gate 2: each module has required fields
    required_fields = {"module_name", "fr_id", "fr_text", "ac_ids", "dependency_fr_ids"}
    for i, mod in enumerate(modules):
        missing = required_fields - set(mod.keys())
        if missing:
            results.append(
                DecompositionGateResult(
                    passed=False,
                    gate_name="decomposition_schema",
                    diagnostic_kind="schema",
                    diagnostic=f"Module[{i}] missing fields: {sorted(missing)}",
                )
            )

    if any(not r.passed for r in results):
        return results

    # Gate 3: unique module_name
    names = [m["module_name"] for m in modules]
    seen = set()
    dupes = set()
    for n in names:
        if n in seen:
            dupes.add(n)
        seen.add(n)
    if dupes:
        results.append(
            DecompositionGateResult(
                passed=False,
                gate_name="decomposition_validation",
                diagnostic_kind="duplicate_module_name",
                diagnostic=f"Duplicate module_name values: {sorted(dupes)}",
            )
        )

    # Gate 3b: semantic naming (Phase B only)
    if phase_b:
        forbidden_suffixes = {"module", "handler", "service", "utils", "manager", "processor"}
        for m in modules:
            mn = m["module_name"]
            if re.fullmatch(r"fr\d+", mn, re.IGNORECASE):
                results.append(
                    DecompositionGateResult(
                        passed=False,
                        gate_name="semantic_naming",
                        diagnostic_kind="fr_shaped_name",
                        diagnostic=f"Module name '{mn}' is FR-shaped (forbidden in Phase B)",
                    )
                )
            if any(mn.endswith("_" + suffix) or mn == suffix for suffix in forbidden_suffixes):
                results.append(
                    DecompositionGateResult(
                        passed=False,
                        gate_name="semantic_naming",
                        diagnostic_kind="generic_suffix",
                        diagnostic=f"Module name '{mn}' uses forbidden generic suffix",
                    )
                )
            if len(mn) > 40 or not re.fullmatch(r"[a-z][a-z0-9_]*", mn):
                results.append(
                    DecompositionGateResult(
                        passed=False,
                        gate_name="semantic_naming",
                        diagnostic_kind="invalid_name",
                        diagnostic=(
                            f"Module name '{mn}' must be snake_case, "
                            "<=40 chars, start with lowercase letter"
                        ),
                    )
                )

    # Gate 4: acyclic dependency graph
    # Phase C allows multiple modules to share an fr_id (e.g. shared substrate
    # + endpoint module both claim FR-01). Cycle detection must operate on
    # module_name (unique) not fr_id (potentially shared), otherwise a module
    # depending on another module with the same fr_id looks like a self-cycle.
    fr_ids = {m["fr_id"] for m in modules}

    fr_to_modules: dict[str, list[str]] = {}
    for m in modules:
        fr_to_modules.setdefault(m["fr_id"], []).append(m["module_name"])

    for m in modules:
        fr_id = m["fr_id"]
        deps = m.get("dependency_fr_ids", [])
        bad_deps = [d for d in deps if d not in fr_ids]
        if bad_deps:
            results.append(
                DecompositionGateResult(
                    passed=False,
                    gate_name="decomposition_validation",
                    diagnostic_kind="bad_dependency",
                    diagnostic=f"Module {fr_id} references unknown fr_ids: {bad_deps}",
                )
            )

    module_deps: dict[str, set[str]] = {m["module_name"]: set() for m in modules}
    for m in modules:
        mn = m["module_name"]
        for dep_fr in m.get("dependency_fr_ids", []):
            if dep_fr not in fr_ids:
                continue
            for dep_mod in fr_to_modules.get(dep_fr, []):
                if dep_mod != mn:
                    module_deps[mn].add(dep_mod)

    # Cycle detection (DFS) on module_name graph
    def _has_cycle(node: str, visiting: set[str], visited: set[str]) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in module_deps.get(node, []):
            if _has_cycle(child, visiting, visited):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    for mn in module_deps:
        if _has_cycle(mn, set(), set()):
            results.append(
                DecompositionGateResult(
                    passed=False,
                    gate_name="decomposition_validation",
                    diagnostic_kind="cyclic_dependency",
                    diagnostic=f"Cyclic dependency detected involving module {mn}",
                )
            )
            break

    # Gate 5: module size constraints (soft cap only)
    for m in modules:
        acs = m.get("ac_ids", [])
        if len(acs) > 12:
            results.append(
                DecompositionGateResult(
                    passed=False,
                    gate_name="decomposition_validation",
                    diagnostic_kind="module_too_large",
                    diagnostic=f"Module {m['fr_id']} has {len(acs)} ACs (max 12)",
                )
            )
    for m in modules:
        acs = m.get("ac_ids", [])
        is_sub = m.get("is_substrate", False)
        if len(acs) < 2 and not is_sub:
            # Soft-warning — count as pass with diagnostic to avoid blocking natural 1-AC modules
            results.append(
                DecompositionGateResult(
                    passed=True,
                    gate_name="decomposition_validation",
                    diagnostic_kind="module_small",
                    diagnostic=f"Module {m['fr_id']} has only {len(acs)} AC(s)",
                )
            )

    # Gate 5b: is_substrate false-positive guard
    # Build fr_id -> list of dependent module_names for the dependents check
    fr_to_dependents: dict[str, list[str]] = {m["fr_id"]: [] for m in modules}
    for m in modules:
        for dep_fr in m.get("dependency_fr_ids", []):
            if dep_fr in fr_to_dependents:
                fr_to_dependents[dep_fr].append(m["module_name"])
    for m in modules:
        is_sub = m.get("is_substrate", False)
        acs = m.get("ac_ids", [])
        if is_sub:
            # A substrate module must have no feature ACs
            if acs:
                results.append(
                    DecompositionGateResult(
                        passed=False,
                        gate_name="substrate_validation",
                        diagnostic_kind="substrate_has_feature_acs",
                        diagnostic=(
                            f"Module {m['module_name']} is marked is_substrate but has "
                            f"feature ACs {acs} — substrate modules must not own feature ACs"
                        ),
                    )
                )
            # A substrate module must have ≥2 dependents
            dependents = fr_to_dependents.get(m["fr_id"], [])
            if len(dependents) < 2:
                results.append(
                    DecompositionGateResult(
                        passed=False,
                        gate_name="substrate_validation",
                        diagnostic_kind="substrate_few_dependents",
                        diagnostic=(
                            f"Module {m['module_name']} is marked is_substrate but has "
                            f"only {len(dependents)} dependent(s) — need ≥2, or inline it"
                        ),
                    )
                )
        else:
            # Non-substrate module with empty ac_ids is suspicious
            # (back-compat: model may not have set is_substrate)
            if not acs:
                # Auto-detect: if ≥2 dependents, treat as implicit substrate
                dependents = fr_to_dependents.get(m["fr_id"], [])
                if len(dependents) >= 2:
                    results.append(
                        DecompositionGateResult(
                            passed=True,
                            gate_name="substrate_validation",
                            diagnostic_kind="implicit_substrate",
                            diagnostic=(
                                f"Module {m['module_name']} has empty ac_ids and "
                                f"{len(dependents)} dependents — implied is_substrate=true"
                            ),
                        )
                    )
                else:
                    results.append(
                        DecompositionGateResult(
                            passed=False,
                            gate_name="substrate_validation",
                            diagnostic_kind="empty_ac_ids",
                            diagnostic=(
                                f"Module {m['module_name']} has empty ac_ids but is "
                                f"not marked is_substrate — each module must own at least "
                                f"one AC or be an explicit substrate"
                            ),
                        )
                    )

    # Gate 6: Phase B.5 — composition (orphaned module detection)
    # A module is orphaned if no other module lists it in dependency_fr_ids.
    # Root modules (no dependencies) are not orphaned — they're entry points.
    # Leaf modules (no dependents) that also have no ACs referencing external
    # concepts are suspicious but not blocking (they may be standalone utilities).
    if phase_b:
        referenced: set[str] = set()
        for m in modules:
            for dep in m.get("dependency_fr_ids", []):
                referenced.add(dep)
        for m in modules:
            fr_id = m["fr_id"]
            has_deps = bool(m.get("dependency_fr_ids"))
            is_referenced = fr_id in referenced
            if has_deps and not is_referenced:
                # Module depends on others but nothing depends on it — orphaned leaf
                results.append(
                    DecompositionGateResult(
                        passed=True,  # warning, not failure
                        gate_name="composition_check",
                        diagnostic_kind="orphaned_module",
                        diagnostic=(
                            f"Module {fr_id} ({m.get('module_name', '?')}) depends on "
                            f"{m['dependency_fr_ids']} but no other module depends on it. "
                            f"If this module has a runtime lifecycle (scheduler, background job), "
                            f"it may need a wiring AC."
                        ),
                    )
                )

    # If no failures so far, one pass result
    if not any(not r.passed for r in results):
        results.append(
            DecompositionGateResult(
                passed=True,
                gate_name="decomposition_validation",
            )
        )

    return results


def _render_yaml_for_prompt(spec_yaml_path: Path) -> dict[str, Any]:
    """Load a spec.yaml and render the structured data for the decomposer prompt."""
    raw = spec_yaml_path.read_text()
    data = yaml.safe_load(raw)
    return data


def _build_structured_prompt(
    spec_data: dict[str, Any] | None,
    spec_md_text: str | None,
    glossary: dict[str, str] | None = None,
    prior_failures: list[DecompositionGateResult] | None = None,
) -> str:
    """Build a decomposer prompt from either structured YAML data or markdown text."""
    parts: list[str] = []
    # Re-read the prompt template each time
    prompt_path = Path(__file__).parent / "prompts" / "decomposer.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    template = prompt_path.read_text()
    parts.append(template)
    parts.append("")
    parts.append("---")
    parts.append("")

    if spec_data is not None:
        parts.append("## spec_yaml")
        parts.append("")
        parts.append("```yaml")
        parts.append(yaml.dump(spec_data, allow_unicode=True, sort_keys=False))
        parts.append("```")
        parts.append("")
    elif spec_md_text is not None:
        parts.append("## spec_text")
        parts.append("")
        parts.append("```")
        parts.append(spec_md_text)
        parts.append("```")
        parts.append("")

    if glossary:
        parts.append("## glossary")
        parts.append("")
        for term, definition in sorted(glossary.items()):
            parts.append(f"- **{term}**: {definition}")
        parts.append("")

    if prior_failures:
        parts.append("## prior_failures")
        parts.append("")
        for entry in prior_failures:
            parts.append(
                f"- attempt {entry.gate_name}: {entry.diagnostic_kind} — {entry.diagnostic}"
            )
        parts.append("")

    return "\n".join(parts)


def _decompose_phase_a(spec_path: Path, spec_yaml_path: Path | None) -> DecompositionResult:
    """Fall back to Phase A deterministic decomposition."""
    from factory.decomposer import decompose_from_spec_md, decompose_from_spec_yaml

    if spec_yaml_path is not None and spec_yaml_path.exists():
        return decompose_from_spec_yaml(spec_yaml_path)
    if spec_path.suffix in (".yaml", ".yml") and spec_path.exists():
        return decompose_from_spec_yaml(spec_path)
    return decompose_from_spec_md(spec_path)


def decompose_from_model(
    channel: Channel,
    config: FactoryConfig,
    spec_path: Path,
    spec_yaml_path: Path | None,
    workspace_root: Path,
    max_retries: int = 2,
    model_override: str | None = None,
) -> DecompositionResult:
    """Model-driven decomposition with mechanical gate validation and retry.

    On failure, retries the channel up to ``max_retries`` times. If all
    attempts fail validation, raises ``DecomposeError``.
    """
    # Load spec data once for AC condition lookup
    spec_yaml_file = (
        spec_yaml_path
        if spec_yaml_path and spec_yaml_path.exists()
        else (spec_path if spec_path.suffix in (".yaml", ".yml") and spec_path.exists() else None)
    )
    spec_data: dict[str, Any] | None = None
    if spec_yaml_file is not None:
        spec_data = _render_yaml_for_prompt(spec_yaml_file)

    last_diagnostics: list[DecompositionGateResult] = []
    for attempt in range(max_retries + 1):
        log.info("decomposer.attempt", attempt=attempt, max_retries=max_retries)
        raw_text = _invoke_decomposer_channel(
            channel,
            config,
            spec_path,
            spec_yaml_path,
            workspace_root,
            prior_failures=last_diagnostics or None,
            model_override=model_override,
        )
        try:
            data = _extract_decomposition_json(raw_text)
        except DecomposeError as exc:
            last_diagnostics = [
                DecompositionGateResult(
                    passed=False,
                    gate_name="decomposition_extraction",
                    diagnostic_kind="extraction",
                    diagnostic=str(exc),
                )
            ]
            continue

        diagnostics = _validate_decomposition(data, phase_b=True)
        last_diagnostics = diagnostics
        if all(r.passed for r in diagnostics):
            # Build AC lookup from spec data to enrich model's ac_ids with condition text
            ac_lookup: dict[str, str] = {}
            if spec_data is not None:
                for ac in spec_data.get("acceptance_criteria", []):
                    ac_lookup[ac["id"]] = ac.get("condition", ac.get("text", ""))
            # Build FR-ID → module_names lookup for dependency resolution.
            # Phase C allows multiple modules to share an fr_id (e.g. shared
            # substrate + endpoint both claim FR-01). When resolving deps, a
            # module listing its own fr_id means "depends on the OTHER module(s)
            # with that fr_id", not itself.
            fr_to_modules_map: dict[str, list[str]] = {}
            for mod in data.get("modules", []):
                fr_to_modules_map.setdefault(mod["fr_id"], []).append(mod["module_name"])
            # Determine implicit substrate: empty ac_ids + ≥2 dependents
            fr_to_dependent_count: dict[str, int] = {}
            for mod in data.get("modules", []):
                for dep_fr in mod.get("dependency_fr_ids", []):
                    fr_to_dependent_count[dep_fr] = fr_to_dependent_count.get(dep_fr, 0) + 1

            modules = []
            for m in data.get("modules", []):
                is_substrate = m.get("is_substrate", False)
                ac_ids_raw = m.get("ac_ids", [])
                # Implicit substrate detection: empty ac_ids + ≥2 dependents
                if not is_substrate and not ac_ids_raw:
                    dep_count = fr_to_dependent_count.get(m["fr_id"], 0)
                    if dep_count >= 2:
                        is_substrate = True
                        log.info(
                            "decomposer.implicit_substrate",
                            module=m["module_name"],
                            dependents=dep_count,
                        )
                # Substrate modules receive the system-owned AC-BOOT-01
                if is_substrate and not ac_ids_raw:
                    ac_entries = [{"id": AC_BOOT_ID, "condition": ""}]
                else:
                    ac_entries = [
                        {"id": ac, "condition": ac_lookup.get(ac, "")} for ac in ac_ids_raw
                    ]
                modules.append(
                    DecomposedModule(
                        module_name=m["module_name"],
                        fr_id=m["fr_id"],
                        fr_text=m["fr_text"],
                        ac_entries=ac_entries,
                        dependency_fr_ids=[
                            dep_mod
                            for d in m.get("dependency_fr_ids", [])
                            for dep_mod in fr_to_modules_map.get(d, [d])
                            if dep_mod != m["module_name"]
                        ],
                        glossary={},
                        is_substrate=is_substrate,
                    )
                )
            return DecompositionResult(
                source=str(spec_path),
                source_hash="model-driven",
                modules=modules,
                glossary={},
                meta=data.get("rationale", ""),
            )

    # Phase B failed after max_retries. Fall back to Phase A deterministic.
    log.info(
        "decomposer.phase_b_failed",
        max_retries=max_retries,
        diagnostics=[d.diagnostic for d in last_diagnostics if not d.passed],
        fallback="phase_a",
    )
    try:
        return _decompose_phase_a(spec_path, spec_yaml_path)
    except Exception as exc:
        raise DecomposeError(
            f"Decomposition failed after {max_retries + 1} attempts (Phase B) "
            f"and Phase A fallback also failed: {exc}. "
            f"Last Phase B diagnostics: {[d.diagnostic for d in last_diagnostics if not d.passed]}"
        ) from exc
