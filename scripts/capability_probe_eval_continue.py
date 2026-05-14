#!/usr/bin/env python3
"""Continue capability-probe evaluation: remaining models + extra-long-timeout retries."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "capability-probe"
OUTPUT_DIR = REPO_ROOT / ".factory" / "analysis" / "capability-probe-validation" / "model-outputs"
PROMPT_DIR = REPO_ROOT / "src" / "factory" / "prompts"

# Runs that haven't been attempted yet
NEW_MODELS = [
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

# Extra-long retries for previously timed-out runs
EXTRA_RETRIES = [
    ("glm-5.1-zai", "zai-coding-plan/glm-5.1", "zhipu", "test_author", 600),
    ("glm-5.1-zai", "zai-coding-plan/glm-5.1", "zhipu", "implementer", 600),
    ("glm-5.1-ollama", "ollama-cloud/glm-5.1", "zhipu", "implementer", 600),
]


def read_file(path: Path) -> str:
    return path.read_text()


def build_prompt(role: str, spec: str, interface: str, tests: str, impl: str) -> str:
    prompt_template = read_file(PROMPT_DIR / f"{role}.md")
    context = f"\n\n---\n\n## Spec section for this work-item\n\n{spec}\n"
    if role in ("test_author", "implementer", "cross_family_reviewer", "frontier_judge"):
        context += f"\n## Locked interface\n\n```python\n{interface}\n```\n"
    if role in ("implementer", "cross_family_reviewer", "frontier_judge"):
        context += f"\n## Test suite\n\n```python\n{tests}\n```\n"
    if role in ("cross_family_reviewer", "frontier_judge"):
        context += f"\n## Implementation\n\n```python\n{impl}\n```\n"
    return prompt_template + context


def run_opencode(model: str, prompt: str, timeout: int) -> tuple[bool, str, str]:
    cmd = ["opencode", "run", "--dangerously-skip-permissions", "--model", model]
    try:
        result = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except FileNotFoundError:
        return False, "", "opencode not found"
    if result.returncode != 0:
        return False, result.stdout, result.stderr
    return True, result.stdout, result.stderr


def main() -> None:
    spec = read_file(FIXTURE_DIR / "wi_rate_limiter.md")
    interface = read_file(FIXTURE_DIR / "reference_flawed_interface.pyi")
    tests = read_file(FIXTURE_DIR / "reference_flawed_tests.py")
    impl = read_file(FIXTURE_DIR / "reference_flawed_implementation.py")

    # Extra-long retries first
    for display_name, model_id, family, role, timeout in EXTRA_RETRIES:
        out_path = OUTPUT_DIR / f"{display_name}__{role}.md"
        meta_path = OUTPUT_DIR / f"{display_name}__{role}.json"
        if out_path.exists():
            out_path.unlink()
        if meta_path.exists():
            meta_path.unlink()

        prompt = build_prompt(role, spec, interface, tests, impl)
        print(f"Extra-retry {display_name} / {role} (timeout={timeout}s) ...", end=" ", flush=True)
        start = time.time()
        success, stdout, stderr = run_opencode(model_id, prompt, timeout)
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
        time.sleep(2)

    # New models
    for display_name, model_id, family in NEW_MODELS:
        print(f"\n=== Model: {display_name} ({model_id}) ===")
        for role in ROLES:
            out_path = OUTPUT_DIR / f"{display_name}__{role}.md"
            meta_path = OUTPUT_DIR / f"{display_name}__{role}.json"
            if out_path.exists():
                print(f"  [{role}] already exists, skipping")
                continue

            prompt = build_prompt(role, spec, interface, tests, impl)
            print(f"  [{role}] invoking {model_id} ...", end=" ", flush=True)
            start = time.time()
            success, stdout, stderr = run_opencode(model_id, prompt, 300)
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
            time.sleep(2)


if __name__ == "__main__":
    main()
