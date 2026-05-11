from __future__ import annotations

import json
import re

_MAX_FALLBACK_LINES = 200
_CODE_FENCE_PATTERN = re.compile(r"```(?:\w+)?\s*\n(.*?)```", re.DOTALL)
_PYTHON_FENCE_PATTERN = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)


def extract_artifact_from_output(content: str) -> str | None:
    python_blocks = list(_PYTHON_FENCE_PATTERN.finditer(content))
    if python_blocks:
        return python_blocks[-1].group(1).rstrip()
    all_blocks = list(_CODE_FENCE_PATTERN.finditer(content))
    if all_blocks:
        return all_blocks[-1].group(1).rstrip()
    for i, line in enumerate(content.split("\n")):
        if i >= _MAX_FALLBACK_LINES:
            break
        stripped = line.strip()
        if stripped.startswith(("from ", "import ", "class ", "def ", "@", "# ")):
            return "\n".join(content.split("\n")[i:]).rstrip()
    return None


def extract_json_from_output(content: str) -> dict | None:
    match = re.search(r"```json\s*\n(.*?)```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    decoder = json.JSONDecoder()
    text = content
    while text:
        text = text.lstrip()
        if not text:
            break
        idx = text.find("{")
        if idx == -1:
            break
        try:
            obj, end = decoder.raw_decode(text, idx)
            if isinstance(obj, dict):
                return obj
            text = text[end:]
        except json.JSONDecodeError:
            text = text[idx + 1 :]
    return None
