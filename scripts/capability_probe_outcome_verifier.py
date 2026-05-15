"""Capability probe evaluator for the outcome_verifier role.

Runs a deliberately flawed integration assembly against target models
and scores their end-to-end verdict + routing_hint accuracy.

Usage:
    python scripts/capability_probe_outcome_verifier.py

Produces per-model outputs under:
    .factory/analysis/capability-probe-validation/outcome-verifier/
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "capability-probe"
OUTPUT_DIR = REPO_ROOT / ".factory" / "analysis" / "capability-probe-validation" / "outcome-verifier"
PROMPT_DIR = REPO_ROOT / "src" / "factory" / "prompts"

MODELS = [
    # (display_name, opencode_model_id, family)
    # Tier-A candidates for outcome_verifier (same pool as frontier_judge)
    ("kimi-k2.6-ollama", "ollama-cloud/kimi-k2.6", "moonshot"),
    ("deepseek-v4-pro-ollama", "ollama-cloud/deepseek-v4-pro", "deepseek"),
    ("glm-5.1-zai", "zai-coding-plan/glm-5.1", "zhipu"),
]


def read_file(path: Path) -> str:
    return path.read_text()


def build_prompt(spec: str, assembled_modules: str, integration_tests: str) -> str:
    prompt_template = read_file(PROMPT_DIR / "outcome_verifier.md")
    context = f"\n\n---\n\n## Spec section for this work-item\n\n{spec}\n"
    context += f"\n## Assembled modules\n\n```python\n{assembled_modules}\n```\n"
    context += f"\n## Integration tests\n\n```python\n{integration_tests}\n```\n"
    return prompt_template + context


def run_opencode(model: str, prompt: str, timeout: int = 120) -> tuple[bool, str, str]:
    cmd = [
        "opencode",
        "run",
        "--dangerously-skip-permissions",
        "--model",
        model,
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
    assembled = read_file(FIXTURE_DIR / "reference_flawed_assembly.py")
    integration_tests = read_file(FIXTURE_DIR / "reference_flawed_integration_tests.py")

    summary: dict[str, dict] = {}

    for display_name, model_id, family in MODELS:
        print(f"\n=== Model: {display_name} ({model_id}) ===")
        out_path = OUTPUT_DIR / f"{display_name}__outcome_verifier.md"
        meta_path = OUTPUT_DIR / f"{display_name}__outcome_verifier.json"

        if out_path.exists():
            print("  already exists, skipping")
            with open(meta_path) as f:
                meta = json.load(f)
            summary[display_name] = meta
            continue

        prompt = build_prompt(spec, assembled, integration_tests)
        print("  invoking ...", end=" ", flush=True)
        start = time.time()
        success, stdout, stderr = run_opencode(model_id, prompt)
        elapsed = time.time() - start
        print(f"done in {elapsed:.1f}s (success={success})")

        out_path.write_text(stdout)
        meta = {
            "model": model_id,
            "family": family,
            "role": "outcome_verifier",
            "success": success,
            "elapsed_seconds": round(elapsed, 2),
            "stderr_preview": stderr[:500] if stderr else "",
        }
        meta_path.write_text(json.dumps(meta, indent=2))
        summary[display_name] = meta

        time.sleep(2)

    summary_path = OUTPUT_DIR / "_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary written to {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
