"""RFC-034: resolved model string flows through telemetry; placement key
includes model so snapshot changes don't merge into confounded buckets."""

from __future__ import annotations

from factory.channel import InvocationResult
from factory.telemetry import (
    GateAttempt,
    PassRateRow,
    compute_pass_rates,
    format_pass_rate_table,
)


class TestInvocationResultModel:
    def test_default_is_none(self):
        r = InvocationResult(success=True)
        assert r.model is None

    def test_explicit_model_preserved(self):
        r = InvocationResult(success=True, model="claude-sonnet-4-6")
        assert r.model == "claude-sonnet-4-6"


class TestPassRateRowKeysIncludeModel:
    def _attempt(self, model, attempt_n=1, passed=True, work_item_id="wi-1"):
        return GateAttempt(
            work_item_id=work_item_id,
            work_item_type="implementation",
            role="implementer",
            channel="opencode",
            family="kimi",
            attempt_n=attempt_n,
            gate_name="pytest",
            passed=passed,
            model=model,
        )

    def test_same_channel_different_models_produce_separate_buckets(self):
        attempts = [
            self._attempt("kimi/k2.6-turbo", work_item_id="wi-a", passed=True),
            self._attempt("kimi/k2.6-turbo", work_item_id="wi-b", passed=False),
            self._attempt("kimi/k2.7-turbo", work_item_id="wi-c", passed=True),
            self._attempt("kimi/k2.7-turbo", work_item_id="wi-d", passed=True),
        ]
        rows = compute_pass_rates(attempts)
        models = sorted((r.model, r.total_evaluations) for r in rows)
        assert models == [
            ("kimi/k2.6-turbo", 2),
            ("kimi/k2.7-turbo", 2),
        ]

    def test_null_model_is_a_distinct_bucket(self):
        attempts = [
            self._attempt("kimi/k2.6-turbo", work_item_id="wi-a", passed=True),
            self._attempt(None, work_item_id="wi-b", passed=True),
        ]
        rows = compute_pass_rates(attempts)
        models = sorted((r.model or "", r.total_evaluations) for r in rows)
        assert models == [("", 1), ("kimi/k2.6-turbo", 1)]


class TestFormatterWarnsOnModelDrift:
    def _row(self, model, passes=1, total=1):
        return PassRateRow(
            role="implementer",
            channel="opencode",
            family="kimi",
            gate_name="pytest",
            total_evaluations=total,
            first_attempt_passes=passes,
            total_passes=passes,
            model=model,
        )

    def test_multiple_models_in_one_group_emits_warning(self):
        rows = [self._row("kimi/k2.6-turbo"), self._row("kimi/k2.7-turbo")]
        out = format_pass_rate_table(rows)
        assert "model changed within comparison group" in out
        assert "kimi/k2.6-turbo" in out
        assert "kimi/k2.7-turbo" in out

    def test_single_model_no_warning(self):
        rows = [self._row("kimi/k2.6-turbo")]
        out = format_pass_rate_table(rows)
        assert "model changed within comparison group" not in out

    def test_partial_null_emits_note(self):
        rows = [self._row("kimi/k2.6-turbo"), self._row(None)]
        out = format_pass_rate_table(rows)
        assert "model=NULL" in out
