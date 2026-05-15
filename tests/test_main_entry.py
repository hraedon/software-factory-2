from __future__ import annotations

from unittest.mock import MagicMock, patch

from factory.gate_process import _main as gate_main
from factory.runner import _main as runner_main
from factory.scheduler import _main as scheduler_main


class TestRunnerMain:
    @patch("factory.runner.run_worker")
    @patch("factory.runner._create_channel")
    def test_default_config(self, mock_channel, mock_worker):
        mock_channel.return_value = type("FakeChannel", (), {"name": "test", "family": "test"})()
        runner_main([])
        mock_worker.assert_called_once()

    @patch("factory.runner.run_worker")
    @patch("factory.runner._create_channel")
    def test_config_path_arg(self, mock_channel, mock_worker):
        mock_channel.return_value = type("FakeChannel", (), {"name": "test", "family": "test"})()
        runner_main(["--config", "/nonexistent.yaml"])
        mock_worker.assert_called_once()


class TestGateMain:
    @patch("factory.gate_process.run_gate")
    def test_default_config(self, mock_gate):
        gate_main([])
        mock_gate.assert_called_once()

    @patch("factory.gate_process.run_gate")
    def test_config_path_arg(self, mock_gate):
        gate_main(["--config", "/nonexistent.yaml"])
        mock_gate.assert_called_once()


class TestSchedulerMain:
    @patch("factory.scheduler.run_scheduler")
    def test_default_config(self, mock_sched):
        scheduler_main([])
        mock_sched.assert_called_once()

    @patch("factory.scheduler.run_scheduler")
    def test_config_path_arg(self, mock_sched):
        scheduler_main(["--config", "/nonexistent.yaml"])
        mock_sched.assert_called_once()


class TestSchedulerDrainAfterSignal:
    def test_drain_cycles_run_after_sigterm(self):
        from factory.scheduler import scheduler_loop

        runtime = MagicMock()
        runtime.config.poll_interval_seconds = 0.01
        runtime.config.stage_topology = []
        poll_count = 0

        def count_poll(rt):
            nonlocal poll_count
            poll_count += 1
            if poll_count >= 2:
                import os
                import signal

                os.kill(os.getpid(), signal.SIGTERM)

        with patch("factory.scheduler._poll_handoffs", side_effect=count_poll):
            scheduler_loop(runtime)

        assert poll_count >= 5
