"""Test-only boundary instrumentation; never shipped as runner behavior.

The parent owns and kills this CLI subprocess. Hooks pause after real writes,
flushes, replacements, publication, or evaluator creation, without fabricating
ledger/manifest states. Evaluators have cooperative release and hard deadlines;
no persisted process identifier is used to signal any process.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--mode", choices=("crash", "fault", "gate"), required=True)
    parser.add_argument("--boundary", default="")
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--markers", type=Path, required=True)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("fault_target", args.runner)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    original_open = Path.open
    original_replace = os.replace
    original_rename = Path.rename
    original_popen = subprocess.Popen
    original_atomic = runner.atomic_json

    def ready(boundary: str) -> None:
        temporary = args.ready.with_suffix(".tmp")
        temporary.write_text(json.dumps({"boundary": boundary, "pid": os.getpid()}), encoding="utf-8")
        original_replace(temporary, args.ready)

    def pause(boundary: str) -> None:
        if args.mode != "crash" or args.boundary != boundary:
            return
        ready(boundary)
        deadline = time.monotonic() + 30
        while not args.release.exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("Parent did not interrupt the instrumented CLI")
            time.sleep(0.01)

    def inject(boundary: str) -> None:
        if args.mode == "fault" and args.boundary == boundary:
            ready(boundary)
            raise OSError("Injected test-only " + boundary)

    def wait_for_evaluator() -> None:
        run_id = args.arguments[args.arguments.index("--id") + 1]
        deadline = time.monotonic() + 10
        while not list(args.markers.glob(run_id + "-*.started")):
            if time.monotonic() >= deadline:
                raise RuntimeError("Actual evaluator did not reach its start marker")
            time.sleep(0.01)

    class LedgerStream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *exception):
            return self.stream.__exit__(*exception)

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def write(self, data):
            if args.mode == "fault" and args.boundary == "write":
                self.stream.write(data[:max(1, len(data) // 2)])
                inject("write")
            return self.stream.write(data)

        def flush(self):
            self.stream.flush()
            inject("flush")

    def opened(path, mode="r", *positional, **keywords):
        if mode == "xb" and path.name == "run.log":
            inject("log_open")
        stream = original_open(path, mode, *positional, **keywords)
        if mode == "xb" and path.name.startswith(".launches.json."):
            return LedgerStream(stream)
        return stream

    def replaced(source, destination, *positional, **keywords):
        destination = Path(destination)
        if destination.name == "launches.json":
            # atomic_json already wrote, flushed, fsynced, and closed this temp.
            pause("ledger_temp_before_replace")
            inject("replace")
        result = original_replace(source, destination, *positional, **keywords)
        if destination.name == "launches.json":
            pause("claim_before_launching")
        return result

    def renamed(source, destination):
        result = original_rename(source, destination)
        if source.name.startswith(".prepare-"):
            pause("prepare_published")
        return result

    def atomic(path, value):
        status = value.get("status") if isinstance(value, dict) else None
        if path.name == "manifest.json" and status == "completed":
            # execute has waited for evaluator exit and validated the result.
            pause("result_before_terminal")
            inject("finalization")
        result = original_atomic(path, value)
        if path.name == "manifest.json":
            if status == "launching":
                pause("launching_before_popen")
            elif status == "running":
                if args.boundary == "active_execution":
                    wait_for_evaluator()
                pause("active_execution")
            elif status == "completed":
                pause("terminal_before_return")
        return result

    def popen(command, *positional, **keywords):
        process = original_popen(command, *positional, **keywords)
        # Git subprocesses also use Popen; only evaluator has this environment.
        if "RESEARCH_SOURCE_COMMIT" in (keywords.get("env") or {}):
            if args.mode == "crash" and args.boundary == "popen_before_running":
                wait_for_evaluator()
                pause("popen_before_running")
        return process

    Path.open = opened
    Path.rename = renamed
    os.replace = replaced
    subprocess.Popen = popen
    runner.atomic_json = atomic
    if args.mode == "gate":
        ready("gate")
        deadline = time.monotonic() + 30
        while not args.release.exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("Contention gate was not released")
            time.sleep(0.01)
    sys.argv = [str(args.runner), *args.arguments]
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
