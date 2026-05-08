from __future__ import annotations

import json
import re


def extract_artifact_from_output(content: str) -> str | None:
    match = re.search(r"```python\s*\n(.*?)```", content, re.DOTALL)
    if match:
        return match.group(1).rstrip()
    match = re.search(r"```\s*\n(.*?)```", content, re.DOTALL)
    if match:
        return match.group(1).rstrip()
    for i, line in enumerate(content.split("\n")):
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
    for m in re.finditer(r"\{[\s\S]*?\}", content):
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            continue
    return None
