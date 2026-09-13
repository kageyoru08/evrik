#!/usr/bin/env python3
"""A local, standard-library experiment ledger. Python 3.11+ and Git required.

The runner records evidence; experimental commands are trusted code, not sandboxed.
Every launch consumes a durable claim before process creation. An interrupted claim
is deliberately never recycled, even when it may not have created a process.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import stat
import subprocess
import sys
import time
from typing import Any
import uuid
import zipfile


RUN_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{12}\Z")
TEMPLATE = {
    "schema_version": 1,
    "name": "small-experiment",
    "question": "Does the candidate improve on the baseline?",
    "command": ["{python}", "evaluate.py", "--output", "{result}"],
    "metric": {"name": "mse", "direction": "minimize", "min_improvement": 0.0},
    "data_paths": ["data.json"],
    "comparability": {"split": "fixed", "randomness": "none"},
    "budget": {"max_runs": 5, "timeout_seconds": 30},
}


class ResearchError(Exception):
    """An actionable input or evidence failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def reject_constant(value: str) -> None:
    raise ResearchError(f"Non-finite JSON value is not allowed: {value}")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, ValueError) as exc:
        raise ResearchError(f"Cannot read JSON at {path}: {exc}") from exc


def safe_path(root: Path, *parts: str) -> Path:
    """Reject existing links/junctions and escape paths before runner file access."""
    candidate = root.joinpath(*parts)
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ResearchError("Path escapes the research directory") from exc
    current = root
    for part in ("", *relative.parts):
        current = current / part if part else current
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ResearchError(f"Links or junctions are not allowed in research storage: {current}")
        # Path.resolve also detects junctions on Python 3.11 on Windows.
        if current.exists() and current.resolve() != current.absolute():
            raise ResearchError(f"Research storage resolves through a link: {current}")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ResearchError("Path escapes the research directory")
    return candidate


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        deadline = time.monotonic() + 1
        while True:
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                # A concurrent reader's Windows handle can briefly deny replacement.
                if os.name != "nt" or time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def project_lock(storage: Path):
    """OS-owned lock: releases on process death, no stale PID recovery needed."""
    lock_path = safe_path(storage, ".lock")
    with lock_path.open("a+b") as stream:
        if lock_path.stat().st_size == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + 15
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ResearchError("Research storage is busy; retry after the current operation")
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def without_git_environment() -> dict[str, str]:
    # Git's environment routing can override -C or discover the live ancestor repo.
    return {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}


def git(project: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(["git", "-C", str(project), *args], shell=False,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=60, check=False, env=without_git_environment())
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ResearchError(f"Git unavailable or timed out: {exc}") from exc
    if result.returncode:
        raise ResearchError("Git command failed: " + result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def project_paths(argument: str, create: bool = False) -> tuple[Path, Path]:
    project = Path(argument).resolve()
    if not project.is_dir():
        raise ResearchError("--project must be an existing Git repository root")
    top = Path(git(project, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if project != top:
        raise ResearchError(f"--project must be the Git root: {top}")
    storage = project / ".research"
    safe_path(storage)
    if create:
        storage.mkdir(exist_ok=True)
    elif not storage.is_dir():
        raise ResearchError("Research storage missing; run init first")
    return project, storage


def ignored(project: Path) -> bool:
    result = subprocess.run(["git", "-C", str(project), "check-ignore", "-q", ".research/"],
                            shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=30, env=without_git_environment())
    return result.returncode == 0


def exact_keys(value: Any, keys: set[str], context: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ResearchError(f"{context} must contain exactly: {', '.join(sorted(keys))}")


def finite_number(value: Any, context: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ResearchError(f"{context} must be a finite number")
    # JSON integers are exact and unbounded; float conversion can erase a win.
    if isinstance(value, float) and not math.isfinite(value):
        raise ResearchError(f"{context} must be a finite number")
    return value


def archive_name(name: str) -> str:
    """Use portable relative names and reject ambiguous extraction targets."""
    path = PurePosixPath(name)
    parts = name.rstrip("/").split("/")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    if (not name or path.is_absolute() or any(part in {"", ".", ".."} for part in parts)
            or any(any(char in part for char in '\\:*?"<>|\x00')
                   or part.endswith((".", " ")) or part.split(".")[0].upper() in reserved
                   for part in parts)
            or parts[0].casefold() in {".git", ".research"}):
        raise ResearchError(f"Unsafe or nonportable snapshot path: {name!r}")
    return "/".join(parts)


def validate_protocol(protocol: Any) -> dict:
    exact_keys(protocol, set(TEMPLATE), "protocol")
    if type(protocol["schema_version"]) is not int or protocol["schema_version"] != 1:
        raise ResearchError("schema_version must be 1")
    for key in ("name", "question"):
        if not isinstance(protocol[key], str) or not protocol[key].strip():
            raise ResearchError(f"{key} must be a nonempty string")
    command = protocol["command"]
    if not isinstance(command, list) or not command:
        raise ResearchError("command must be a nonempty argv list")
    for arg in command:
        if not isinstance(arg, str) or not arg or "\x00" in arg:
            raise ResearchError("command arguments must be nonempty strings without NUL")
        remainder = arg.replace("{python}", "").replace("{result}", "")
        if "{" in remainder or "}" in remainder:
            raise ResearchError("Only {python} and {result} command placeholders are supported")
    if not any("{result}" in arg for arg in command):
        raise ResearchError("command must include {result} for the evidence output path")
    metric = protocol["metric"]
    exact_keys(metric, {"name", "direction", "min_improvement"}, "metric")
    if not isinstance(metric["name"], str) or not metric["name"].strip():
        raise ResearchError("metric.name must be a nonempty string")
    if metric["direction"] not in ("minimize", "maximize"):
        raise ResearchError("metric.direction must be minimize or maximize")
    if finite_number(metric["min_improvement"], "metric.min_improvement") < 0:
        raise ResearchError("metric.min_improvement must be nonnegative (absolute units)")
    paths = protocol["data_paths"]
    if not isinstance(paths, list) or any(not isinstance(p, str) for p in paths):
        raise ResearchError("data_paths must list snapshot-relative data file names")
    for path in paths:
        if archive_name(path) != path or path.endswith("/"):
            raise ResearchError("data_paths must contain canonical relative file names")
    if len({path.casefold() for path in paths}) != len(paths):
        raise ResearchError("data_paths contains duplicates")
    comparison = protocol["comparability"]
    if (not isinstance(comparison, dict) or not comparison
            or any(not isinstance(key, str) or not key.strip() for key in comparison)):
        raise ResearchError("comparability must be a nonempty JSON object with nonempty keys")
    try:
        canonical(comparison)
    except ValueError as exc:
        raise ResearchError("comparability values must be finite JSON values") from exc
    budget = protocol["budget"]
    exact_keys(budget, {"max_runs", "timeout_seconds"}, "budget")
    if type(budget["max_runs"]) is not int or budget["max_runs"] < 1:
        raise ResearchError("budget.max_runs must be a positive integer")
    if finite_number(budget["timeout_seconds"], "budget.timeout_seconds") <= 0:
        raise ResearchError("budget.timeout_seconds must be positive")
    return protocol


def environment() -> dict:
    return {"python_version": sys.version, "python_executable": str(Path(sys.executable).resolve()),
            "platform": platform.platform(), "machine": platform.machine()}


def snapshot_files(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    files: dict[str, zipfile.ZipInfo] = {}
    seen: set[str] = set()
    for entry in archive.infolist():
        name = archive_name(entry.filename)
        if name.casefold() in seen:
            raise ResearchError(f"Duplicate or case-colliding snapshot path: {name}")
        seen.add(name.casefold())
        mode = entry.external_attr >> 16
        kind = stat.S_IFMT(mode)
        if entry.flag_bits & 1 or kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ResearchError(f"Unsupported snapshot file (links are rejected): {name}")
        if not entry.is_dir():
            files[name] = entry
    file_names = {name.casefold() for name in files}
    for name in files:
        for parent in PurePosixPath(name).parents:
            if str(parent).casefold() in file_names:
                raise ResearchError(f"Snapshot path overlaps a file: {name}")
    return files


def data_evidence(archive: zipfile.ZipFile, files: dict, paths: list[str]) -> list[dict]:
    result = []
    for name in paths:
        if name not in files:
            raise ResearchError(f"Declared data file missing from committed snapshot: {name}")
        with archive.open(files[name]) as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        result.append({"path": name, "sha256": sha, "size_bytes": files[name].file_size})
    return result


def run_directory(storage: Path, run_id: str) -> Path:
    if not RUN_ID.fullmatch(run_id):
        raise ResearchError("Invalid run id")
    directory = safe_path(storage, "runs", run_id)
    if not directory.is_dir():
        raise ResearchError(f"Run not found: {run_id}")
    return directory


def read_manifest(storage: Path, run_id: str) -> tuple[Path, dict]:
    directory = run_directory(storage, run_id)
    manifest = read_json(safe_path(storage, "runs", run_id, "manifest.json"))
    if not isinstance(manifest, dict) or manifest.get("id") != run_id:
        raise ResearchError(f"Invalid run manifest: {run_id}")
    return directory, manifest


def ledger(storage: Path) -> dict:
    path = safe_path(storage, "launches.json")
    if not path.exists():
        # Missing launch evidence must never enable a previously claimed run.
        runs = safe_path(storage, "runs")
        if runs.exists():
            for directory in runs.iterdir():
                if directory.is_dir() and RUN_ID.fullmatch(directory.name):
                    _, manifest = read_manifest(storage, directory.name)
                    if manifest.get("status") != "prepared":
                        raise ResearchError("Launch ledger missing for existing launches; do not relaunch")
        return {"schema_version": 1, "claims": {}}
    value = read_json(path)
    exact_keys(value, {"schema_version", "claims"}, "launch ledger")
    if value["schema_version"] != 1 or not isinstance(value["claims"], dict):
        raise ResearchError("Invalid launch ledger")
    return value


def initialize(project: Path, storage: Path) -> dict:
    with project_lock(storage):
        protocol_path = safe_path(storage, "protocol.json")
        created = not protocol_path.exists()
        if created:
            atomic_json(protocol_path, TEMPLATE)
    is_ignored = ignored(project)
    return {"protocol": str(protocol_path), "created": created, "research_ignored": is_ignored,
            "guidance": "Edit the protocol, ignore .research/, and commit experimental source and data before prepare."}


def prepare(project: Path, storage: Path, args: argparse.Namespace) -> dict:
    if not ignored(project):
        raise ResearchError(".research/ must be ignored by Git; add it to .gitignore and commit that change")
    protocol = validate_protocol(read_json(safe_path(storage, "protocol.json")))
    with project_lock(storage):
        if git(project, "status", "--porcelain=v1", "--untracked-files=normal"):
            raise ResearchError("Commit or otherwise preserve changes before prepare; the Git tree must be clean")
        commit = git(project, "rev-parse", "HEAD").decode().strip()
        for record in git(project, "ls-tree", "-r", "-z", commit).split(b"\0"):
            if record.startswith((b"120000 ", b"160000 ")):
                raise ResearchError("Snapshots containing symlinks or submodules are unsupported")
        runs = safe_path(storage, "runs")
        runs.mkdir(exist_ok=True)
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12]
        temporary = safe_path(storage, "runs", ".prepare-" + uuid.uuid4().hex)
        temporary.mkdir()
        archive_path = temporary / "source.zip"
        try:
            git(project, "archive", "--format=zip", "--output=" + str(archive_path), commit)
            with zipfile.ZipFile(archive_path) as archive:
                files = snapshot_files(archive)
                data = data_evidence(archive, files, protocol["data_paths"])
            if (git(project, "rev-parse", "HEAD").decode().strip() != commit
                    or git(project, "status", "--porcelain=v1", "--untracked-files=normal")):
                raise ResearchError("Git state changed during prepare; retry after preserving those changes")
            inputs = {"source": {"commit": commit, "archive_sha256": file_digest(archive_path)},
                      "protocol_sha256": digest(protocol), "data": data, "environment": environment()}
            fingerprint = digest(inputs)
            if not args.replicate:
                for directory in sorted(runs.iterdir()):
                    if directory.is_dir() and RUN_ID.fullmatch(directory.name):
                        _, previous = read_manifest(storage, directory.name)
                        if previous.get("fingerprint") == fingerprint:
                            return {"id": previous["id"], "status": previous["status"],
                                    "deduplicated": True, "manifest": str(directory / "manifest.json"),
                                    "guidance": "Use --replicate to allocate an intentional new run."}
            manifest = {"schema_version": 1, "id": run_id, "label": args.label,
                        "hypothesis": args.hypothesis, "replicate": args.replicate,
                        "created_at": utc_now(), "status": "prepared", "fingerprint": fingerprint,
                        **inputs, "protocol": protocol, "evidence": {"status": "pending"}}
            atomic_json(temporary / "manifest.json", manifest)
            destination = safe_path(storage, "runs", run_id)
            temporary.rename(destination)
            return {"id": run_id, "status": "prepared", "deduplicated": False,
                    "fingerprint": fingerprint, "manifest": str(destination / "manifest.json")}
        finally:
            # Only these two exclusively created files can exist in a preparation.
            if temporary.exists():
                (temporary / "source.zip").unlink(missing_ok=True)
                (temporary / "manifest.json").unlink(missing_ok=True)
                temporary.rmdir()


def verify_snapshot(storage: Path, directory: Path, manifest: dict) -> dict:
    protocol = validate_protocol(manifest.get("protocol"))
    if digest(protocol) != manifest.get("protocol_sha256"):
        raise ResearchError("Recorded protocol integrity check failed")
    archive_path = safe_path(storage, "runs", manifest["id"], "source.zip")
    if file_digest(archive_path) != manifest.get("source", {}).get("archive_sha256"):
        raise ResearchError("Source archive integrity check failed")
    with zipfile.ZipFile(archive_path) as archive:
        data = data_evidence(archive, snapshot_files(archive), protocol["data_paths"])
    if data != manifest.get("data"):
        raise ResearchError("Recorded data identity does not match the snapshot")
    inputs = {key: manifest.get(key) for key in ("source", "protocol_sha256", "data", "environment")}
    if digest(inputs) != manifest.get("fingerprint"):
        raise ResearchError("Run fingerprint integrity check failed")
    return protocol


def extract_source(storage: Path, directory: Path) -> Path:
    source = safe_path(storage, "runs", directory.name, "source-" + uuid.uuid4().hex[:12])
    source.mkdir()
    # Invalid Git metadata stops ancestor discovery even when paths contain os.pathsep.
    # This is deliberately not a valid gitdir pointer to any external directory.
    (source / ".git").write_text("Research Lab snapshot: Git metadata is unavailable.\n", encoding="utf-8")
    with zipfile.ZipFile(directory / "source.zip") as archive:
        files = snapshot_files(archive)
        for name, entry in files.items():
            target = source.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as origin, target.open("xb") as destination:
                while chunk := origin.read(1024 * 1024):
                    destination.write(chunk)
            if os.name != "nt":
                target.chmod(0o755 if (entry.external_attr >> 16) & 0o111 else 0o644)
    return source


def stop_owned_process(process: subprocess.Popen) -> dict:
    """Record observed cleanup actions; detached descendants cannot be certified."""
    detail = {"attempted": False, "method": "none", "scope": "owned direct child",
              "signal_succeeded": False, "direct_child_reaped": False, "descendant_state": "unknown"}
    if process.poll() is not None:
        detail.update(direct_child_reaped=True, reason="Owned direct child already exited")
        return detail
    detail["attempted"] = True
    try:
        if os.name == "nt":
            detail.update(method="taskkill /T /F", scope="OS-requested process tree")
            result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                    shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            detail["signal_succeeded"] = result.returncode == 0
            if result.returncode and process.poll() is None:
                process.kill()
                detail["direct_child_kill_fallback"] = True
        else:
            detail.update(method="SIGKILL", scope="owned POSIX process group")
            os.killpg(process.pid, signal.SIGKILL)
            detail["signal_succeeded"] = True
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        detail["error"] = str(exc)
        if process.poll() is None:
            try:
                process.kill()
                detail["direct_child_kill_fallback"] = True
                process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired) as fallback:
                detail["fallback_error"] = str(fallback)
    detail["direct_child_reaped"] = process.poll() is not None
    return detail


def result_evidence(path: Path, primary_metric: str) -> dict:
    try:
        raw = path.read_bytes()
        result = json.loads(raw.decode("utf-8"), parse_constant=reject_constant)
    except (OSError, ValueError) as exc:
        raise ResearchError(f"Cannot read JSON at {path}: {exc}") from exc
    if not isinstance(result, dict) or not isinstance(result.get("metrics"), dict):
        raise ResearchError("Result must contain a metrics object")
    metrics = result["metrics"]
    if primary_metric not in metrics:
        raise ResearchError(f"Result missing primary metric: {primary_metric}")
    for name, value in metrics.items():
        if not isinstance(name, str) or not name:
            raise ResearchError("Metric names must be nonempty strings")
        finite_number(value, f"metrics.{name}")
    return {"status": "valid", "result_sha256": hashlib.sha256(raw).hexdigest(), "metrics": metrics}


def execute(project: Path, storage: Path, run_id: str) -> dict:
    process = None
    with project_lock(storage):
        directory, manifest = read_manifest(storage, run_id)
        launches = ledger(storage)
        if run_id in launches["claims"] or manifest.get("status") != "prepared":
            raise ResearchError("This run already has a launch claim or is not prepared; inspect it. Never relaunch this id.")
        protocol = verify_snapshot(storage, directory, manifest)
        if environment() != manifest["environment"]:
            raise ResearchError("Runtime environment changed since prepare; prepare a new run")
        if len(launches["claims"]) >= protocol["budget"]["max_runs"]:
            raise ResearchError("Project launch budget exhausted (uncertain claims also consume a slot)")
        result_path = safe_path(storage, "runs", run_id, "result.json")
        log_path = safe_path(storage, "runs", run_id, "run.log")
        if result_path.exists() or log_path.exists():
            raise ResearchError("Prepared run already contains execution files; inspect it and prepare an explicit replicate")
        source = extract_source(storage, directory)
        command = [part.replace("{python}", sys.executable).replace("{result}", str(result_path))
                   for part in protocol["command"]]
        launched_at = utc_now()
        launches["claims"][run_id] = {"claimed_at": launched_at}
        atomic_json(safe_path(storage, "launches.json"), launches)
        manifest.update(status="launching", claimed_at=launched_at, command=command,
                        source_directory=source.name, runtime_environment=environment())
        atomic_json(directory / "manifest.json", manifest)
    try:
        child_environment = without_git_environment()
        child_environment.update(RESEARCH_SOURCE_COMMIT=manifest["source"]["commit"],
                                 RESEARCH_SOURCE_ROOT=str(source))
        with log_path.open("xb") as log:
            process = subprocess.Popen(command, cwd=source, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, shell=False,
                                       env=child_environment,
                                       start_new_session=os.name != "nt",
                                       creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
            manifest.update(status="running", started_at=utc_now(),
                            process={"pid": process.pid, "advisory_only": True,
                                     "note": "Never use this persisted PID to kill or infer liveness."})
            atomic_json(directory / "manifest.json", manifest)
            try:
                code = process.wait(timeout=protocol["budget"]["timeout_seconds"])
                manifest.update(status="completed" if code == 0 else "failed", exit_code=code)
            except subprocess.TimeoutExpired:
                manifest.update(status="timed_out", cleanup=stop_owned_process(process), exit_code=process.poll())
            except KeyboardInterrupt:
                manifest.update(status="interrupted", cleanup=stop_owned_process(process), exit_code=process.poll())
            log.flush()
            os.fsync(log.fileno())
    except KeyboardInterrupt:
        manifest.update(status="interrupted", exit_code=process.poll() if process else None)
        if process is not None:
            manifest["cleanup"] = stop_owned_process(process)
    except (OSError, ValueError, OverflowError) as exc:
        manifest.update(status="launch_failed" if process is None else "interrupted", error=str(exc))
        if process is not None:
            manifest["cleanup"] = stop_owned_process(process)
        manifest["exit_code"] = process.poll() if process else None
    manifest["ended_at"] = utc_now()
    if manifest["status"] == "completed":
        try:
            safe_path(storage, "runs", run_id, "result.json")
            manifest["evidence"] = result_evidence(result_path, protocol["metric"]["name"])
        except ResearchError as exc:
            manifest["evidence"] = {"status": "invalid", "reason": str(exc)}
    else:
        manifest["evidence"] = {"status": "invalid", "reason": "Execution did not complete successfully"}
    if log_path.is_file():
        safe_path(storage, "runs", run_id, "run.log")
        manifest["log_sha256"] = file_digest(log_path)
    atomic_json(safe_path(storage, "runs", run_id, "manifest.json"), manifest)
    return manifest


def unresolved_launch(manifest: dict, claimed: bool) -> bool:
    status = manifest.get("status")
    if status in {"launching", "running", "failed", "timed_out", "interrupted"} or (claimed and status == "prepared"):
        return True  # Signals and direct-child reaping do not prove all descendants ended.
    if status == "launch_failed" and ("cleanup" in manifest or manifest.get("process") is not None):
        return True
    return False


def inspect(storage: Path, run_id: str | None) -> dict:
    with project_lock(storage):
        launches = ledger(storage)
        if run_id:
            _, manifest = read_manifest(storage, run_id)
            claimed = run_id in launches["claims"]
            unresolved = unresolved_launch(manifest, claimed)
            return {**manifest, "launch_claimed": claimed, "unresolved": unresolved,
                    "guidance": "Recorded state only; unresolved launches need manual reconciliation and must not be retried. Persisted PIDs do not prove liveness."
                    if unresolved else "Execution status and evidence validity are separate; use compare for the metric decision."}
        runs = safe_path(storage, "runs")
        summaries = []
        if runs.exists():
            for directory in sorted(runs.iterdir()):
                if directory.is_dir() and RUN_ID.fullmatch(directory.name):
                    _, manifest = read_manifest(storage, directory.name)
                    claimed = directory.name in launches["claims"]
                    summaries.append({"id": directory.name, "label": manifest.get("label"),
                                      "status": manifest.get("status"), "evidence": manifest.get("evidence"),
                                      "launch_claimed": claimed,
                                      "unresolved": unresolved_launch(manifest, claimed)})
        return {"runs": summaries, "launch_claims_used": len(launches["claims"])}


def compare(storage: Path, baseline_id: str, candidate_id: str) -> dict:
    if baseline_id == candidate_id:
        raise ResearchError("Baseline and candidate must be different runs")
    with project_lock(storage):
        launches = ledger(storage)
        pair = [read_manifest(storage, run_id) for run_id in (baseline_id, candidate_id)]
        for directory, manifest in pair:
            if (manifest.get("status") != "completed" or manifest.get("exit_code") != 0
                    or manifest.get("evidence", {}).get("status") != "valid"
                    or manifest["id"] not in launches["claims"]):
                raise ResearchError(f"Run is incomplete or has invalid evidence: {manifest['id']}")
            protocol = verify_snapshot(storage, directory, manifest)
            if manifest.get("runtime_environment") != manifest.get("environment"):
                raise ResearchError("Run runtime does not match its prepared environment")
            result = safe_path(storage, "runs", manifest["id"], "result.json")
            if result_evidence(result, protocol["metric"]["name"]) != manifest["evidence"]:
                raise ResearchError(f"Result evidence changed after completion: {manifest['id']}")
            log = safe_path(storage, "runs", manifest["id"], "run.log")
            if file_digest(log) != manifest.get("log_sha256"):
                raise ResearchError(f"Log evidence changed after completion: {manifest['id']}")
        baseline, candidate = pair[0][1], pair[1][1]
        for key in ("protocol_sha256", "data", "environment"):
            if baseline[key] != candidate[key]:
                raise ResearchError(f"Runs are not comparable: {key} differs")
        metric = baseline["protocol"]["metric"]
        old = finite_number(baseline["evidence"]["metrics"][metric["name"]], "baseline metric")
        new = finite_number(candidate["evidence"]["metrics"][metric["name"]], "candidate metric")
        try:
            if isinstance(old, int) != isinstance(new, int):
                integer = old if isinstance(old, int) else new
                if int(float(integer)) != integer:
                    raise ResearchError("Mixed integer/float metrics require an exactly float-representable integer")
            improvement = finite_number(old - new if metric["direction"] == "minimize" else new - old,
                                        "metric improvement")
        except OverflowError as exc:
            raise ResearchError("Metric improvement exceeds the supported mixed float/integer range") from exc
        win = improvement > 0 and improvement >= metric["min_improvement"]
        return {"baseline": baseline_id, "candidate": candidate_id, "metric": metric["name"],
                "direction": metric["direction"], "baseline_value": old, "candidate_value": new,
                "absolute_improvement": improvement, "min_improvement": metric["min_improvement"],
                "outcome": "win" if win else "no_improvement",
                "scope": "Primary-metric decision only; scientific validity requires the declared research protocol."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("init", "prepare", "run", "inspect", "compare"):
        command = sub.add_parser(name)
        command.add_argument("--project", required=True, help="Git repository root")
        if name == "prepare":
            command.add_argument("--label", required=True)
            command.add_argument("--hypothesis", default="")
            command.add_argument("--replicate", action="store_true")
        if name in {"run", "inspect"}:
            command.add_argument("--id", required=name == "run")
        if name == "compare":
            command.add_argument("--baseline", required=True)
            command.add_argument("--candidate", required=True)
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 11):
            raise ResearchError("Python 3.11 or newer is required")
        project, storage = project_paths(args.project, create=args.action == "init")
        if args.action == "init":
            result = initialize(project, storage)
        elif args.action == "prepare":
            if not args.label.strip():
                raise ResearchError("--label must not be blank")
            result = prepare(project, storage, args)
        elif args.action == "run":
            result = execute(project, storage, args.id)
        elif args.action == "inspect":
            result = inspect(storage, args.id)
        else:
            result = compare(storage, args.baseline, args.candidate)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        if args.action == "run" and (result["status"] != "completed" or result["evidence"]["status"] != "valid"):
            return 1
        return 0
    except (ResearchError, OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"error": "Interrupted; inspect recorded state before any further action"}), file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
