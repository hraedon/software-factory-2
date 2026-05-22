from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from factory.config import FactoryConfig
from factory.constants import (
    GATE_NAME_INNER_MYPY,
    GATE_NAME_INNER_RUFF,
    ROLE_IMPLEMENTER,
    ROLE_INTERFACE_ARCHITECT,
)
from factory.context import PromptContext
from factory.inner_gate import _inner_gate_label, _inner_gate_loop
from factory.pre_gate import PreGateResult


def _make_config(inner_gate_retries: int = 3) -> FactoryConfig:
    return FactoryConfig(
        dsn="postgresql://x",
        project_name="test_retry",
        hmac_key_path="/dev/null",
        workspace_root=Path("/tmp/test_retry"),
        inner_gate_retries=inner_gate_retries,
    )


def _make_ctx() -> PromptContext:
    return PromptContext(
        work_item_id="wi-1",
        role=ROLE_IMPLEMENTER,
        spec_section="## AC-01: Foo\nMust foo.",
        ac_ids=["AC-01"],
        glossary={},
        prior_failures=[],
        prompt_template="",
        context_hash="h1",
        prompt_template_hash="ph1",
        extra_artifacts={},
        stub_only_deps=[],
    )


def _make_pre_result(
    passed: bool = False,
    mypy_passed: bool = True,
    ruff_passed: bool = True,
    pytest_passed: bool = True,
    imports_symbols_passed: bool = True,
    diagnostics: list[str] | None = None,
) -> PreGateResult:
    return PreGateResult(
        passed=passed,
        mypy_passed=mypy_passed,
        ruff_passed=ruff_passed,
        pytest_passed=pytest_passed,
        imports_symbols_passed=imports_symbols_passed,
        diagnostics=diagnostics or ["mypy error"],
    )


class TestInnerGateRetryLoopFirstPass:
    def test_returns_immediately_on_first_pass(self, tmp_path: Path):
        config = _make_config(inner_gate_retries=3)
        ctx = _make_ctx()
        artifact_path = tmp_path / "impl.py"
        artifact_path.write_text("x = 1\n")
        ad = tmp_path / "attempt-1"
        ad.mkdir()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.artifact_name = "impl.py"
        mock_result.error_message = None
        mock_result.family = "test"
        mock_channel = MagicMock()
        mock_channel.invoke.return_value = mock_result
        mock_channel.name = "test"
        mock_channel.family = "test"

        pre_result = _make_pre_result(passed=True, diagnostics=[])

        with patch("factory.inner_gate._run_pre_gate", return_value=pre_result):
            with patch("factory.inner_gate._resolve_pre_gate_deps"):
                with patch("factory.inner_gate._build_export_map", return_value={}):
                    _result_art, _result_ctx, _dur, attempts = _inner_gate_loop(
                        runtime=MagicMock(),
                        wi=MagicMock(custom_fields={}),
                        actor_id="actor-1",
                        claim=MagicMock(),
                        role_name=ROLE_IMPLEMENTER,
                        channel=mock_channel,
                        ctx=ctx,
                        artifact_path=artifact_path,
                        attempt_number=1,
                        ad=ad,
                        timeout=60,
                        invocation_start=0.0,
                        effective_family="test",
                        config=config,
                    )

        assert _result_art == artifact_path
        assert len(attempts) == 1
        assert attempts[0]["passed"] is True
        mock_channel.invoke.assert_not_called()


class TestInnerGateRetryLoopSuccessOnRetry:
    def test_retries_and_succeeds_on_second_attempt(self, tmp_path: Path):
        config = _make_config(inner_gate_retries=3)
        ctx = _make_ctx()
        artifact_path = tmp_path / "impl.py"
        artifact_path.write_text("x = 1\n")
        ad = tmp_path / "attempt-1"
        ad.mkdir()
        retry_ad = ad / "retry-0"
        retry_ad.mkdir(parents=True)
        retry_art = retry_ad / "impl.py"
        retry_art.write_text("x = 2\n")

        fail_result = _make_pre_result(passed=False, mypy_passed=False)
        pass_result = _make_pre_result(passed=True, diagnostics=[])

        mock_invoke = MagicMock()
        mock_invoke.success = True
        mock_invoke.artifact_name = "impl.py"
        mock_invoke.error_message = None
        mock_invoke.family = "test"
        mock_channel = MagicMock()
        mock_channel.invoke.return_value = mock_invoke
        mock_channel.name = "test"
        mock_channel.family = "test"

        mock_runtime = MagicMock()
        mock_runtime.fallback_channel_for_role.return_value = None

        with patch("factory.inner_gate._run_pre_gate", side_effect=[fail_result, pass_result]):
            with patch("factory.inner_gate._resolve_pre_gate_deps"):
                with patch("factory.inner_gate._build_export_map", return_value={}):
                    with patch("factory.inner_gate.render_prompt", return_value="prompt"):
                        _result_art, _result_ctx, _dur, attempts = _inner_gate_loop(
                            runtime=mock_runtime,
                            wi=MagicMock(custom_fields={}),
                            actor_id="actor-1",
                            claim=MagicMock(),
                            role_name=ROLE_IMPLEMENTER,
                            channel=mock_channel,
                            ctx=ctx,
                            artifact_path=artifact_path,
                            attempt_number=1,
                            ad=ad,
                            timeout=60,
                            invocation_start=0.0,
                            effective_family="test",
                            config=config,
                        )

        assert len(attempts) == 2
        assert attempts[0]["passed"] is False
        assert attempts[1]["passed"] is True
        mock_channel.invoke.assert_called_once()


class TestInnerGateRetryLoopExhausted:
    def test_returns_artifact_after_exhausting_retries(self, tmp_path: Path):
        config = _make_config(inner_gate_retries=2)
        ctx = _make_ctx()
        artifact_path = tmp_path / "impl.py"
        artifact_path.write_text("x = 1\n")
        ad = tmp_path / "attempt-1"
        ad.mkdir()
        for i in range(2):
            retry_ad = ad / f"retry-{i}"
            retry_ad.mkdir(parents=True)
            (retry_ad / "impl.py").write_text(f"x = {i}\n")

        fail_result = _make_pre_result(passed=False, mypy_passed=False)

        mock_invoke = MagicMock()
        mock_invoke.success = True
        mock_invoke.artifact_name = "impl.py"
        mock_invoke.error_message = None
        mock_invoke.family = "test"
        mock_channel = MagicMock()
        mock_channel.invoke.return_value = mock_invoke
        mock_channel.name = "test"
        mock_channel.family = "test"

        mock_runtime = MagicMock()
        mock_runtime.fallback_channel_for_role.return_value = None

        with patch("factory.inner_gate._run_pre_gate", return_value=fail_result):
            with patch("factory.inner_gate._resolve_pre_gate_deps"):
                with patch("factory.inner_gate._build_export_map", return_value={}):
                    with patch("factory.inner_gate.render_prompt", return_value="prompt"):
                        _result_art, _result_ctx, _dur, attempts = _inner_gate_loop(
                            runtime=mock_runtime,
                            wi=MagicMock(custom_fields={}),
                            actor_id="actor-1",
                            claim=MagicMock(),
                            role_name=ROLE_IMPLEMENTER,
                            channel=mock_channel,
                            ctx=ctx,
                            artifact_path=artifact_path,
                            attempt_number=1,
                            ad=ad,
                            timeout=60,
                            invocation_start=0.0,
                            effective_family="test",
                            config=config,
                        )

        assert len(attempts) == 2
        assert all(a["passed"] is False for a in attempts)
        assert mock_channel.invoke.call_count == 2


class TestInnerGateRetryLoopInvokeFailure:
    def test_returns_none_on_channel_invoke_failure(self, tmp_path: Path):
        config = _make_config(inner_gate_retries=3)
        ctx = _make_ctx()
        artifact_path = tmp_path / "impl.py"
        artifact_path.write_text("x = 1\n")
        ad = tmp_path / "attempt-1"
        ad.mkdir()

        fail_pre = _make_pre_result(passed=False, mypy_passed=False)

        mock_invoke = MagicMock()
        mock_invoke.success = False
        mock_invoke.error_message = "timeout"
        mock_invoke.timed_out = True
        mock_invoke.exit_code = 1
        mock_channel = MagicMock()
        mock_channel.invoke.return_value = mock_invoke
        mock_channel.name = "test"
        mock_channel.family = "test"

        mock_sub = MagicMock()
        mock_runtime = MagicMock()
        mock_runtime.sub = mock_sub
        mock_runtime.fallback_channel_for_role.return_value = None

        with patch("factory.inner_gate._run_pre_gate", return_value=fail_pre):
            with patch("factory.inner_gate._resolve_pre_gate_deps"):
                with patch("factory.inner_gate._build_export_map", return_value={}):
                    with patch("factory.inner_gate.render_prompt", return_value="prompt"):
                        _result_art, _result_ctx, _dur, attempts = _inner_gate_loop(
                            runtime=mock_runtime,
                            wi=MagicMock(
                                work_item_id="wi-1",
                                custom_fields={},
                            ),
                            actor_id="actor-1",
                            claim=MagicMock(),
                            role_name=ROLE_IMPLEMENTER,
                            channel=mock_channel,
                            ctx=ctx,
                            artifact_path=artifact_path,
                            attempt_number=1,
                            ad=ad,
                            timeout=60,
                            invocation_start=0.0,
                            effective_family="test",
                            config=config,
                        )

        assert _result_art is None
        assert len(attempts) == 1
        mock_sub.transition.assert_called_once()
        transition_call = mock_sub.transition.call_args
        assert transition_call[0][0] == "wi-1"
        assert transition_call[0][1] == "channel_fail"


class TestInnerGateRetryLoopMissingArtifact:
    def test_returns_early_when_artifact_missing(self, tmp_path: Path):
        config = _make_config(inner_gate_retries=3)
        ctx = _make_ctx()
        artifact_path = tmp_path / "nonexistent.py"
        ad = tmp_path / "attempt-1"
        ad.mkdir()

        mock_channel = MagicMock()
        mock_channel.name = "test"
        mock_channel.family = "test"

        with patch("factory.inner_gate._resolve_pre_gate_deps"):
            with patch("factory.inner_gate._build_export_map", return_value={}):
                _result_art, _result_ctx, _dur, attempts = _inner_gate_loop(
                    runtime=MagicMock(),
                    wi=MagicMock(custom_fields={}),
                    actor_id="actor-1",
                    claim=MagicMock(),
                    role_name=ROLE_IMPLEMENTER,
                    channel=mock_channel,
                    ctx=ctx,
                    artifact_path=artifact_path,
                    attempt_number=1,
                    ad=ad,
                    timeout=60,
                    invocation_start=0.0,
                    effective_family="test",
                    config=config,
                )

        assert _result_art == artifact_path
        assert len(attempts) == 0


class TestInnerGateLabel:
    def test_interface_architect_pytest_failure_returns_inner_import(self):
        result = _make_pre_result(passed=False, pytest_passed=False)
        assert _inner_gate_label(result, ROLE_INTERFACE_ARCHITECT) == "inner_import"

    def test_mypy_failure_returns_inner_mypy(self):
        result = _make_pre_result(passed=False, mypy_passed=False)
        assert _inner_gate_label(result, ROLE_IMPLEMENTER) == GATE_NAME_INNER_MYPY

    def test_ruff_failure_returns_inner_ruff(self):
        result = _make_pre_result(passed=False, ruff_passed=False)
        assert _inner_gate_label(result, ROLE_IMPLEMENTER) == GATE_NAME_INNER_RUFF

    def test_imports_symbols_failure_returns_import_symbols(self):
        result = _make_pre_result(passed=False, imports_symbols_passed=False)
        label = _inner_gate_label(result, ROLE_IMPLEMENTER)
        assert label == "inner_import_symbols"
