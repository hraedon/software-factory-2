#!/usr/bin/env python3
"""Capability probe evaluator — runs flawed-spec probe against target models.

Usage:
    python scripts/capability_probe_eval.py

Produces per-model, per-role outputs under:
    .factory/analysis/capability-probe-validation/model-outputs/
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "capability-probe"
OUTPUT_DIR = REPO_ROOT / ".factory" / "analysis" / "capability-probe-validation" / "model-outputs"
PROMPT_DIR = REPO_ROOT / "src" / "factory" / "prompts"

MODELS = [
    # (display_name, opencode_model_id, family)
    ("glm-5.1-zai", "zai-coding-plan/glm-5.1", "zhipu"),
    ("kimi-k2.6-ollama", "ollama-cloud/kimi-k2.6", "moonshot"),
    ("glm-5.1-ollama", "ollama-cloud/glm-5.1", "zhipu"),
    ("deepseek-v4-pro-ollama", "ollama-cloud/deepseek-v4-pro", "deepseek"),
    ("qwen3.6-27b-ollama", "mac-studio-lms/qwen/qwen3.6-27b", "qwen"),
]

ROLES = [
    "interface_architect",
    "test_author",
    "implementer",
    "cross_family_reviewer",
    "frontier_judge",
]


def read_file(path: Path) -> str:
    return path.read_text()


def build_prompt(role: str, spec: str, interface: str, tests: str, impl: str) -> str:
    prompt_template = read_file(PROMPT_DIR / f"{role}.md")

    # Append the evaluation context
    context = f"\n\n---\n\n## Spec section for this work-item\n\n{spec}\n"

    if role in ("test_author", "implementer", "cross_family_reviewer", "frontier_judge"):
        context += f"\n## Locked interface\n\n```python\n{interface}\n```\n"

    if role in ("implementer", "cross_family_reviewer", "frontier_judge"):
        context += f"\n## Test suite\n\n```python\n{tests}\n```\n"

    if role in ("cross_family_reviewer", "frontier_judge"):
        context += f"\n## Implementation\n\n```python\n{impl}\n```\n"

    return prompt_template + context


def run_opencode(model: str, prompt: str, timeout: int = 120) -> tuple[bool, str, str]:
    cmd = [
        "opencode", "run", "--dangerously-skip-permissions",
        "--model", model,
    ]
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except FileNotFoundError:
        return False, "", "opencode not found"

    if result.returncode != 0:
        return False, result.stdout, result.stderr

    return True, result.stdout, result.stderr


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    spec = read_file(FIXTURE_DIR / "wi_rate_limiter.md")
    interface = read_file(FIXTURE_DIR / "reference_flawed_interface.pyi")
    tests = read_file(FIXTURE_DIR / "reference_flawed_tests.py")
    impl = read_file(FIXTURE_DIR / "reference_flawed_implementation.py")

    summary: dict[str, dict[str, dict]] = {}

    for display_name, model_id, family in MODELS:
        summary[display_name] = {}
        print(f"\n=== Model: {display_name} ({model_id}) ===")
        for role in ROLES:
            prompt = build_prompt(role, spec, interface, tests, impl)
            out_path = OUTPUT_DIR / f"{display_name}__{role}.md"
            meta_path = OUTPUT_DIR / f"{display_name}__{role}.json"

            if out_path.exists():
                print(f"  [{role}] already exists, skipping")
                with open(meta_path) as f:
                    meta = json.load(f)
                summary[display_name][role] = meta
                continue

            print(f"  [{role}] invoking {model_id} ...", end=" ", flush=True)
            start = time.time()
            success, stdout, stderr = run_opencode(model_id, prompt)
            elapsed = time.time() - start
            print(f"done in {elapsed:.1f}s (success={success})")

            out_path.write_text(stdout)
            meta = {
                "model": model_id,
                "family": family,
                "role": role,
                "success": success,
                "elapsed_seconds": round(elapsed, 2),
                "stderr_preview": stderr[:500] if stderr else "",
            }
            meta_path.write_text(json.dumps(meta, indent=2))
            summary[display_name][role] = meta

            # Rate-limiting: small pause between invocations
            time.sleep(2)

    # Write summary
    summary_path = OUTPUT_DIR / "_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary written to {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
