#!/usr/bin/env python3
"""Process nanny for golden runs.

Launches runner, gate, and scheduler as subprocesses. If any process exits
unexpectedly, terminates the remaining processes and reports which one failed.
Supports an overall timeout and periodic progress reporting.
"""
from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path

PROCESSES = [
    ("runner", "-m", "factory.runner"),
    ("gate_process", "-m", "factory.gate_process"),
    ("scheduler", "-m", "factory.scheduler"),
]

PROGRESS_INTERVAL_SECONDS = 30
DEFAULT_TIMEOUT_SECONDS = 3600


def _fmt_elapsed(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s}s" if m >= 1 else f"{s}s"


def main() -> None:
    parser = argparse.ArgumentParser(description="Golden-run process nanny")
    parser.add_argument("--config", required=True, help="Path to factory config YAML")
    parser.add_argument("--populate", action="store_true", help="Run populate_work_items first")
    parser.add_argument("--fixtures", default=None, help="Fixtures directory for populate")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Overall timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    args = parser.parse_args()

    python = sys.executable
    config = args.config

    if args.populate:
        pop_cmd = [python, "populate_work_items.py", "--config", config, "--reset"]
        if args.fixtures:
            pop_cmd.extend(["--fixtures", args.fixtures])
        print(f"[nanny] Running populate: {' '.join(pop_cmd)}")
        result = subprocess.run(pop_cmd)
        if result.returncode != 0:
            print(f"[nanny] populate_work_items failed with exit code {result.returncode}")
            sys.exit(result.returncode)

    procs: list[tuple[str, subprocess.Popen]] = []
    log_files: list = []
    shutting_down = False

    def _signal_handler(signum: int, frame: object) -> None:
        nonlocal shutting_down
        shutting_down = True
        print(f"\n[nanny] Received signal {signum}, terminating children...")
        for name, proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for name, proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        for fh in log_files:
            fh.close()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    for name, module in PROCESSES:
        cmd = [python, module, "--config", config]
        log_path = Path(f"/tmp/gr-nanny-{name}.log")
        log_file = open(log_path, "w")
        log_files.append(log_file)
        print(f"[nanny] Starting {name} (log: {log_path})")
        proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
        procs.append((name, proc))

    start_time = time.monotonic()
    last_progress = start_time

    try:
        while not shutting_down:
            elapsed = time.monotonic() - start_time

            if elapsed >= args.timeout:
                print(f"[nanny] Timeout ({_fmt_elapsed(elapsed)}), killing all processes")
                for name, proc in procs:
                    if proc.poll() is None:
                        proc.terminate()
                for name, proc in procs:
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                for fh in log_files:
                    fh.close()
                sys.exit(2)

            now = time.monotonic()
            if now - last_progress >= PROGRESS_INTERVAL_SECONDS:
                last_progress = now
                statuses = []
                for name, proc in procs:
                    status = f"pid={proc.pid}" if proc.poll() is None else f"exit={proc.returncode}"
                    statuses.append(f"{name}({status})")
                print(f"[nanny] {_fmt_elapsed(elapsed)} elapsed — {', '.join(statuses)}")

            for name, proc in procs:
                ret = proc.poll()
                if ret is not None:
                    print(f"[nanny] {name} exited with code {ret}")
                    for other_name, other_proc in procs:
                        if other_proc.poll() is None:
                            other_proc.terminate()
                    for other_name, other_proc in procs:
                        try:
                            other_proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            other_proc.kill()
                    print(f"[nanny] Aborting: {name} died with exit code {ret}")
                    for fh in log_files:
                        fh.close()
                    sys.exit(ret if ret else 1)
            time.sleep(2)
    finally:
        for name, proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for fh in log_files:
            fh.close()
        print("[nanny] All processes terminated")


if __name__ == "__main__":
    main()
