from __future__ import annotations

from factory.output_extraction import extract_artifact_from_output, extract_json_from_output


class TestExtractArtifactMultipleBlocks:
    def test_prefers_last_python_block(self):
        content = "```python\nfirst = 1\n```\nSome prose\n```python\nsecond = 2\n```"
        result = extract_artifact_from_output(content)
        assert "second = 2" in result
        assert "first = 1" not in result

    def test_fallback_to_any_fenced_block(self):
        content = "Result:\n```\ndef foo(): pass\n```"
        result = extract_artifact_from_output(content)
        assert "def foo" in result

    def test_fallback_heuristic_limited_lines(self):
        lines = ["print(i)" for i in range(500)]
        lines[:200] = [f"# comment line {i}" for i in range(200)]
        content = "\n".join(lines)
        result = extract_artifact_from_output(content)
        assert result is not None

    def test_empty_input_returns_none(self):
        assert extract_artifact_from_output("") is None

    def test_prose_only_no_code_returns_none(self):
        assert extract_artifact_from_output("Hello world\nNo code here") is None


class TestExtractJsonFromOutput:
    def test_valid_json_in_code_block(self):
        content = '```json\n{"status": "ok"}\n```'
        assert extract_json_from_output(content) == {"status": "ok"}

    def test_invalid_json_in_code_block_falls_through(self):
        content = '```json\n{invalid}\n```\nSome text {"status": "ok"} here'
        result = extract_json_from_output(content)
        assert result == {"status": "ok"}

    def test_nested_braces_valid_json(self):
        content = '{"outer": {"inner": "value"}, "count": 1}'
        result = extract_json_from_output(content)
        assert result == {"outer": {"inner": "value"}, "count": 1}

    def test_truncated_json_skipped(self):
        content = '{"key": "value'
        result = extract_json_from_output(content)
        assert result is None

    def test_first_valid_dict_found(self):
        content = 'text {"bad": } more {"good": 1} end'
        result = extract_json_from_output(content)
        assert result == {"good": 1}

    def test_no_json_returns_none(self):
        assert extract_json_from_output("no json here") is None

    def test_cannot_proceed_detected(self):
        content = '```json\n{"status": "cannot_proceed", "reason": "stuck"}\n```'
        result = extract_json_from_output(content)
        assert result["status"] == "cannot_proceed"

    def test_raw_decode_multiple_objects(self):
        content = 'prefix {"a": 1} and {"b": 2} suffix'
        result = extract_json_from_output(content)
        assert result == {"a": 1}

    def test_deeply_nested_json(self):
        content = '{"a": {"b": {"c": [1, 2, 3]}}}'
        result = extract_json_from_output(content)
        assert result["a"]["b"]["c"] == [1, 2, 3]
