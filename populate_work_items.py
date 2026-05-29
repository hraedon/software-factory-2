#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import uuid as _uuid
from pathlib import Path

from regista import Regista

from factory.config import FactoryConfig
from factory.constants import (
    CUSTOM_FIELD_AC_IDS,
    CUSTOM_FIELD_DEPENDENCY_REFS,
    CUSTOM_FIELD_INITIATIVE_ID,
    CUSTOM_FIELD_MODULE_NAME,
    CUSTOM_FIELD_SPEC_SECTION,
    ROLE_INTERFACE_ARCHITECT,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
)

ROOT_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = ROOT_DIR / "tests" / "fixtures" / "primary-spec"
SECONDARY_DIR = ROOT_DIR / "tests" / "fixtures" / "secondary-spec"
ROUTING_STRESS_DIR = ROOT_DIR / "tests" / "fixtures" / "routing-stress"


def _extract_ac_ids_from_fixture(spec_text: str) -> list[str]:
    """Extract AC IDs from a fixture spec's heading or bulleted format."""
    ids: list[str] = []
    for line in spec_text.splitlines():
        m = re.match(r"^##\s+(AC-(?:[A-Z]+-)?\d+)\s*:?", line, re.IGNORECASE)
        if m:
            ids.append(m.group(1))
    if ids:
        return ids
    for line in spec_text.splitlines():
        stripped = line.strip()
        m = re.match(r"^- `(AC-(?:[A-Z]+-)?\d+)`:", stripped)
        if m:
            ids.append(m.group(1))
            continue
        m = re.match(r"^-\s*(AC-(?:[A-Z]+-)?\d+):", stripped)
        if m:
            ids.append(m.group(1))
    return ids

PRIMARY_ITEMS = [
    ("01-acquire_claim.md", "01", "pure-interface", ["AC-06"]),
    ("02-register_workflow.md", "02", "pure-interface", ["AC-17"]),
    ("03-create_link.md", "03", "pure-interface", ["AC-22"]),
    ("04-verify_event_errors.md", "04", "error-taxonomy", ["AC-15", "AC-26"]),
    ("05-acquire_claim_errors.md", "05", "error-taxonomy", ["AC-06"]),
    ("06-transition_errors.md", "06", "error-taxonomy", ["AC-11", "AC-12"]),
    ("07-drift_report.md", "07", "ADT-validation", ["AC-16"]),
    ("08-create_work_item.md", "08", "ADT-validation", ["AC-02"]),
    ("09-query_work_items.md", "09", "ADT-validation", ["AC-05b"]),
    ("10-dead_letter.md", "10", "ADT-validation", ["AC-14"]),
]

ADVERSARIAL_ITEMS = [
    ("AA-adversarial.md", "AA", "adversarial", ["TS-ADV-01", "TS-ADV-02"]),
]

SECONDARY_ITEMS = [
    ("spec.md", "S1", "pure-interface", ["AC-01"]),
    ("spec.md", "S2", "error-taxonomy", ["AC-02"]),
    ("spec.md", "S3", "ADT-validation", ["AC-03"]),
]

ROUTING_STRESS_ITEMS = [
    ("RS-01-type_narrowing.md", "RS1", "pure-interface", ["AC-RS1"]),
    ("RS-02-chunked_process.md", "RS2", "pure-interface", ["AC-RS2"]),
]

ALL_ITEMS = PRIMARY_ITEMS + ADVERSARIAL_ITEMS + SECONDARY_ITEMS + ROUTING_STRESS_ITEMS

_PRIMARY_DSN = "postgresql://regista_test:regista_test@localhost:5432/regista_test"
_KEY_PATH = str(ROOT_DIR / "tests" / "test_keys.json")


def _run_spec_review(spec_path: Path, config, args) -> None:
    """Run model-mediated spec review before decomposition. Exits if low-confidence gaps found."""
    from factory.spec_review import format_review_output, review_spec

    _cfg = config or FactoryConfig()

    # Build channel from decomposer-channel args (reuse same channel)
    if args.decomposer_channel:
        if args.decomposer_channel == "opencode":
            from factory.opencode_channel import OpenCodeChannel

            channel = OpenCodeChannel(_cfg)
        elif args.decomposer_channel == "claude-code":
            from factory.claude_code_channel import ClaudeCodeChannel

            channel = ClaudeCodeChannel(_cfg)
        elif args.decomposer_channel == "gemini-cli":
            from factory.gemini_channel import GeminiCLIChannel

            channel = GeminiCLIChannel(_cfg)
        else:
            print(f"ERROR: unknown channel {args.decomposer_channel}", file=sys.stderr)
            sys.exit(1)
    else:
        # Default to opencode for spec review
        from factory.opencode_channel import OpenCodeChannel

        channel = OpenCodeChannel(_cfg)

    result = review_spec(
        channel=channel,
        config=_cfg,
        spec_path=spec_path,
        confidence_threshold=args.spec_review_threshold,
    )

    output = format_review_output(result)
    print(output)

    if not result.passed and not args.force:
        print(
            f"\nERROR: {len(result.surfaced_findings)} finding(s) below confidence "
            f"threshold {args.spec_review_threshold}. Answer the questions above or "
            f"use --force to proceed anyway.",
            file=sys.stderr,
        )
        sys.exit(1)


def _resolve_spec_text(filename: str, label: str) -> str | None:
    if label.startswith("S"):
        path = SECONDARY_DIR / filename
    elif label.startswith("RS"):
        path = ROUTING_STRESS_DIR / filename
    else:
        path = FIXTURES_DIR / filename
    if not path.exists():
        return None
    return path.read_text()


def _parse_dependency_refs(spec_text: str) -> list[str]:
    deps = []
    in_deps = False
    for line in spec_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## dependencies"):
            in_deps = True
            continue
        if in_deps and stripped.startswith("##"):
            break
        if in_deps:
            m = re.match(r"^-?\s*`?interface_ref`?\s*:\s*`?([^`\s]+)`?", stripped)
            if m:
                deps.append(m.group(1))
    return deps


_SAFE_RESET_PREFIXES = ("/tmp", "/var/tmp", "/private/tmp")


def _validate_workspace_root_for_reset(ws: Path) -> None:
    if ".." in str(ws):
        raise ValueError(f"Workspace root contains '..' segments: {ws}")
    safe = False
    for prefix in _SAFE_RESET_PREFIXES:
        if str(ws).startswith(prefix):
            safe = True
            break
    if str(ws).startswith(str(ROOT_DIR)):
        safe = True
    if not safe:
        raise ValueError(
            f"Refusing to delete workspace root outside safe directories: {ws}. "
            f"Allowed prefixes: {_SAFE_RESET_PREFIXES} or project root {ROOT_DIR}"
        )


def _to_uuid(value: str | _uuid.UUID) -> _uuid.UUID:
    if isinstance(value, _uuid.UUID):
        return value
    return _uuid.UUID(value)


def _open_or_create_project(
    dsn: str,
    project: str,
    key_path: str,
    workflow_path: Path,
    reset: bool,
    workspace_root: str | None = None,
) -> Regista:
    if reset:
        from regista._testing import drop_project_schema

        try:
            drop_project_schema(dsn, project)
        except Exception:
            pass
        if workspace_root:
            ws = Path(workspace_root).resolve()
            if ws.exists():
                _validate_workspace_root_for_reset(ws)
                shutil.rmtree(ws, ignore_errors=True)
                ws.mkdir(parents=True, exist_ok=True)
            print(f"Cleaned workspace '{workspace_root}'")
        print(f"Reset project '{project}'")
    try:
        sub = Regista.create_project(dsn, project, key_path)
        print(f"Created project '{project}'")
        sub.register_workflow_file(str(workflow_path))
        return sub
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            sub = Regista(dsn, project, key_path)
            print(f"Connected to existing project '{project}'")
            sub.register_workflow_file(str(workflow_path))
            return sub
        if reset:
            raise
        print(f"ERROR: {e}", file=sys.stderr)
        print("Use --reset to drop and recreate the project.", file=sys.stderr)
        sys.exit(1)


def main():
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Populate SF2 work-items from fixture specs")
    parser.add_argument("--project", default="sf2_test", help="Regista project name")
    parser.add_argument("--dsn", default=_PRIMARY_DSN, help="Postgres connection string")
    parser.add_argument("--key-path", default=_KEY_PATH, help="Path to HMAC key file")
    parser.add_argument(
        "--reset", action="store_true", help="Drop and recreate the project before populating"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip work-items that already exist instead of re-creating",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated labels to populate (e.g. '01,AA') — skips all others",
    )
    parser.add_argument(
        "--workspace-root",
        type=str,
        default=None,
        help="Workspace directory to clean on --reset (e.g. /tmp/sf2-golden-001)",
    )
    parser.add_argument(
        "--set",
        type=str,
        default="all",
        choices=["primary", "secondary", "routing-stress", "all"],
        help="Which item set to populate (default: all)",
    )
    parser.add_argument(
        "--workflow",
        type=str,
        default=None,
        choices=["phase1", "phase2", "phase3", "phase4", "phase5"],
        help="Workflow version to register (default: inferred from --config or phase2)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help=(
            "Path to factory config YAML"
            " (overrides --dsn, --project, --key-path, --workspace-root)"
        ),
    )
    parser.add_argument(
        "--fixtures",
        type=str,
        default=None,
        help="Directory containing .md fixture files for custom golden-run sets",
    )
    parser.add_argument(
        "--spec-yaml",
        type=str,
        default=None,
        help="Path to spec.yaml to decompose into fixtures (RFC-023 decomposer)",
    )
    parser.add_argument(
        "--spec-md",
        type=str,
        default=None,
        help="Path to spec.md to decompose into fixtures (RFC-023 decomposer)",
    )
    parser.add_argument(
        "--decomposer-channel",
        type=str,
        default=None,
        choices=["opencode", "claude-code", "gemini-cli"],
        help="Model channel for RFC-023 Phase B model-driven decomposition",
    )
    parser.add_argument(
        "--decomposer-model",
        type=str,
        default=None,
        help="Model override for --decomposer-channel (e.g. fireworks-ai/.../kimi-k2p6-turbo)",
    )
    parser.add_argument(
        "--skip-lint",
        action="store_true",
        help="Skip spec lint checks (use with caution)",
    )
    parser.add_argument(
        "--strict-lint",
        action="store_true",
        help="Treat lint warnings as errors",
    )
    parser.add_argument(
        "--spec-review",
        action="store_true",
        help="Run model-mediated spec review before decomposition (catches composition gaps)",
    )
    parser.add_argument(
        "--spec-review-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for spec review findings (default 0.7)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed despite spec review surfaced findings",
    )
    parser.add_argument(
        "--archetype",
        type=str,
        default=None,
        help=(
            "Project archetype for skeleton generation"
            " (e.g. cli-tool, web-service, library-module)"
        ),
    )
    args = parser.parse_args()

    config: FactoryConfig | None = None
    if args.config:
        config = FactoryConfig.from_yaml(args.config)

    if args.workflow is not None:
        workflow_name = args.workflow
    elif config is not None:
        workflow_name = {1: "phase1", 2: "phase2", 3: "phase3", 4: "phase4", 5: "phase5"}.get(
            config.workflow_version, "phase2"
        )
    else:
        workflow_name = "phase2"

    dsn = args.dsn
    project = args.project
    key_path = args.key_path
    workspace_root = args.workspace_root
    if config is not None:
        dsn = config.dsn
        project = config.project_name
        key_path = config.hmac_key_path
        workspace_root = str(config.workspace_root)

    workflow_path = ROOT_DIR / "workflows" / f"{workflow_name}.yaml"
    if workflow_name == "phase1":
        workflow_version = 1
    elif workflow_name == "phase3":
        workflow_version = 3
    elif workflow_name == "phase4":
        workflow_version = 4
    elif workflow_name == "phase5":
        workflow_version = 5
    else:
        workflow_version = 2

    # Decompose to a temp dir first; files are copied into workspace after --reset
    _decompose_temp: Path | None = None
    if args.decomposer_channel and (args.spec_yaml or args.spec_md):
        from factory.decomposer_model import DecomposeError, decompose_from_model

        spec_path = Path(args.spec_yaml or args.spec_md)
        _decompose_temp = Path(tempfile.mkdtemp(prefix="sf2-decompose-"))
        _cfg = config or FactoryConfig()

        # Run spec review if requested
        if args.spec_review:
            _run_spec_review(spec_path, config, args)

        # Build channel from CLI arguments
        if args.decomposer_channel == "opencode":
            from factory.opencode_channel import OpenCodeChannel

            channel = OpenCodeChannel(_cfg)
        elif args.decomposer_channel == "claude-code":
            from factory.claude_code_channel import ClaudeCodeChannel

            channel = ClaudeCodeChannel(_cfg)
        elif args.decomposer_channel == "gemini-cli":
            from factory.gemini_channel import GeminiCLIChannel

            channel = GeminiCLIChannel(_cfg)
        else:
            print(f"ERROR: unknown decomposer channel {args.decomposer_channel}", file=sys.stderr)
            sys.exit(1)

        try:
            result = decompose_from_model(
                channel,
                _cfg,
                spec_path,
                spec_yaml_path=Path(args.spec_yaml) if args.spec_yaml else None,
                workspace_root=_decompose_temp,
                max_retries=2,
                model_override=args.decomposer_model,
            )
        except DecomposeError as exc:
            print(f"ERROR: model-driven decomposition failed: {exc}", file=sys.stderr)
            sys.exit(1)
        from factory.decomposer import write_fixture_files as _write_fixtures

        decomposed_dir = _decompose_temp / ".decomposed"
        _write_fixtures(result, decomposed_dir)
        print(f"Decomposed {spec_path.name} → {len(result.modules)} modules in {decomposed_dir}")
        md_files = sorted(decomposed_dir.glob("*.md"))
        items = []
        for f in md_files:
            ac_ids = _extract_ac_ids_from_fixture(f.read_text()) or ["AC-01"]
            items.append((f.name, f.stem, "custom", ac_ids))
    elif args.spec_yaml:
        from factory.decomposer import (
            decompose_from_spec_yaml as _decompose_yaml,
        )
        from factory.decomposer import (
            write_fixture_files as _write_fixtures,
        )

        spec_path = Path(args.spec_yaml)

        # Run spec review if requested
        if args.spec_review:
            _run_spec_review(spec_path, config, args)

        _decompose_temp = Path(tempfile.mkdtemp(prefix="sf2-decompose-"))
        result = _decompose_yaml(spec_path)
        decomposed_dir = _decompose_temp / ".decomposed"
        _write_fixtures(result, decomposed_dir)
        print(f"Decomposed {spec_path.name} → {len(result.modules)} modules in {decomposed_dir}")
        md_files = sorted(decomposed_dir.glob("*.md"))
        items = []
        for f in md_files:
            ac_ids = _extract_ac_ids_from_fixture(f.read_text()) or ["AC-01"]
            items.append((f.name, f.stem, "custom", ac_ids))
    elif args.spec_md:
        from factory.decomposer import (
            decompose_from_spec_md as _decompose_md,
        )
        from factory.decomposer import (
            write_fixture_files as _write_fixtures,
        )

        spec_path = Path(args.spec_md)

        # Run spec review if requested
        if args.spec_review:
            _run_spec_review(spec_path, config, args)

        _decompose_temp = Path(tempfile.mkdtemp(prefix="sf2-decompose-"))
        result = _decompose_md(spec_path)
        decomposed_dir = _decompose_temp / ".decomposed"
        _write_fixtures(result, decomposed_dir)
        print(f"Decomposed {spec_path.name} → {len(result.modules)} modules in {decomposed_dir}")
        md_files = sorted(decomposed_dir.glob("*.md"))
        items = []
        for f in md_files:
            ac_ids = _extract_ac_ids_from_fixture(f.read_text()) or ["AC-01"]
            items.append((f.name, f.stem, "custom", ac_ids))
    elif args.fixtures:
        fixtures_dir = Path(args.fixtures)
        md_files = sorted(fixtures_dir.glob("*.md"))
        items = []
        for f in md_files:
            ac_ids = _extract_ac_ids_from_fixture(f.read_text()) or ["AC-01"]
            items.append((f.name, f.stem, "custom", ac_ids))
    elif args.set == "primary":
        items = PRIMARY_ITEMS + ADVERSARIAL_ITEMS
    elif args.set == "secondary":
        items = SECONDARY_ITEMS
    elif args.set == "routing-stress":
        items = ROUTING_STRESS_ITEMS
    else:
        items = ALL_ITEMS

    only_labels = set(args.only.split(",")) if args.only else None

    sub = _open_or_create_project(dsn, project, key_path, workflow_path, args.reset, workspace_root)

    # Copy decomposed files into the (now-clean) workspace
    if _decompose_temp is not None and workspace_root:
        ws_root = Path(workspace_root)
        ws_root.mkdir(parents=True, exist_ok=True)
        dest_dir = ws_root / ".decomposed"
        shutil.copytree(_decompose_temp / ".decomposed", dest_dir, dirs_exist_ok=True)
        shutil.rmtree(_decompose_temp, ignore_errors=True)

    _config = FactoryConfig()
    if config is not None:
        _config = config
    actor_id = "factory-setup"

    fixtures_dir_custom = Path(args.fixtures) if args.fixtures else None
    if fixtures_dir_custom is not None and workspace_root:
        fixture_reqs = fixtures_dir_custom / "requirements.txt"
        if fixture_reqs.exists():
            ws_root = Path(workspace_root)
            ws_root.mkdir(parents=True, exist_ok=True)
            dest = ws_root / "requirements.txt"
            dest.write_text(fixture_reqs.read_text())
            print(f"  Copied {fixture_reqs} -> {dest}")

    if args.archetype and workspace_root:
        from factory.catalog import apply_skeleton, load_archetype, validate_archetype

        archetype = load_archetype(args.archetype)
        config_phases = [_config.workflow_version] if _config else [2]
        config_roles = list(_config.roles.keys()) if _config and _config.roles else []
        warnings = validate_archetype(archetype, config_phases, config_roles)
        for w in warnings:
            print(f"  WARNING: {w}", file=sys.stderr)
        ws_root = Path(workspace_root)
        ws_root.mkdir(parents=True, exist_ok=True)
        created_files = apply_skeleton(archetype, ws_root, project)
        print(f"  Applied archetype '{args.archetype}': {len(created_files)} files created")

    if not args.skip_lint:
        from factory.spec_lint import format_lint_results, spec_lint

        lint_results: list[tuple[str, object]] = []
        for filename, label, _shape, _ac_ids in items:
            if only_labels is not None and label not in only_labels:
                continue
            if fixtures_dir_custom is not None:
                spec_path = fixtures_dir_custom / filename
                spec_text = spec_path.read_text() if spec_path.exists() else None
            else:
                spec_text = _resolve_spec_text(filename, label)
            if spec_text is None:
                continue
            result = spec_lint(filename, spec_text)
            lint_results.append((filename, result))

        if lint_results:
            report = format_lint_results(lint_results)
            print(report)

            if args.strict_lint:
                any_finding = any(r.findings for _, r in lint_results)
                if any_finding:
                    print(
                        "\n--strict-lint: treating warnings as errors. Aborting.", file=sys.stderr
                    )
                    sys.exit(1)
            else:
                any_error = any(r.errors for _, r in lint_results)
                if any_error:
                    print(
                        "\nSpec lint found errors. Fix or use --skip-lint to override.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
    else:
        print("WARNING: --skip-lint used; spec lint checks bypassed")

    created = []
    skipped = 0
    label_to_id: dict[str, str] = {}
    pending_deps: dict[str, list[str]] = {}
    dep_name_to_label: dict[str, str] = {}
    from factory.initiative import generate_initiative_id

    initiative_id = generate_initiative_id()
    for filename, label, shape, ac_ids in items:
        if only_labels is not None and label not in only_labels:
            skipped += 1
            continue
        if fixtures_dir_custom is not None:
            spec_path = fixtures_dir_custom / filename
            spec_text = spec_path.read_text() if spec_path.exists() else None
        else:
            spec_text = _resolve_spec_text(filename, label)
            # Fallback: check workspace .decomposed dir for model-decomposed fixtures
            if spec_text is None and workspace_root:
                ws_decomposed = Path(workspace_root) / ".decomposed" / filename
                if ws_decomposed.exists():
                    spec_text = ws_decomposed.read_text()
        if spec_text is None:
            print(f"  [{label}] SKIP: {filename} not found")
            continue
        dep_names = _parse_dependency_refs(spec_text)
        module_name = label.removeprefix("wi_")
        custom_fields = {
            CUSTOM_FIELD_SPEC_SECTION: spec_text,
            CUSTOM_FIELD_AC_IDS: ac_ids,
            CUSTOM_FIELD_MODULE_NAME: module_name,
            CUSTOM_FIELD_INITIATIVE_ID: initiative_id,
            "shape": shape,
        }
        try:
            wi, _ = sub.create_work_item(
                workflow_name=_config.workflow_name,
                work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
                actor_id=actor_id,
                custom_fields=custom_fields,
            )
            created.append((label, shape, str(wi.work_item_id)))
            label_to_id[label] = str(wi.work_item_id)
            bare_label = label.removeprefix("wi_")
            dep_name_to_label[bare_label] = label
            dep_name_to_label[label] = label
            print(f"  [{label}] {shape:20s} {wi.work_item_id}")
            if dep_names:
                pending_deps[str(wi.work_item_id)] = dep_names
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print(f"  [{label}] {shape:20s} (already exists, skipping)")
                skipped += 1
            else:
                raise

    if pending_deps:
        name_to_id: dict[str, str] = {}
        for dep_label_name in label_to_id:
            bare = dep_label_name.removeprefix("wi_")
            name_to_id[bare] = label_to_id[dep_label_name]
            name_to_id[dep_label_name] = label_to_id[dep_label_name]
        deps_actor_id = ROLE_INTERFACE_ARCHITECT
        deps_actor_metadata = {"role": ROLE_INTERFACE_ARCHITECT}
        for wi_id_str, dep_names in pending_deps.items():
            resolved = []
            for dn in dep_names:
                rid = name_to_id.get(dn)
                if rid:
                    resolved.append(rid)
                else:
                    print(f"  WARNING: dependency '{dn}' not resolved for {wi_id_str}")
            if resolved:
                sub.transition(
                    work_item_id=_uuid.UUID(wi_id_str),
                    transition_name="claim",
                    actor_id=deps_actor_id,
                    actor_metadata=deps_actor_metadata,
                    custom_fields={CUSTOM_FIELD_DEPENDENCY_REFS: resolved},
                )
                sub.transition(
                    work_item_id=_uuid.UUID(wi_id_str),
                    transition_name="release",
                    actor_id=deps_actor_id,
                    actor_metadata=deps_actor_metadata,
                )
                print(f"  [{wi_id_str[:8]}] dependency_refs updated: {resolved}")

    print(
        f"\nCreated {len(created)} work-items, skipped {skipped} existing, "
        f"in project '{project}' (workflow_version={workflow_version})"
    )
    print("\nSummary:")
    for label, shape, wi_id in created:
        print(f"  {label}  {shape:20s}  {wi_id}")
    sub.close()


if __name__ == "__main__":
    main()
