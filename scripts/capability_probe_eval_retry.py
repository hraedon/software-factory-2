#!/usr/bin/env python3
"""Retry failed capability-probe evaluations with longer timeout."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "capability-probe"
OUTPUT_DIR = REPO_ROOT / ".factory" / "analysis" / "capability-probe-validation" / "model-outputs"
PROMPT_DIR = REPO_ROOT / "src" / "factory" / "prompts"

TIMEOUT = 300

RETRIES = [
    # (display_name, model_id, family, role)
    ("glm-5.1-zai", "zai-coding-plan/glm-5.1", "zhipu", "interface_architect"),
    ("glm-5.1-zai", "zai-coding-plan/glm-5.1", "zhipu", "test_author"),
    ("glm-5.1-zai", "zai-coding-plan/glm-5.1", "zhipu", "implementer"),
    ("glm-5.1-ollama", "ollama-cloud/glm-5.1", "zhipu", "interface_architect"),
    ("glm-5.1-ollama", "ollama-cloud/glm-5.1", "zhipu", "test_author"),
    ("glm-5.1-ollama", "ollama-cloud/glm-5.1", "zhipu", "implementer"),
    ("glm-5.1-ollama", "ollama-cloud/glm-5.1", "zhipu", "cross_family_reviewer"),
    ("glm-5.1-ollama", "ollama-cloud/glm-5.1", "zhipu", "frontier_judge"),
    ("kimi-k2.6-ollama", "ollama-cloud/kimi-k2.6", "moonshot", "implementer"),
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

    for display_name, model_id, family, role in RETRIES:
        out_path = OUTPUT_DIR / f"{display_name}__{role}.md"
        meta_path = OUTPUT_DIR / f"{display_name}__{role}.json"

        # Remove old failed artifacts so we can retry
        if out_path.exists():
            out_path.unlink()
        if meta_path.exists():
            meta_path.unlink()

        prompt = build_prompt(role, spec, interface, tests, impl)
        print(f"Retrying {display_name} / {role} (timeout={TIMEOUT}s) ...", end=" ", flush=True)
        start = time.time()
        success, stdout, stderr = run_opencode(model_id, prompt, TIMEOUT)
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
