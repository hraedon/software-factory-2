from __future__ import annotations

from factory.claude_code_channel import _extract_artifact_from_output, _extract_json_from_output


class TestExtractArtifact:
    def test_python_fenced_block(self):
        content = 'Here is the code:\n```python\ndef foo(x: int) -> str: ...\n```\nDone.'
        result = _extract_artifact_from_output(content)
        assert result is not None
        assert "def foo" in result

    def test_plain_fenced_block(self):
        content = '```\ndef foo(x: int) -> str: ...\n```\n'
        result = _extract_artifact_from_output(content)
        assert result is not None
        assert "def foo" in result

    def test_no_fenced_block_starts_with_def(self):
        content = "def foo(x: int) -> str: ...\n"
        result = _extract_artifact_from_output(content)
        assert result is not None
        assert "def foo" in result

    def test_no_artifact_returns_none(self):
        content = "This is just text with no code.\n"
        result = _extract_artifact_from_output(content)
        assert result is None

    def test_starts_with_from_import(self):
        content = "from typing import Union\n\ndef foo() -> int: ...\n"
        result = _extract_artifact_from_output(content)
        assert result is not None
        assert "from typing" in result

    def test_starts_with_class(self):
        content = "class Foo:\n    x: int\n"
        result = _extract_artifact_from_output(content)
        assert result is not None
        assert "class Foo" in result

    def test_multiple_fenced_blocks_picks_python(self):
        content = (
            "First block:\n```json\n{\"status\": \"ok\"}\n```\n"
            "Second:\n```python\ndef foo() -> int: ...\n```\n"
        )
        result = _extract_artifact_from_output(content)
        assert result is not None
        assert "def foo" in result

    def test_whitespace_only_returns_none(self):
        result = _extract_artifact_from_output("   \n  \n")
        assert result is None


class TestExtractJson:
    def test_json_fenced_block(self):
        content = '```json\n{"status": "cannot_proceed", "reason": "bad"}\n```'
        result = _extract_json_from_output(content)
        assert result is not None
        assert result["status"] == "cannot_proceed"
        assert result["reason"] == "bad"

    def test_inline_braced_object(self):
        content = 'Result: {"status": "cannot_proceed", "reason": "ambiguous"}'
        result = _extract_json_from_output(content)
        assert result is not None
        assert result["status"] == "cannot_proceed"

    def test_no_json_returns_none(self):
        content = "This has no JSON at all."
        result = _extract_json_from_output(content)
        assert result is None

    def test_invalid_json_in_fenced_returns_none(self):
        content = '```json\n{invalid json}\n```'
        result = _extract_json_from_output(content)
        assert result is None

    def test_multiple_braced_objects_picks_first_valid(self):
        content = 'First: {bad} Second: {"status": "ok"}'
        result = _extract_json_from_output(content)
        assert result is not None
        assert result["status"] == "ok"
