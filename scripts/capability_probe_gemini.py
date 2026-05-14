#!/usr/bin/env python3
"""Capability probe evaluator for Gemini CLI.

Runs the same flawed-spec probe as capability_probe_eval.py but through
the Gemini CLI (with Node 24 PATH fix) instead of opencode.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "capability-probe"
OUTPUT_DIR = REPO_ROOT / ".factory" / "analysis" / "capability-probe-validation" / "model-outputs"
PROMPT_DIR = REPO_ROOT / "src" / "factory" / "prompts"

# Ensure Node 24 is on PATH for gemini CLI
_NVM_NODE_BIN = Path.home() / ".nvm" / "versions" / "node" / "v24.15.0" / "bin"

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
    context = f"\n\n---\n\n## Spec section for this work-item\n\n{spec}\n"
    if role in ("test_author", "implementer", "cross_family_reviewer", "frontier_judge"):
        context += f"\n## Locked interface\n\n```python\n{interface}\n```\n"
    if role in ("implementer", "cross_family_reviewer", "frontier_judge"):
        context += f"\n## Test suite\n\n```python\n{tests}\n```\n"
    if role in ("cross_family_reviewer", "frontier_judge"):
        context += f"\n## Implementation\n\n```python\n{impl}\n```\n"
    return prompt_template + context


def run_gemini(prompt: str, timeout: int, model_flag: str | None = None) -> tuple[bool, str, str]:
    env = os.environ.copy()
    if _NVM_NODE_BIN.is_dir():
        node_bin = str(_NVM_NODE_BIN)
        env["PATH"] = f"{node_bin}:{env.get('PATH', '')}"

    cmd = ["gemini", "-p", "-", "--yolo", "--skip-trust"]
    if model_flag:
        cmd.extend(["-m", model_flag])
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except FileNotFoundError:
        return False, "", "gemini not found"

    if result.returncode != 0:
        return False, result.stdout, result.stderr
    return True, result.stdout, result.stderr


def run_probe(display_name: str, model_flag: str | None) -> dict[str, dict]:
    spec = read_file(FIXTURE_DIR / "wi_rate_limiter.md")
    interface = read_file(FIXTURE_DIR / "reference_flawed_interface.pyi")
    tests = read_file(FIXTURE_DIR / "reference_flawed_tests.py")
    impl = read_file(FIXTURE_DIR / "reference_flawed_implementation.py")

    summary: dict[str, dict] = {}

    print(f"\n=== Model: {display_name} ===")
    for role in ROLES:
        prompt = build_prompt(role, spec, interface, tests, impl)
        out_path = OUTPUT_DIR / f"{display_name}__{role}.md"
        meta_path = OUTPUT_DIR / f"{display_name}__{role}.json"

        if out_path.exists():
            print(f"  [{role}] already exists, skipping")
            with open(meta_path) as f:
                meta = json.load(f)
            summary[role] = meta
            continue

        # timeouts based on prior probe evidence
        timeout = 600 if role in ("test_author", "implementer") else 300
        print(f"  [{role}] invoking gemini (timeout={timeout}s) ...", end=" ", flush=True)
        start = time.time()
        success, stdout, stderr = run_gemini(prompt, timeout=timeout, model_flag=model_flag)
        elapsed = time.time() - start
        print(f"done in {elapsed:.1f}s (success={success})")

        out_path.write_text(stdout)
        meta = {
            "model": display_name,
            "family": "gemini",
            "role": role,
            "success": success,
            "elapsed_seconds": round(elapsed, 2),
            "stderr_preview": stderr[:500] if stderr else "",
        }
        meta_path.write_text(json.dumps(meta, indent=2))
        summary[role] = meta

        time.sleep(2)

    return summary


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_summaries: dict[str, dict[str, dict]] = {}

    # Flash (default / no explicit -m flag)
    all_summaries["gemini-2.5-flash-cli"] = run_probe("gemini-2.5-flash-cli", model_flag=None)

    # Pro
    all_summaries["gemini-2.5-pro-cli"] = run_probe("gemini-2.5-pro-cli", model_flag="gemini-2.5-pro")

    summary_path = OUTPUT_DIR / "_summary_gemini.json"
    summary_path.write_text(json.dumps(all_summaries, indent=2))
    print(f"\nSummary written to {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
