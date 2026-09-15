#!/usr/bin/env python3
"""A local, standard-library experiment ledger. Python 3.11+ and Git required.

The runner records evidence; experimental commands are trusted code, not sandboxed.
Every launch consumes a durable claim before process creation. An interrupted claim
is deliberately never recycled, even when it may not have created a process.
"""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
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


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResearchError(f"Duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant,
                          object_pairs_hook=unique_json_object)
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
def project_lock(storage: Path, wait_seconds: float = 15):
    """OS-owned lock: releases on process death, no stale PID recovery needed."""
    lock_path = safe_path(storage, ".lock")
    with lock_path.open("a+b") as stream:
        if lock_path.stat().st_size == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + wait_seconds
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


def live_git_environment() -> dict[str, str]:
    # Native Windows sandbox accounts inherit ownership context, not repo routing.
    inherited = {(key.upper() if os.name == "nt" else key): value
                 for key, value in os.environ.items()}
    result = {key: value for key, value in os.environ.items()
              if not (key.upper() if os.name == "nt" else key).startswith("GIT_")}
    # Replaying only part of these channels can discard a later trust reset.
    unsupported = {"GIT_CONFIG_PARAMETERS", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
                   "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG"}
    if unsupported.intersection(inherited):
        raise ResearchError("Unsupported mixed Git configuration environment; preserve the caller configuration and report the blocker")
    raw_count = inherited.get("GIT_CONFIG_COUNT", "")
    if not raw_count:
        return result
    digits = raw_count.lstrip("0") or "0"
    if (not re.fullmatch(r"[0-9]+", raw_count)
            or len(digits) > len(str(len(inherited))) or int(digits) > len(inherited) // 2):
        raise ResearchError("Invalid GIT_CONFIG_COUNT in caller environment")
    values = []
    for index in range(int(digits)):
        key = inherited.get(f"GIT_CONFIG_KEY_{index}")
        value = inherited.get(f"GIT_CONFIG_VALUE_{index}")
        if not key or value is None:
            raise ResearchError(f"Missing Git configuration key or value at index {index}")
        lowered = key.lower()
        if lowered.startswith(("include.", "includeif.")):
            raise ResearchError("Unsupported Git configuration include in caller environment")
        if key.isascii() and lowered == "safe.directory":
            values.append(value)
    if values:
        result["GIT_CONFIG_COUNT"] = str(len(values))
        for index, value in enumerate(values):
            result[f"GIT_CONFIG_KEY_{index}"] = "safe.directory"
            result[f"GIT_CONFIG_VALUE_{index}"] = value
    return result


def git(project: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(["git", "-C", str(project), *args], shell=False,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=60, check=False, env=live_git_environment())
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
                            timeout=30, env=live_git_environment())
    if result.returncode not in (0, 1):
        raise ResearchError("Git check-ignore failed: " + result.stderr.decode("utf-8", "replace").strip())
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
        # ZipInfo may normalize backslashes or truncate NULs before validation.
        name = archive_name(entry.orig_filename)
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
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ResearchError(f"Unsupported run manifest schema_version: {run_id}")
    status = manifest.get("status")
    if not isinstance(status, str) or status not in {
        "prepared", "launching", "running", "completed", "failed", "timed_out", "interrupted", "launch_failed"
    }:
        raise ResearchError(f"Invalid run manifest status: {run_id}")
    for field in ("source", "evidence"):
        if not isinstance(manifest.get(field), dict):
            raise ResearchError(f"Invalid run manifest {field}: expected an object: {run_id}")
    commit = manifest["source"].get("commit")
    if not isinstance(commit, str) or not commit or "\0" in commit:
        raise ResearchError(f"Invalid run manifest source.commit: expected a nonempty NUL-free string: {run_id}")
    return directory, manifest


def ledger(storage: Path) -> dict:
    path = safe_path(storage, "launches.json")
    value = read_json(path) if path.exists() else {"schema_version": 1, "claims": {}}
    exact_keys(value, {"schema_version", "claims"}, "launch ledger")
    if (type(value["schema_version"]) is not int or value["schema_version"] != 1
            or not isinstance(value["claims"], dict)):
        raise ResearchError("Invalid launch ledger")
    runs = safe_path(storage, "runs")
    manifests = {}
    if runs.exists():
        for directory in runs.iterdir():
            if directory.is_dir() and RUN_ID.fullmatch(directory.name):
                _, manifest = read_manifest(storage, directory.name)
                manifests[directory.name] = manifest
    for run_id in value["claims"]:
        if run_id not in manifests:
            raise ResearchError(f"Corrupt launch ledger: claim has missing run evidence: {run_id}")
    for run_id, manifest in manifests.items():
        if manifest["status"] != "prepared" and run_id not in value["claims"]:
            raise ResearchError(f"Corrupt launch ledger: executed run is missing its claim: {run_id}; do not relaunch")
    # A prepared manifest with a claim is a valid unresolved crash window.
    return value


def initialize(project: Path, storage: Path) -> dict:
    with project_lock(storage):
        review = load_review(storage)
        protocol_path = safe_path(storage, "protocol.json")
        created = not protocol_path.exists()
        if created:
            atomic_json(protocol_path, TEMPLATE)
    is_ignored = ignored(project)
    return {"protocol": str(protocol_path), "created": created, "research_ignored": is_ignored,
            "entry_status": entry_status(review),
            "guidance": "Before experimental edits or launches, use reconcile --note PATH to select and resolve inherited material, or reconcile --no-inherited-notes --rationale TEXT to record the caller's absence assertion. Registration alone does not resolve pending units. Then edit the protocol, ignore .research/, and commit experimental source and data before prepare."}


DISPOSITIONS = {"context", "completed", "unresolved", "unsupported", "independent", "verify"}


def review_path(project: Path, name: str) -> Path:
    # Allow ordinary ignored notes, but never Git metadata or the generated review.
    if (not isinstance(name, str) or archive_name("content/" + name) != "content/" + name
            or name.endswith("/") or name.split("/")[0].casefold() == ".git"
            or name.casefold().startswith(".research/reconciliation/")):
        raise ResearchError("Reconciliation requires a canonical project-relative source path")
    return safe_path(project, *PurePosixPath(name).parts)


def review_bytes(project: Path, name: str) -> bytes:
    path = review_path(project, name)
    if not path.is_file():
        raise ResearchError(f"Reconciliation source must be an existing regular file: {name}")
    return path.read_bytes()


def source_units(name: str, text: str) -> list[dict]:
    raw = text.encode("utf-8")
    units, start, end = [], 0, 0
    for line in raw.splitlines(keepends=True):
        end += len(line)
        if not line.strip() or end == len(raw):
            block = raw[start:end]
            sha = hashlib.sha256(block).hexdigest()
            units.append({"id": digest([name, start, end, sha]), "path": name,
                          "start_byte": start, "end_byte": end, "sha256": sha,
                          "text": block.decode("utf-8")})
            start = end
    return units


def source_selection(project: Path, name: str, span: list[int] | None,
                     revision: str | None = None) -> dict:
    origin = {"kind": "file"}
    if revision is None:
        raw = review_bytes(project, name)
    else:
        review_path(project, name)
        if not isinstance(revision, str) or not revision or "\0" in revision:
            raise ResearchError("A Git reference must be a nonempty NUL-free string")
        commit = git(project, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}").decode().strip()
        entries = git(project, "--literal-pathspecs", "ls-tree", "--full-tree", "-z", commit, "--", name).split(b"\0")
        if len(entries) != 2 or not entries[0]:
            raise ResearchError(f"Committed reconciliation source missing or not a file: {name}")
        metadata, actual = entries[0].split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        if actual.decode("utf-8") != name or kind != "blob" or mode not in {"100644", "100755"}:
            raise ResearchError(f"Unsupported committed reconciliation source: {name}")
        raw = git(project, "cat-file", "blob", blob)
        origin = {"kind": "git", "revision": revision, "commit": commit, "blob": blob}
    if span is not None and (not isinstance(span, list) or len(span) != 2
            or any(type(item) is not int for item in span) or not 0 <= span[0] < span[1] <= len(raw)):
        raise ResearchError("Source range must be START:END bytes, zero-based and end-exclusive, within the file")
    selected = raw if span is None else raw[span[0]:span[1]]
    return {"path": name, "range": span, "origin": origin,
            "file_sha256": hashlib.sha256(raw).hexdigest(), "file_size_bytes": len(raw),
            "sha256": hashlib.sha256(selected).hexdigest(),
            "content_base64": base64.b64encode(selected).decode("ascii")}


def observation_bytes(selection: Any) -> bytes:
    exact_keys(selection, {"path", "range", "origin", "file_sha256", "file_size_bytes",
                           "sha256", "content_base64"}, "reconciliation selection")
    if (not isinstance(selection["content_base64"], str)
            or not isinstance(selection["path"], str)
            or any(not isinstance(selection[key], str) or not re.fullmatch(r"[0-9a-f]{64}", selection[key])
                   for key in ("file_sha256", "sha256"))):
        raise ResearchError("Invalid reconciliation content representation")
    raw = base64.b64decode(selection["content_base64"], validate=True)
    if hashlib.sha256(raw).hexdigest() != selection["sha256"]:
        raise ResearchError("Reconciliation selected-content integrity check failed")
    if selection["range"] is None and selection["file_sha256"] != selection["sha256"]:
        raise ResearchError("Reconciliation whole-file identity check failed")
    span, size, origin = selection["range"], selection["file_size_bytes"], selection["origin"]
    if (type(size) is not int or size < 0 or (span is None and len(raw) != size)
            or (span is not None and (not isinstance(span, list) or len(span) != 2
                or any(type(item) is not int for item in span)
                or not 0 <= span[0] < span[1] <= size or len(raw) != span[1] - span[0]))):
        raise ResearchError("Invalid reconciliation source range or size")
    if not isinstance(origin, dict) or origin.get("kind") not in ("file", "git"):
        raise ResearchError("Invalid reconciliation source origin")
    exact_keys(origin, {"kind"} if origin["kind"] == "file" else
               {"kind", "revision", "commit", "blob"}, "reconciliation origin")
    if origin["kind"] == "git" and any(not isinstance(origin[key], str) or not origin[key]
            or "\0" in origin[key] for key in ("revision", "commit", "blob")):
        raise ResearchError("Invalid reconciliation Git identity")
    return raw


def review_state(envelope: Any) -> tuple[dict, list[dict], dict, dict]:
    exact_keys(envelope, {"sha256", "review"}, "reconciliation record")
    record = envelope["review"]
    version = record.get("schema_version") if isinstance(record, dict) else None
    keys = {"schema_version", "id", "sources", "events"}
    exact_keys(record, keys | ({"no_inherited_material"} if version == 2 else set()), "reconciliation review")
    declaration = record.get("no_inherited_material")
    if declaration is not None:
        exact_keys(declaration, {"rationale", "recorded_at"}, "no-inherited-material declaration")
        if any(not isinstance(declaration[key], str) or not declaration[key].strip()
               for key in ("rationale", "recorded_at")):
            raise ResearchError("No-inherited-material declaration requires a rationale and recorded time")
    if (type(version) is not int or version not in (1, 2)
            or not isinstance(record["id"], str) or not re.fullmatch(r"[0-9a-f]{32}", record["id"])
            or not isinstance(record["sources"], list) or (not record["sources"] and declaration is None)
            or not isinstance(record["events"], list) or digest(record) != envelope["sha256"]):
        raise ResearchError("Invalid reconciliation record or integrity checksum")
    sources, known = {}, {}
    for source in record["sources"]:
        exact_keys(source, {"path", "text", "sha256", "units"}, "reconciliation source")
        if (not isinstance(source["path"], str) or not isinstance(source["text"], str)
                or hashlib.sha256(source["text"].encode("utf-8")).hexdigest() != source["sha256"]
                or source_units(source["path"], source["text"]) != source["units"]):
            raise ResearchError("Reconciliation source coverage integrity check failed")
        sources[source["path"]] = source
        known.update((unit["id"], unit) for unit in source["units"])
    dispositions, comparisons = {}, {}
    for event in record["events"]:
        exact_keys(event, {"units", "disposition", "rationale", "recorded_at", "observation"}, "reconciliation event")
        if (not isinstance(event["units"], list) or not event["units"]
                or any(not isinstance(item, str) or item not in known for item in event["units"])
                or not isinstance(event["disposition"], str) or event["disposition"] not in DISPOSITIONS
                or not isinstance(event["rationale"], str) or not event["rationale"].strip()
                or not isinstance(event["recorded_at"], str) or not event["recorded_at"]):
            raise ResearchError("Invalid reconciliation disposition")
        observation = event["observation"]
        if (observation is None) != (event["disposition"] != "verify"):
            raise ResearchError("A verify disposition requires computed comparison evidence")
        if observation is not None:
            exact_keys(observation, {"reference", "current", "committed", "equal"}, "reconciliation observation")
            values = [observation_bytes(observation[name]) for name in ("reference", "current", "committed")]
            if type(observation["equal"]) is not bool or observation["equal"] != (values[0] == values[1] == values[2]):
                raise ResearchError("Reconciliation comparison result does not match retained source bytes")
            current, committed = observation["current"], observation["committed"]
            if (current["origin"]["kind"] != "file" or committed["origin"]["kind"] != "git"
                    or (current["path"], current["range"]) != (committed["path"], committed["range"])):
                raise ResearchError("Invalid reconciliation current/committed relation")
        for unit in event["units"]:
            dispositions[unit] = event
            if observation is not None:
                comparisons[unit] = observation  # A later label cannot erase a declared prerequisite.
    active = {unit["id"]: unit for source in sources.values() for unit in source["units"]}
    for unit_id, unit in known.items():
        if (unit_id in comparisons or unit_id not in dispositions
                or dispositions[unit_id]["disposition"] in {"unresolved", "unsupported"}):
            active.setdefault(unit_id, unit)  # Refreshing note bytes cannot retire outstanding obligations.
    return sources, list(active.values()), dispositions, comparisons


def load_review(storage: Path, *, required: bool = False) -> dict | None:
    directory = safe_path(storage, "reconciliation")
    if not directory.exists():
        runs = safe_path(storage, "runs")
        if runs.exists():
            for run in runs.iterdir():
                if run.is_dir() and RUN_ID.fullmatch(run.name):
                    _, manifest = read_manifest(storage, run.name)
                    if "reconciliation" in manifest:
                        raise ResearchError("Registered reconciliation missing; retained run receipts prove prior registration. Restore original evidence before continuing")
        if required:
            raise ResearchError("Entry decision required: use reconcile --note PATH, or reconcile --no-inherited-notes --rationale TEXT for the caller's explicit absence assertion")
        return None  # Legacy inspection is read-only; new preparation/launch requires entry.
    envelope = read_json(safe_path(storage, "reconciliation", "review.json"))
    review_state(envelope)
    return envelope


def entry_status(envelope: dict | None) -> str:
    if envelope is None:
        return "required"
    return ("selected_notes_registered" if envelope["review"]["sources"]
            else "no_inherited_material_declared")


def check_review(project: Path, envelope: dict, *, current: bool) -> dict:
    sources, units, dispositions, comparisons = review_state(envelope)
    for source in sources.values():
        review_path(project, source["path"])
        if current and hashlib.sha256(review_bytes(project, source["path"])).hexdigest() != source["sha256"]:
            raise ResearchError(f"Stale inherited source: {source['path']}; refresh it with reconcile --note")
    checked = set()
    for unit in units:
        event = dispositions.get(unit["id"])
        if event is None or event["disposition"] in {"unresolved", "unsupported"}:
            raise ResearchError(f"Reconciliation unit pending or unresolved: {unit['id']}")
        observation = comparisons.get(unit["id"])
        if observation is None or digest(observation) in checked:
            continue
        checked.add(digest(observation))
        if not observation["equal"]:  # review_state computed this relation from the retained bytes.
            raise ResearchError(f"Reconciliation prerequisite comparison failed: {unit['id']}")
        for name in ("reference", "current", "committed"):
            selected = observation[name]
            review_path(project, selected["path"])
            if current:
                revision = ("HEAD" if name == "committed" else selected["origin"].get("revision"))
                fresh = source_selection(project, selected["path"], selected["range"], revision)
                if fresh["sha256"] != selected["sha256"]:
                    raise ResearchError(f"Stale reconciliation {name}: {selected['path']}; record a fresh comparison")
    return envelope


def check_review_snapshot(project: Path, envelope: dict, archive: zipfile.ZipFile) -> None:
    check_review(project, envelope, current=False)
    _, units, _, comparisons = review_state(envelope)
    files, checked = snapshot_files(archive), set()
    for unit in units:
        observation = comparisons.get(unit["id"])
        if observation is None or digest(observation) in checked:
            continue
        checked.add(digest(observation))
        selected = observation["committed"]
        name, span = selected["path"], selected["range"]
        if name not in files:
            raise ResearchError(f"Reconciliation protected source missing from prepared snapshot: {name}")
        raw = archive.read(files[name])
        if (span is not None and span[1] > len(raw)) or observation_bytes(selected) != (
                raw if span is None else raw[span[0]:span[1]]):
            raise ResearchError(f"Reconciliation does not match prepared source: {name}")


def reconciliation_coverage(envelope: dict) -> list[dict]:
    sources, units, dispositions, comparisons = review_state(envelope)
    current = {unit["id"] for source in sources.values() for unit in source["units"]}
    return [{**unit, "disposition": dispositions.get(unit["id"]),
             "carried_forward": unit["id"] not in current,
             "required_comparison": comparisons.get(unit["id"])} for unit in units]


def reconcile(project: Path, storage: Path, args: argparse.Namespace) -> dict:
    with project_lock(storage):
        launches = ledger(storage)
        envelope = load_review(storage)
        if args.note and args.unit:
            raise ResearchError("Refresh selected notes before recording their dispositions")
        selectors = any((args.reference, args.current, args.reference_revision,
                         args.reference_range, args.current_range))
        if args.no_inherited_notes:
            if (args.note or args.unit or args.disposition or selectors
                    or not args.rationale or not args.rationale.strip()):
                raise ResearchError("--no-inherited-notes requires --rationale and cannot select notes, units, dispositions or comparisons")
        elif not args.unit and (args.disposition or args.rationale or selectors):
            raise ResearchError("Disposition and comparison options require --unit")
        record = envelope["review"] if envelope else {
            "schema_version": 2, "id": uuid.uuid4().hex, "sources": [], "events": [],
            "no_inherited_material": None}
        changed = False
        if args.no_inherited_notes:
            if record["sources"]:
                raise ResearchError("Selected inherited sources cannot be cleared by a no-inherited-notes declaration")
            previous = record.get("no_inherited_material")
            if previous is not None and previous["rationale"] != args.rationale:
                raise ResearchError("No-inherited-material declaration already recorded; retain it and select any newly relevant notes")
            if previous is None:
                record["no_inherited_material"] = {"rationale": args.rationale, "recorded_at": utc_now()}
                changed = True
        for name in args.note or []:
            raw = review_bytes(project, name)
            text = raw.decode("utf-8")
            source = {"path": name, "text": text, "sha256": hashlib.sha256(raw).hexdigest(),
                      "units": source_units(name, text)}
            previous = next((item for item in reversed(record["sources"]) if item["path"] == name), None)
            if source != previous:
                record["sources"].append(source)
                changed = True
        if not record["sources"] and record.get("no_inherited_material") is None:
            if args.unit:
                raise ResearchError("Register inherited sources with reconcile --note before classifying units")
            return {"registered": False, "entry_status": "required",
                    "guidance": "Before new preparation or launch, select inherited notes with reconcile --note PATH (repeatable), or record the caller's absence assertion with --no-inherited-notes --rationale TEXT. No entry is inferred by inspection."}
        envelope = {"review": record, "sha256": digest(record)}
        sources, units, _, _ = review_state(envelope)
        if args.unit:
            active = {unit["id"] for unit in units}
            if (not args.disposition or not args.rationale or not args.rationale.strip()
                    or any(unit not in active for unit in args.unit)):
                raise ResearchError("Use active --unit identifiers, --disposition and a nonempty --rationale")
            for source in sources.values():
                if hashlib.sha256(review_bytes(project, source["path"])).hexdigest() != source["sha256"]:
                    raise ResearchError("Inherited text changed; reconcile --note before classifying it")
            observation = None
            if args.disposition == "verify":
                if not args.reference or not args.current:
                    raise ResearchError("verify requires --reference and --current source paths")
                def span(value):
                    if value is None:
                        return None
                    if not re.fullmatch(r"[0-9]+:[0-9]+", value):
                        raise ResearchError("Source ranges use START:END byte offsets")
                    return [int(item) for item in value.split(":")]
                current_range = span(args.current_range)
                observation = {
                    "reference": source_selection(project, args.reference, span(args.reference_range), args.reference_revision),
                    "current": source_selection(project, args.current, current_range),
                    "committed": source_selection(project, args.current, current_range, "HEAD")}
                observation["equal"] = (observation["reference"]["content_base64"]
                                        == observation["current"]["content_base64"]
                                        == observation["committed"]["content_base64"])
            elif selectors:
                raise ResearchError("Comparison selectors require a verify disposition")
            record["events"].append({"units": list(dict.fromkeys(args.unit)), "disposition": args.disposition,
                                     "rationale": args.rationale, "recorded_at": utc_now(), "observation": observation})
            changed = True
        envelope = {"review": record, "sha256": digest(record)}
        coverage = reconciliation_coverage(envelope)
        if changed:
            safe_path(storage, "reconciliation").mkdir(exist_ok=True)
            atomic_json(safe_path(storage, "reconciliation", "review.json"), envelope)
        return {"registered": bool(record["sources"]), "entry_status": entry_status(envelope),
                "machine_verified": False, **envelope,
                "coverage": coverage,
                "runner": {"launches": launches, "runs": [
                    {key: manifest.get(key) for key in ("id", "label", "status", "source", "evidence")}
                    for _, manifest in (read_manifest(storage, directory.name)
                        for directory in safe_path(storage, "runs").iterdir()
                        if directory.is_dir() and RUN_ID.fullmatch(directory.name))
                ] if safe_path(storage, "runs").exists() else []},
                "limits": "Entry and dispositions are caller judgments, not machine verification. Coverage is selected text, not proof of completeness or understanding; only retained comparisons compute content equality. Independent units remain unresolved outside this work. Direct shell actions and final-checkpoint completeness are not mediated."}


def prepare(project: Path, storage: Path, args: argparse.Namespace) -> dict:
    if not ignored(project):
        raise ResearchError(".research/ must be ignored by Git; add it to .gitignore and commit that change")
    protocol = validate_protocol(read_json(safe_path(storage, "protocol.json")))
    with project_lock(storage):
        if git(project, "status", "--porcelain=v1", "--untracked-files=normal"):
            raise ResearchError("Commit or otherwise preserve changes before prepare; the Git tree must be clean")
        reconciliation = load_review(storage, required=True)
        check_review(project, reconciliation, current=True)
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
            git(project, "-c", "core.autocrlf=false", "-c", "core.eol=lf",
                "archive", "--format=zip", "--output=" + str(archive_path), commit)
            with zipfile.ZipFile(archive_path) as archive:
                files = snapshot_files(archive)
                data = data_evidence(archive, files, protocol["data_paths"])
                check_review_snapshot(project, reconciliation, archive)
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
                        if (previous.get("fingerprint") == fingerprint
                                and previous.get("reconciliation") == reconciliation):
                            return {"id": previous["id"], "status": previous["status"],
                                    "deduplicated": True, "manifest": str(directory / "manifest.json"),
                                    "guidance": "Use --replicate to allocate an intentional new run."}
            manifest = {"schema_version": 1, "id": run_id, "label": args.label,
                        "hypothesis": args.hypothesis, "replicate": args.replicate,
                        "created_at": utc_now(), "status": "prepared", "fingerprint": fingerprint,
                        **inputs, "protocol": protocol, "evidence": {"status": "pending"}}
            if reconciliation is not None:
                manifest["reconciliation"] = reconciliation
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
        result = json.loads(raw.decode("utf-8"), parse_constant=reject_constant,
                            object_pairs_hook=unique_json_object)
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
        reconciliation = load_review(storage, required=True)
        captured_review = manifest.get("reconciliation")
        check_review(project, reconciliation, current=True)
        if captured_review is None:
            raise ResearchError("This run predates the entry decision; preserve it and prepare a new attributable run; use --replicate only for an intentional repeat")
        review_state(captured_review)
        if captured_review["review"]["id"] != reconciliation["review"]["id"]:
            raise ResearchError("Prepared reconciliation belongs to another registration")
        if reconciliation["review"]["sources"] and not captured_review["review"]["sources"]:
            raise ResearchError("This run predates selected-note registration; preserve it and prepare a new attributable run; use --replicate only for an intentional repeat")
        def protected_selectors(review):
            _, units, _, comparisons = review_state(review)
            return {digest({key: comparisons[unit["id"]]["current"][key] for key in ("path", "range")})
                    for unit in units if unit["id"] in comparisons}
        if not protected_selectors(reconciliation) <= protected_selectors(captured_review):
            raise ResearchError("Reconciliation declares a new protected selector absent from this prepared receipt; preserve it and prepare a new attributable run; use --replicate only for an intentional repeat")
        with zipfile.ZipFile(directory / "source.zip") as archive:
            check_review_snapshot(project, captured_review, archive)
        active_protocol = validate_protocol(read_json(safe_path(storage, "protocol.json")))
        if active_protocol["budget"] != protocol["budget"]:
            raise ResearchError("Active execution budget differs from this prepared run; prepare a new run under the active budget before launching")
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
            if (manifest.get("status") != "completed" or type(manifest.get("exit_code")) is not int
                    or manifest["exit_code"] != 0
                    or manifest.get("evidence", {}).get("status") != "valid"
                    or manifest["id"] not in launches["claims"]):
                raise ResearchError(f"Run is incomplete or has invalid evidence: {manifest['id']}")
            protocol = verify_snapshot(storage, directory, manifest)
            if manifest.get("runtime_environment") != manifest.get("environment"):
                raise ResearchError("Run runtime does not match its prepared environment")
            result = safe_path(storage, "runs", manifest["id"], "result.json")
            if result_evidence(result, protocol["metric"]["name"]) != manifest["evidence"]:
                raise ResearchError(f"Result evidence changed after completion: {manifest['id']}")
            # Python equality permits True == 1, including in secondary metrics.
            for name, value in manifest["evidence"]["metrics"].items():
                finite_number(value, f"recorded metrics.{name}")
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


EVIDENCE_LIMIT = 262144
READER_TEXT_LIMIT = 6144
READER_OUTPUT_LIMIT = 16384
READER_OUTPUT_HINT = (
    "For each generated reader page, request max_output_tokens=16384 or more where supported and preserve "
    "the complete outer result. Frames are capped at 16384 UTF-8 bytes including the final newline; "
    "bytes are not tokens, and platform delivery is not verified."
)
SOURCE_RECORD_REFERENCE = re.compile(r"""(?:\A|[\s`"'(\[{])source:([0-9a-f]{64})(?=\Z|[\s`"')\]},;.!?])""")
HOOK_LIMIT = 1048576
EVIDENCE_PRIVATE_KEYS = {"encrypted_content", "reasoning", "reasoning_content", "private_context",
                         "transcript_path", "agent_transcript_path", "session_path", "authorization",
                         "access_token", "refresh_token"}
EVIDENCE_PRIVATE_PATH = re.compile(r"(?i)(?:(?<![a-z0-9])[a-z]:[\\/]|/(?:users|home)/|[\\/]\.codex[\\/](?:sessions|memories))")


def evidence_id(value: Any) -> str:
    try:
        valid = isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        valid = False
    if not valid:
        raise ResearchError("Evidence requires a canonical native session identity")
    return value


def evidence_paths(argument: str) -> tuple[Path, Path]:
    project = Path(argument).absolute()
    if not project.is_dir():
        raise ResearchError("Evidence --project must be an existing directory")
    # Inspect the selected spelling before resolve expands Windows short names.
    # Resolving first would also hide a selected link or ancestor junction.
    for component in (*reversed(project.parents), project):
        metadata = component.lstat()
        if stat.S_ISLNK(metadata.st_mode) or (os.name == "nt" and
                metadata.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ResearchError(f"Links or reparse points are not allowed in evidence project paths: {component}")
    project = project.resolve()
    safe_path(project)
    return project, safe_path(project, ".research")


def evidence_artifact(project: Path, name: str) -> Path:
    if not isinstance(name, str):
        raise ResearchError("Evidence artifact paths must be strings")
    path = review_path(project, name)
    if name.casefold().split("/")[0] == ".codex" or name.casefold().startswith(".research/evidence/"):
        raise ResearchError("Evidence artifacts cannot select configuration or generated evidence")
    return path


def evidence_envelope(path: Path) -> dict:
    envelope = read_json(path)
    exact_keys(envelope, {"value", "sha256", "recorded_at"}, "evidence receipt")
    if (not isinstance(envelope["value"], dict) or digest(envelope["value"]) != envelope["sha256"]
            or not isinstance(envelope["recorded_at"], str) or not envelope["recorded_at"]):
        raise ResearchError("Invalid evidence receipt")
    return envelope


def evidence_read(path: Path) -> dict:
    return evidence_envelope(path)["value"]


def evidence_output(value: dict) -> bytes:
    return canonical(value) + b"\n"


def evidence_reader_command(activation: dict, reader: str, receipt_id: str, index: int) -> str:
    return activation[reader + "_command"] + f" --receipt {receipt_id} --page {index}"


def evidence_reader_request(activation: dict, tool_input: Any) -> tuple | None:
    if not isinstance(tool_input, dict) or set(tool_input) != {"command"}:
        return None
    for reader in ("readback", "sources"):
        command = activation.get(reader + "_command")
        if not command:
            continue
        if tool_input["command"] == command:
            return reader, None, 0
        if activation.get("reader_transport") != "pages-v1" or not isinstance(tool_input["command"], str):
            continue
        suffix = re.fullmatch(re.escape(command) + r" --receipt ([0-9a-f]{64}) --page (0|[1-9][0-9]{0,2})", tool_input["command"])
        if suffix:
            return reader, suffix[1], int(suffix[2])
    return None


def evidence_reader_bundle(directory: Path, activation: dict, reader: str, receipt_id: str) -> dict:
    if not isinstance(receipt_id, str) or not re.fullmatch(r"[0-9a-f]{64}", receipt_id):
        raise ResearchError("Invalid reader receipt")
    bundle = evidence_read(safe_path(directory, f"{reader}-{receipt_id}.json"))
    if (digest(bundle) != receipt_id or bundle.get("generation") != activation["id"]
            or bundle.get("session_id") != directory.name or len(canonical(bundle)) > EVIDENCE_LIMIT):
        raise ResearchError("Reader receipt binding mismatch")
    return bundle


def evidence_reader_frame(activation: dict, reader: str, receipt_id: str, page: dict,
                          next_index: int | None) -> dict:
    return {"status": "emitted", "reader": reader, "receipt_id": receipt_id,
            "generation": activation["id"], "page": page,
            "next_command": evidence_reader_command(activation, reader, receipt_id, next_index)
                            if next_index is not None else None}


def evidence_reader_pages(activation: dict, reader: str, receipt_id: str, bundle: dict) -> list[dict]:
    raw, fragments, offset, start = canonical(bundle), [], 0, 0
    if len(raw) > EVIDENCE_LIMIT:
        raise ResearchError("Evidence bundle exceeds the supported return limit")
    text = raw.decode("utf-8")
    # N bounds every numeric field and the longest continuation index. Reserve
    # its full command once; this is a size bound, never an emitted page.
    reserved = evidence_reader_frame(activation, reader, receipt_id,
                                    {"index": len(raw), "count": len(raw), "offset": len(raw),
                                     "total_bytes": len(raw), "text": ""}, len(raw))
    capacity = READER_OUTPUT_LIMIT - len(evidence_output(reserved))
    empty_size = len(canonical(""))
    while offset < len(raw):
        end = min(offset + READER_TEXT_LIMIT, len(raw))
        while end < len(raw) and raw[end] & 0xC0 == 0x80:
            end -= 1
        floor = raw[offset:end].decode("utf-8")
        if len(canonical(floor)) - empty_size > capacity:
            raise ResearchError("Reader slice floor exceeds the complete native output limit; coverage incomplete")
        low, high = len(floor), min(len(text) - start, capacity)
        while low < high:
            middle = (low + high + 1) // 2
            if len(canonical(text[start:start + middle])) - empty_size <= capacity:
                low = middle
            else:
                high = middle - 1
        fragment = text[start:start + low]
        fragments.append((offset, fragment))
        offset += len(fragment.encode("utf-8"))
        start += low
    pages = []
    for index, (offset, text) in enumerate(fragments):
        frame = evidence_reader_frame(activation, reader, receipt_id,
                                      {"index": index, "count": len(fragments), "offset": offset,
                                       "total_bytes": len(raw), "text": text},
                                      index + 1 if index + 1 < len(fragments) else None)
        if len(evidence_output(frame)) > READER_OUTPUT_LIMIT:
            raise ResearchError("Reader frame exceeds the complete native output limit; coverage incomplete")
        pages.append(frame)
    return pages


def evidence_page_matches(directory: Path, activation: dict, reader: str, receipt_id: str,
                          bundle: dict, *, frames: list[dict] | None = None) -> tuple[list, list]:
    if frames is None:
        frames = evidence_reader_pages(activation, reader, receipt_id, bundle)
    matches = []
    for index, frame in enumerate(frames):
        path = safe_path(directory, f"page-matched-{reader}-{receipt_id}-{index}.json")
        if not path.exists():
            continue
        match = evidence_read(path)
        exact_keys(match, {"call", "phase", "status", "request_sha256", "response_sha256",
                           "receipt_id", "generation", "page"}, "native reader page match")
        if (not isinstance(match["call"], str) or not re.fullmatch(r"[0-9a-f]{64}", match["call"])
                or type(match["page"]) is not int):
            raise ResearchError("Invalid matched native call")
        pre = evidence_read(safe_path(directory, f"reader-{activation['id']}-{match['call']}-pre.json"))
        post = evidence_read(safe_path(directory, f"reader-{activation['id']}-{match['call']}-post.json"))
        commands = [evidence_reader_command(activation, reader, receipt_id, index)]
        if index == 0:
            commands.append(activation[reader + "_command"])
        expected_pre = {"call": match["call"], "phase": "PreToolUse", "status": "attempted",
                        "request_sha256": match["request_sha256"]}
        expected = {**expected_pre, "phase": "PostToolUse", "status": "reader_page_matched",
                    "response_sha256": digest(evidence_output(frame).decode("utf-8")),
                    "receipt_id": receipt_id, "generation": activation["id"], "page": index}
        if (pre != expected_pre or match != post or match != expected
                or match["request_sha256"] not in {digest({"command": command}) for command in commands}):
            raise ResearchError("Invalid native reader page binding")
        matches.append({"index": index, "call": match["call"]})
    return frames, matches


def evidence_reader_aggregate(activation: dict, reader: str, receipt_id: str, matches: list) -> dict:
    return {"transport": "pages-v1", "reader": reader, "receipt_id": receipt_id,
            "generation": activation["id"], "status": "source_response_matched" if reader == "sources" else "native_response_matched",
            "pages": matches}


def evidence_reader_progress(directory: Path, activation: dict, reader: str, receipt_id: str, bundle: dict) -> dict:
    frames, matches = evidence_page_matches(directory, activation, reader, receipt_id, bundle)
    present = {match["index"] for match in matches}
    # A complete set without its aggregate can be repaired by an explicit local reread.
    next_index = next((index for index in range(len(frames)) if index not in present), 0)
    return {"matched_pages": len(matches), "total_pages": len(frames),
            "next_command": evidence_reader_command(activation, reader, receipt_id, next_index)}


def evidence_write(path: Path, value: dict, *, immutable: bool = False) -> None:
    if immutable and path.exists():
        if evidence_read(path) != value:
            raise ResearchError("Conflicting evidence receipt; original preserved")
        return
    atomic_json(path, {"value": value, "sha256": digest(value), "recorded_at": utc_now()})


def evidence_session(project: Path, directory: Path, session_id: str) -> dict | None:
    path = safe_path(directory, "session.json")
    if not path.exists():
        return None
    state = evidence_read(path)
    exact_keys(state, {"schema_version", "project", "session_id", "owner_thread_id", "activations"}, "evidence session")
    if (type(state["schema_version"]) is not int or state["schema_version"] != 1
            or state["project"] != str(project) or state["session_id"] != session_id
            or state["owner_thread_id"] != session_id or not isinstance(state["activations"], list)
            or not state["activations"]):
        raise ResearchError("Invalid evidence session binding")
    for item in state["activations"]:
        fields = {"id", "artifacts", "public_web", "experiment", "handler_sha256", "readback_command",
                  "state", "opened_at", "closed_at", "reason", "latest_readback"}
        # Retain original generations without inventing source acknowledgements.
        if isinstance(item, dict) and "record" in item:
            fields |= {"record", "sources_command"}
        if isinstance(item, dict) and "reader_transport" in item:
            fields |= {"reader_transport", "latest_sources"}
        exact_keys(item, fields, "evidence activation")
        if "reader_transport" in item and (item["reader_transport"] != "pages-v1"
                or (item["latest_sources"] is not None and not re.fullmatch(r"[0-9a-f]{64}", str(item["latest_sources"])))):
            raise ResearchError("Invalid reader transport binding")
        if (not isinstance(item["id"], str) or not re.fullmatch(r"[0-9a-f]{32}", item["id"])
                or item["state"] not in {"active", "closed"} or type(item["public_web"]) is not bool
                or type(item["experiment"]) is not bool or not isinstance(item["artifacts"], list)
                or not item["artifacts"] or not isinstance(item["readback_command"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", str(item["handler_sha256"]))
                or (item["latest_readback"] is not None and not re.fullmatch(r"[0-9a-f]{64}", str(item["latest_readback"])))):
            raise ResearchError("Invalid evidence activation")
        if (not isinstance(item["opened_at"], str) or not item["opened_at"]
                or (item["state"] == "active" and (item["closed_at"] is not None or item["reason"] is not None))
                or (item["state"] == "closed" and (not isinstance(item["closed_at"], str) or not item["closed_at"]
                                                    or not isinstance(item["reason"], str) or not item["reason"].strip()))):
            raise ResearchError("Invalid evidence activation lifecycle")
        for name in item["artifacts"]:
            evidence_artifact(project, name)
        if len(set(item["artifacts"])) != len(item["artifacts"]):
            raise ResearchError("Duplicate evidence artifacts")
        if "record" in item:
            if item["public_web"]:
                if (item["record"] not in item["artifacts"] or not isinstance(item["sources_command"], str)
                        or not item["sources_command"]):
                    raise ResearchError("Invalid evidence source boundary")
            elif item["record"] is not None or item["sources_command"] is not None:
                raise ResearchError("Source boundary requires public web activation")
    if any(item["state"] != "closed" for item in state["activations"][:-1]):
        raise ResearchError("Prior evidence activation is not closed")
    return state


def evidence_dependencies(project: Path, storage: Path, experiment: bool) -> dict:
    if not experiment:
        return {"experiment_attached": False, "ready": True}
    project_paths(str(project))  # Existing Git contract; no discovery for literature.
    validate_protocol(read_json(safe_path(storage, "protocol.json")))
    review = load_review(storage, required=True)
    result = {"experiment_attached": True, "ready": True, "reconciliation": review,
              "coverage": reconciliation_coverage(review), "launches": ledger(storage), "runs": []}
    try:
        check_review(project, review, current=True)
    except ResearchError as exc:
        result.update(ready=False, reconciliation_issue=str(exc))
    runs = safe_path(storage, "runs")
    for directory in sorted(runs.iterdir()) if runs.exists() else []:
        if not directory.is_dir() or not RUN_ID.fullmatch(directory.name):
            continue
        _, manifest = read_manifest(storage, directory.name)
        unresolved = unresolved_launch(manifest, directory.name in result["launches"]["claims"])
        files = {name: file_digest(safe_path(directory, name)) if safe_path(directory, name).is_file() else None
                 for name in ("manifest.json", "source.zip", "result.json", "run.log")}
        run = {"manifest": manifest, "files": files, "unresolved": unresolved}
        try:
            protocol = verify_snapshot(storage, directory, manifest)
            if manifest["status"] == "completed" and (
                    result_evidence(safe_path(directory, "result.json"), protocol["metric"]["name"]) != manifest["evidence"]
                    or files["run.log"] != manifest.get("log_sha256")):
                raise ResearchError("Completed run evidence changed")
        except (ResearchError, OSError, ValueError, zipfile.BadZipFile) as exc:
            run["evidence_issue"] = str(exc)
            result["ready"] = False
        result["runs"].append(run)
        if unresolved:
            result["ready"] = False
    return result


def evidence_captures(project: Path, directory: Path, activation: dict) -> tuple[dict, list]:
    catalog, calls, complete = [], {}, True
    for path in sorted(directory.glob(f"web-{activation['id']}-*.json")):
        envelope = evidence_envelope(safe_path(directory, path.name))
        record = envelope["value"]
        reference = {"path": str(path.relative_to(project)), "sha256": file_digest(path)}
        catalog.append(reference)
        calls.setdefault(record["call"], {})[record["phase"]] = (record, envelope["recorded_at"],
                                                               {**reference, "path": path.relative_to(project).as_posix()})
        complete = complete and record["status"] in {"attempted", "captured_text"}
    captures = []
    for phases in calls.values():
        complete = complete and {key: value[0]["status"] for key, value in phases.items()} == {
            "PreToolUse": "attempted", "PostToolUse": "captured_text"}
        if "PreToolUse" not in phases or "PostToolUse" not in phases:
            continue
        pre, post = phases["PreToolUse"], phases["PostToolUse"]
        if (pre[0]["status"] == "attempted" and post[0]["status"] == "captured_text"
                and pre[0]["request_sha256"] == post[0]["request_sha256"]):
            references = [pre[2], post[2]]
            captures.append({"id": digest(references), "request": pre[0]["request"], "captured_at": post[1],
                             "receipts": references, "returned_text": post[0]["returned_text"]})
    return {"complete": complete, "receipts": catalog}, captures


def evidence_native_match(directory: Path, activation: dict, receipt_id: str, reader: str, matched: dict) -> bool:
    if activation.get("reader_transport") == "pages-v1":
        exact_keys(matched, {"transport", "reader", "receipt_id", "generation", "status", "pages"}, "native reader aggregate")
        if not isinstance(matched["pages"], list):
            raise ResearchError("Invalid native reader page coverage")
        for item in matched["pages"]:
            exact_keys(item, {"index", "call"}, "native reader page reference")
            if type(item["index"]) is not int or not isinstance(item["call"], str):
                raise ResearchError("Invalid native reader page reference")
        bundle = evidence_reader_bundle(directory, activation, reader, receipt_id)
        frames, matches = evidence_page_matches(directory, activation, reader, receipt_id, bundle)
        return (len(matches) == len(frames)
                and b"".join(frame["page"]["text"].encode("utf-8") for frame in frames) == canonical(bundle)
                and matched == evidence_reader_aggregate(activation, reader, receipt_id, matches))
    exact_keys(matched, {"call", "phase", "status", "request_sha256", "response_sha256", "receipt_id", "generation"}, "native reader match")
    if not re.fullmatch(r"[0-9a-f]{64}", str(matched["call"])):
        raise ResearchError("Invalid matched native call")
    post = evidence_read(safe_path(directory, f"reader-{activation['id']}-{matched['call']}-post.json"))
    pre = evidence_read(safe_path(directory, f"reader-{activation['id']}-{matched['call']}-pre.json"))
    expected_pre = {"call": matched["call"], "phase": "PreToolUse", "status": "attempted",
                    "request_sha256": digest({"command": activation[reader + "_command"]})}
    return (matched == post and pre == expected_pre and matched["request_sha256"] == pre["request_sha256"]
            and matched["receipt_id"] == receipt_id and matched["generation"] == activation["id"]
            and matched["status"] == ("source_response_matched" if reader == "sources" else "native_response_matched")
            and matched["phase"] == "PostToolUse")


def evidence_sources(project: Path, directory: Path, activation: dict) -> tuple[dict, list]:
    result = {"ready": True, "pending_reads": [], "missing_record_refs": [], "next_command": None}
    if not activation["public_web"]:
        return result, []
    if "record" not in activation:
        return {**result, "ready": False, "issue": "Legacy public-web activation has no source-reader boundary; preserve it and close incomplete before a new explicit activation."}, []
    _, captures = evidence_captures(project, directory, activation)
    pending = []
    for capture in captures:
        match_path = safe_path(directory, f"source-matched-{capture['id']}.json")
        matched = False
        if match_path.exists():
            match = evidence_read(match_path)
            receipt_id = match.get("receipt_id")
            if not isinstance(receipt_id, str) or not re.fullmatch(r"[0-9a-f]{64}", receipt_id):
                raise ResearchError("Invalid source reader receipt")
            bundle = evidence_read(safe_path(directory, f"sources-{receipt_id}.json"))
            matched = (digest(bundle) == receipt_id and bundle.get("capture") == capture
                       and bundle.get("generation") == activation["id"]
                       and bundle.get("session_id") == directory.name
                       and evidence_native_match(directory, activation, receipt_id, "sources", match))
        if not matched:
            pending.append(capture)
    text = ""
    if captures:
        path = evidence_artifact(project, activation["record"])
        if path.exists():
            if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
                raise ResearchError("Evidence record must be a regular UTF-8 file")
            with path.open("rb") as stream:
                raw = stream.read(EVIDENCE_LIMIT + 1)
            if len(raw) > EVIDENCE_LIMIT:
                raise ResearchError("Evidence record exceeds the supported whole-text limit")
            text = raw.decode("utf-8")
    result["pending_reads"] = [capture["id"] for capture in pending]
    if pending:
        result["next_command"] = activation["sources_command"]
        receipt_id = activation.get("latest_sources")
        if receipt_id:
            bundle = evidence_reader_bundle(directory, activation, "sources", receipt_id)
            if bundle.get("capture") == pending[0]:
                result["reader_progress"] = evidence_reader_progress(directory, activation, "sources", receipt_id, bundle)
                result["next_command"] = result["reader_progress"]["next_command"]
    record_references = set(SOURCE_RECORD_REFERENCE.findall(text))
    result["missing_record_refs"] = [ref["path"] for capture in captures for ref in capture["receipts"]
                                     if capture["id"] not in record_references and ref["path"] not in text]
    result["ready"] = not (pending or result["missing_record_refs"])
    if not result["ready"]:
        result["issue"] = ("Saved sources require their exact native reader response and references in the current record. "
                           "Complete every pending reader page using next_command, retain each capture's "
                           "record_reference or its complete literal receipt paths in "
                           + activation["record"] + ", then check again.")
    return result, pending


def evidence_snapshot(project: Path, storage: Path, directory: Path, activation: dict) -> dict:
    artifacts, total = [], 0
    for name in activation["artifacts"]:
        path = evidence_artifact(project, name)
        if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
            raise ResearchError(f"Required evidence artifact missing or not a regular file: {name}")
        with path.open("rb") as stream:
            raw = stream.read(EVIDENCE_LIMIT + 1)
        total += len(raw)
        if total > EVIDENCE_LIMIT:
            raise ResearchError("Evidence readback exceeds the supported whole-text limit; coverage incomplete")
        artifacts.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                          "text": raw.decode("utf-8")})
    web, _ = evidence_captures(project, directory, activation)
    return {"artifacts": artifacts, "dependencies": evidence_dependencies(project, storage, activation["experiment"]),
            "web": web}


def evidence_reader_current(project: Path, storage: Path, directory: Path, activation: dict,
                            reader: str, receipt_id: str, bundle: dict) -> None:
    if reader == "readback":
        if (activation["latest_readback"] != receipt_id
                or bundle.get("snapshot") != evidence_snapshot(project, storage, directory, activation)):
            raise ResearchError("Reader snapshot changed; preserve it and explicitly read back current evidence")
    elif bundle.get("capture") is not None:
        _, captures = evidence_captures(project, directory, activation)
        if bundle["capture"] not in captures:
            raise ResearchError("Source capture differs from saved receipts")


def evidence_status(project: Path, storage: Path, directory: Path, activation: dict) -> dict:
    result = {"status": "missing_readback", "fresh": False, "native_response_matched": False,
              "ready_to_close": False, "semantic_review_verified": False,
              "semantic_review_note": "False is expected: semantic judgment is outside machine proof and is not a normal-close prerequisite.",
              "latest_readback": activation["latest_readback"], "readback_command": activation["readback_command"],
              "next_readback_command": activation["readback_command"],
              "sources_command": activation.get("sources_command"), "reader_output_hint": READER_OUTPUT_HINT}
    try:
        result["sources"], _ = evidence_sources(project, directory, activation)
        snapshot = evidence_snapshot(project, storage, directory, activation)
        result["web"] = snapshot["web"]
        result["dependencies_ready"] = snapshot["dependencies"]["ready"]
        receipt_id = activation["latest_readback"]
        if receipt_id:
            bundle = evidence_read(safe_path(directory, f"readback-{receipt_id}.json"))
            if digest(bundle) != receipt_id or bundle.get("generation") != activation["id"]:
                raise ResearchError("Readback receipt identity mismatch")
            result["fresh"] = (bundle["snapshot"] == snapshot
                               and activation["handler_sha256"] == file_digest(Path(__file__)))
            match = safe_path(directory, f"matched-{receipt_id}.json")
            if match.exists():
                result["native_response_matched"] = evidence_native_match(directory, activation, receipt_id, "readback", evidence_read(match))
            if result["fresh"] and activation.get("reader_transport") == "pages-v1":
                result["reader_progress"] = evidence_reader_progress(directory, activation, "readback", receipt_id, bundle)
                result["next_readback_command"] = (None if result["native_response_matched"]
                                                   else result["reader_progress"]["next_command"])
            result["status"] = "current" if result["fresh"] else "stale"
        result["ready_to_close"] = (result["fresh"] and result["native_response_matched"]
                                    and snapshot["web"]["complete"] and snapshot["dependencies"]["ready"]
                                    and result["sources"]["ready"])
        if result["fresh"] and not result["ready_to_close"]:
            result["status"] = "incomplete"
    except (ResearchError, OSError, ValueError, KeyError, TypeError) as exc:
        result.update(status="incomplete", issue=str(exc))
    result["unmet"] = [name for name, needed in (
        ("current_artifact_readback", not result["fresh"]),
        ("latest_native_reader_match", not result["native_response_matched"]),
        ("complete_public_capture", result.get("web", {}).get("complete") is False),
        ("experiment_dependencies", result.get("dependencies_ready") is False),
        ("saved_source_read_and_record_refs", result.get("sources", {}).get("ready") is False),
        ("evidence_state_unavailable", "issue" in result)) if needed]
    if not result["native_response_matched"] and "issue" not in result:
        result["reader_recovery"] = ("No native response match is recorded for the latest readback. "
                                     "Run next_readback_command alone in a separate native call with complete output, "
                                     "inspect every page, then check or close separately.")
    return result


def evidence_action(args: argparse.Namespace) -> dict:
    project, storage = evidence_paths(args.project)
    session_id = evidence_id(os.environ.get("CODEX_SESSION_ID"))
    if evidence_id(os.environ.get("CODEX_THREAD_ID")) != session_id:
        raise ResearchError("Evidence activation supports only the native root owner, not children")
    directory = safe_path(storage, "evidence", session_id)
    if args.operation == "activate":
        for name in args.artifact:
            evidence_artifact(project, name)
        if args.public_web and (args.record is None or args.record not in args.artifact):
            raise ResearchError("Public web activation requires --record equal to one declared --artifact")
        if args.record is not None and not args.public_web:
            raise ResearchError("--record requires --public-web")
        if args.experiment:
            evidence_dependencies(project, storage, True)
        directory.mkdir(parents=True, exist_ok=True)
    elif not safe_path(directory, "session.json").exists():
        return {"status": "not_activated", "ready_to_close": False, "semantic_review_verified": False}
    with project_lock(storage):
        state = evidence_session(project, directory, session_id)
        activation = state["activations"][-1] if state else None
        if args.operation == "activate":
            boundary = {"artifacts": sorted(set(args.artifact)), "public_web": args.public_web,
                        "experiment": args.experiment, "handler_sha256": file_digest(Path(__file__)), "record": args.record}
            if activation and activation["state"] == "active":
                if any(activation.get(key) != value for key, value in boundary.items()):
                    raise ResearchError("Active evidence scope differs; close it honestly before a new activation")
            else:
                commands = {"sources_command": None}
                for reader in ("readback", "sources") if args.public_web else ("readback",):
                    argv = [sys.executable, "-X", "utf8", "-B", str(Path(__file__).resolve()),
                            "evidence", reader, "--project", str(project)]
                    commands[reader + "_command"] = ("& " + " ".join("'" + part.replace("'", "''") + "'" for part in argv)
                                                     if os.name == "nt" else shlex.join(argv))
                activation = {**boundary, **commands, "id": uuid.uuid4().hex, "state": "active",
                              "opened_at": utc_now(), "closed_at": None, "reason": None, "latest_readback": None,
                              "reader_transport": "pages-v1", "latest_sources": None}
                state = state or {"schema_version": 1, "project": str(project), "session_id": session_id,
                                  "owner_thread_id": session_id, "activations": []}
                state["activations"].append(activation)
                evidence_write(safe_path(directory, "session.json"), state)
            return {"status": "active", "session_id": session_id, "generation": activation["id"],
                    "readback_command": activation["readback_command"], "artifacts": activation["artifacts"],
                    "sources_command": activation.get("sources_command"), "record": activation.get("record"),
                    "evidence_directory": str(directory.relative_to(project)), "semantic_review_verified": False,
                    "reader_output_hint": READER_OUTPUT_HINT}
        if args.operation == "close" and bool(args.incomplete) != bool(args.reason and args.reason.strip()):
            raise ResearchError("Incomplete close requires --incomplete and a nonempty --reason together")
        if activation["state"] == "closed":
            result = {"status": "closed", "reason": activation["reason"], "semantic_review_verified": False}
            if args.operation in {"check", "close"}:
                current = evidence_status(project, storage, directory, activation)
                result["current_evidence"] = {key: current[key] for key in (
                    "status", "fresh", "native_response_matched", "ready_to_close", "unmet", "issue",
                    "dependencies_ready") if key in current}
                if not current["ready_to_close"]:
                    result["recovery"] = ("The historical close is unchanged. Further native review requires "
                                          "an explicit new activation; closed readers and hooks remain inactive.")
                    if args.operation == "close" and not args.incomplete:
                        error = ResearchError("Closed session does not meet current evidence requirements")
                        error.evidence_status = result
                        raise error
            return result
        if args.operation in {"readback", "sources"}:
            if activation["handler_sha256"] != file_digest(Path(__file__)):
                raise ResearchError("Evidence handler changed; preserve and close the old activation")
            if activation.get("reader_transport") != "pages-v1":
                raise ResearchError("Preserve and close the old reader activation before using the current transport")
            if (args.receipt is None) != (args.page is None):
                raise ResearchError("Reader continuation requires both --receipt and --page")
            if args.receipt is not None:
                bundle = evidence_reader_bundle(directory, activation, args.operation, args.receipt)
                evidence_reader_current(project, storage, directory, activation, args.operation, args.receipt, bundle)
                frames = evidence_reader_pages(activation, args.operation, args.receipt, bundle)
                if not 0 <= args.page < len(frames):
                    raise ResearchError("Reader page is outside the saved bundle")
                return frames[args.page]
            if args.operation == "sources":
                sources, pending = evidence_sources(project, directory, activation)
                if not activation.get("sources_command"):
                    raise ResearchError(sources.get("issue", "Sources reader requires explicit public-web activation"))
                bundle = {"session_id": session_id, "generation": activation["id"],
                          "capture": pending[0] if pending else None,
                          "record_reference": "source:" + pending[0]["id"] if pending else None,
                          "remaining_unread_captures": max(0, len(pending) - 1),
                          "missing_record_refs": sources["missing_record_refs"],
                          "record": activation["record"],
                          "record_refs_hint": "These saved receipt paths were absent from record when this bundle was created. "
                                              "Retain each capture's record_reference or all its literal receipt paths with your "
                                              "source notes, then check; this is not a source access or capture failure."}
            else:
                bundle = {"session_id": session_id, "generation": activation["id"], "emitted_at": utc_now(),
                          "snapshot": evidence_snapshot(project, storage, directory, activation)}
            if len(canonical(bundle)) > EVIDENCE_LIMIT:
                raise ResearchError("Evidence bundle exceeds the supported return limit; coverage incomplete")
            receipt_id = digest(bundle)
            frames = evidence_reader_pages(activation, args.operation, receipt_id, bundle)
            evidence_write(safe_path(directory, f"{args.operation}-{receipt_id}.json"), bundle, immutable=True)
            activation["latest_readback" if args.operation == "readback" else "latest_sources"] = receipt_id
            evidence_write(safe_path(directory, "session.json"), state)
            return frames[0]
        status = evidence_status(project, storage, directory, activation)
        if args.operation == "close":
            if not args.incomplete and not status["ready_to_close"]:
                error = ResearchError("Evidence is not ready to close: " + status.get("sources", {}).get("issue", status["status"]))
                error.evidence_status = status
                raise error
            activation.update(state="closed", closed_at=utc_now(),
                              reason=args.reason if args.incomplete else "Current evidence and native response matched; semantics not verified")
            evidence_write(safe_path(directory, "session.json"), state)
            return {**status, "status": "closed", "incomplete": args.incomplete, "reason": activation["reason"]}
        return status


def evidence_unsafe(value: Any, depth: int = 0) -> bool:
    if depth > 16:
        return True
    if isinstance(value, dict):
        return any(str(key).lower() in EVIDENCE_PRIVATE_KEYS or evidence_unsafe(item, depth + 1)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(evidence_unsafe(item, depth + 1) for item in value)
    if isinstance(value, str):
        if EVIDENCE_PRIVATE_PATH.search(value):
            return True
        if value.lstrip().startswith(("{", "[")):
            try:
                return evidence_unsafe(json.loads(value), depth + 1)
            except (ValueError, RecursionError):
                pass
        return bool(re.search(r'''(?i)["'](?:encrypted_content|private_context|reasoning_content)["']\s*:''', value))
    return False


def evidence_text(value: Any) -> dict | None:
    if isinstance(value, str):
        result = {"representation": "string", "text": value}
    else:
        blocks = value.get("content") if isinstance(value, dict) else value
        if (not isinstance(blocks, list) or not blocks or not all(
                isinstance(block, dict) and set(block) == {"type", "text"}
                and block["type"] in ("text", "input_text") and isinstance(block["text"], str) for block in blocks)):
            return None
        result = {"representation": "text_blocks", "content": blocks}
    return result if len(canonical(result)) <= EVIDENCE_LIMIT and not evidence_unsafe(value) else None


def evidence_public_request(value: Any) -> bool:
    if not isinstance(value, dict) or evidence_unsafe(value) or len(canonical(value)) > EVIDENCE_LIMIT:
        return False
    operations = set(value) & {"search_query", "open", "find"}
    if not operations or set(value) - operations - {"response_length"}:
        return False
    if "response_length" in value and value["response_length"] not in ("short", "medium", "long"):
        return False
    for operation in operations:
        required, allowed = {"search_query": ({"q"}, {"q", "domains", "recency"}),
                             "open": ({"ref_id"}, {"ref_id", "lineno"}),
                             "find": ({"ref_id", "pattern"}, {"ref_id", "pattern"})}[operation]
        items = value[operation]
        if not isinstance(items, list) or not items or (operation == "search_query" and len(items) > 4):
            return False
        for item in items:
            if not isinstance(item, dict) or not required <= set(item) <= allowed:
                return False
            for key, field in item.items():
                if key in {"q", "ref_id", "pattern"} and (not isinstance(field, str) or not field.strip() or "\0" in field):
                    return False
                if key == "ref_id" and not (re.match(r"https?://[^/@\s]+(?:/|$)", field)
                                             or re.fullmatch(r"turn[0-9]+[A-Za-z][A-Za-z0-9_-]*[0-9]", field)):
                    return False
                if key in {"recency", "lineno"} and (type(field) is not int or field < 0):
                    return False
                if key == "domains" and (not isinstance(field, list) or not field
                                          or any(not isinstance(domain, str) or not re.fullmatch(r"[A-Za-z0-9.-]+", domain) for domain in field)):
                    return False
    return True


def evidence_hook() -> dict:
    active = False
    failure_stage = "active_capture"
    try:
        raw = sys.stdin.buffer.read(HOOK_LIMIT + 1)
        if len(raw) > HOOK_LIMIT:
            return {}
        event = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_json_object)
        if not isinstance(event, dict) or any(key in event for key in ("agent_id", "agent_type")):
            return {}
        phase, name = event.get("hook_event_name"), event.get("tool_name")
        if phase not in {"PreToolUse", "PostToolUse"} or name not in {"webrun", "Bash"}:
            return {}
        project, storage = evidence_paths(str(Path.cwd()))
        if not isinstance(event.get("cwd"), str) or evidence_paths(event["cwd"])[0] != project:
            return {}
        session_id = evidence_id(event.get("session_id"))
        directory = safe_path(storage, "evidence", session_id)
        state = evidence_session(project, directory, session_id)
        if state is None or state["activations"][-1]["state"] != "active":
            return {}
        activation = state["activations"][-1]
        tool_input = event.get("tool_input")
        reader_request = evidence_reader_request(activation, tool_input) if name == "Bash" else None
        reader = reader_request[0] if reader_request else None
        active = reader or (name == "webrun" and activation["public_web"])
        if not active:
            return {}
        failure_stage = "attempt_binding"
        with project_lock(storage, wait_seconds=1):
            state = evidence_session(project, directory, session_id)
            activation = state["activations"][-1]
            if activation["state"] != "active":
                return {}
            tool_input = event.get("tool_input")
            reader_request = evidence_reader_request(activation, tool_input) if name == "Bash" else None
            reader = reader_request[0] if reader_request else None
            if not reader and not (name == "webrun" and activation["public_web"]):
                return {}
            request_ok = bool(reader) or evidence_public_request(tool_input)
            if not reader and not request_ok and phase == "PreToolUse":
                return {"decision": "block", "reason": "Unsupported public web request refused before retrieval; "
                        "no capture attempt was recorded. Correct the request within the supported public scope before submitting it."}
            if not reader and request_ok and phase == "PreToolUse":
                sources, _ = evidence_sources(project, directory, activation)
                if not sources["ready"]:
                    return {"decision": "block", "reason": "Web request deferred before retrieval; no capture attempt was recorded. "
                            + sources["issue"] + " After this local repair, the original web operation may proceed."}
            if activation["handler_sha256"] != file_digest(Path(__file__)):
                raise ResearchError("Handler identity changed")
            frames = None
            if reader and reader_request[1] is not None:
                failure_stage = "reader_saved_bundle"
                requested_bundle = evidence_reader_bundle(directory, activation, reader, reader_request[1])
                failure_stage = "reader_current_evidence"
                evidence_reader_current(project, storage, directory, activation, reader, reader_request[1], requested_bundle)
                failure_stage = "reader_response_match"
                frames = evidence_reader_pages(activation, reader, reader_request[1], requested_bundle)
                if reader_request[2] >= len(frames):
                    raise ResearchError("Reader page is outside the saved bundle")
                failure_stage = "attempt_binding"
            tool_id = event.get("tool_use_id")
            if not isinstance(tool_id, str) or not tool_id or len(tool_id) > 256:
                raise ResearchError("Missing native call identity")
            call = digest({"generation": activation["id"], "tool_use_id": tool_id})
            prefix = f"{'reader' if reader else 'web'}-{activation['id']}-{call}"
            path = safe_path(directory, f"{prefix}-{'pre' if phase == 'PreToolUse' else 'post'}.json")
            record = {"call": call, "phase": phase, "status": "attempted" if request_ok else "incomplete",
                      "request_sha256": digest(tool_input)}
            if not reader and request_ok:
                record["request"] = tool_input
            if phase == "PostToolUse":
                pre_path = safe_path(directory, prefix + "-pre.json")
                pre = evidence_read(pre_path) if pre_path.exists() else None
                matched_pre = (pre is not None and pre["status"] == "attempted"
                               and pre["request_sha256"] == record["request_sha256"])
                response = event.get("tool_response")
                record["response_sha256"] = digest(response)
                if reader:
                    if not matched_pre:
                        raise ResearchError("Reader request does not match its attempt")
                    failure_stage = "reader_response_type"
                    if not isinstance(response, str):
                        raise ResearchError("Unsupported reader response")
                    failure_stage = "reader_response_json"
                    returned = json.loads(response, parse_constant=reject_constant, object_pairs_hook=unique_json_object)
                    failure_stage = "reader_response_schema"
                    exact_keys(returned, {"status", "reader", "receipt_id", "generation", "page", "next_command"}, "reader return")
                    exact_keys(returned["page"], {"index", "count", "offset", "total_bytes", "text"}, "reader page")
                    receipt_id = returned["receipt_id"]
                    if not isinstance(receipt_id, str) or not re.fullmatch(r"[0-9a-f]{64}", receipt_id):
                        raise ResearchError("Invalid reader receipt")
                    failure_stage = "reader_saved_bundle"
                    bundle = evidence_reader_bundle(directory, activation, reader, receipt_id)
                    failure_stage = "reader_response_match"
                    # Reuse only this invocation's frames after the independent bundle read.
                    if frames is None or reader_request[1] != receipt_id or requested_bundle != bundle:
                        frames = evidence_reader_pages(activation, reader, receipt_id, bundle)
                    index = returned["page"]["index"]
                    if (type(index) is not int or not 0 <= index < len(frames)
                            or (reader_request[1] is not None and reader_request[1] != receipt_id)
                            or reader_request[2] != index or returned != frames[index]
                            or response != evidence_output(frames[index]).decode("utf-8")):
                        raise ResearchError("Reader response differs from saved evidence")
                    failure_stage = "reader_current_evidence"
                    evidence_reader_current(project, storage, directory, activation, reader, receipt_id, bundle)
                    record.update(status="reader_page_matched", receipt_id=receipt_id,
                                  generation=activation["id"], page=index)
                else:
                    text = evidence_text(response) if request_ok and matched_pre else None
                    record["status"] = "captured_text" if text is not None else "incomplete"
                    if text is not None:
                        record["returned_text"] = text
            failure_stage = "receipt_persistence"
            if path.exists() and evidence_read(path) != record:
                evidence_write(safe_path(directory, f"web-{activation['id']}-{call}-conflict-{digest(record)}.json"),
                               {"call": call, "phase": "conflict", "status": "incomplete", "sha256": digest(record)}, immutable=True)
                raise ResearchError("Conflicting native response")
            evidence_write(path, record, immutable=True)
            if reader and phase == "PostToolUse":
                page_path = safe_path(directory, f"page-matched-{reader}-{receipt_id}-{index}.json")
                if not page_path.exists():
                    evidence_write(page_path, record, immutable=True)
                frames, matches = evidence_page_matches(directory, activation, reader, receipt_id, bundle, frames=frames)
                if len(matches) == len(frames):
                    match_path = (safe_path(directory, f"matched-{receipt_id}.json") if reader == "readback" else
                                  safe_path(directory, f"source-matched-{bundle['capture']['id']}.json")
                                  if bundle["capture"] is not None else None)
                    if match_path is not None and not match_path.exists():
                        evidence_write(match_path, evidence_reader_aggregate(activation, reader, receipt_id, matches), immutable=True)
            if record["status"] == "incomplete":
                failure_stage = "capture_validation"
                raise ResearchError("Unsupported or filtered capture")
        return {}
    except (ResearchError, OSError, ValueError, KeyError, TypeError, RecursionError):
        # No raw input, private paths, response text or exception detail is logged.
        return {"decision": "block", "reason": f"Research evidence capture incomplete [stage={failure_stage}]; preserve the original operation and do not retry retrieval. Native delivery handling remains a platform boundary."} if active else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("init", "prepare", "run", "inspect", "compare", "reconcile"):
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
        if name == "reconcile":
            command.add_argument("--note", action="append", help="Select or refresh an inherited UTF-8 note inside the project")
            command.add_argument("--no-inherited-notes", action="store_true", help="Record the caller's assertion that no inherited material applies; requires --rationale")
            command.add_argument("--unit", action="append", help="Source-derived unit ID to classify; repeat for adjacent units")
            command.add_argument("--disposition", choices=sorted(DISPOSITIONS))
            command.add_argument("--rationale")
            command.add_argument("--reference", help="Authoritative reference path inside the project")
            command.add_argument("--reference-revision", help="Read the reference from this Git commit/ref, instead of the live file")
            command.add_argument("--current", help="Protected current file to compare with the reference and its HEAD blob")
            command.add_argument("--reference-range", help="Optional zero-based, end-exclusive START:END byte range")
            command.add_argument("--current-range", help="Optional zero-based, end-exclusive START:END byte range")
    evidence = sub.add_parser("evidence", help="Explicit native-session evidence without requiring Git")
    actions = evidence.add_subparsers(dest="operation", required=True)
    for name in ("activate", "readback", "sources", "check", "close", "hook"):
        action = actions.add_parser(name)
        if name != "hook":
            action.add_argument("--project", required=True, help="Explicit authorized filesystem root")
        if name == "activate":
            action.add_argument("--artifact", action="append", required=True)
            action.add_argument("--public-web", action="store_true")
            action.add_argument("--record", help="Working UTF-8 record selected from --artifact; required with --public-web")
            action.add_argument("--experiment", action="store_true")
        if name in {"readback", "sources"}:
            action.add_argument("--receipt", help="Exact saved reader receipt returned by the previous page")
            action.add_argument("--page", type=int, help="Index in the immutable saved reader bundle")
        if name == "close":
            action.add_argument("--incomplete", action="store_true")
            action.add_argument("--reason")
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 11):
            raise ResearchError("Python 3.11 or newer is required")
        if args.action == "evidence":
            try:
                result = evidence_hook() if args.operation == "hook" else evidence_action(args)
            except (TypeError, AttributeError, RecursionError) as exc:
                raise ResearchError("Invalid evidence state or input") from exc
            if result:
                sys.stdout.buffer.write(evidence_output(result))
            return 0
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
        elif args.action == "reconcile":
            result = reconcile(project, storage, args)
        else:
            result = compare(storage, args.baseline, args.candidate)
        # JSON escapes preserve arbitrary note text even on legacy-codepage pipes.
        print(json.dumps(result, indent=2, allow_nan=False))
        if args.action == "run" and (result["status"] != "completed" or result["evidence"]["status"] != "valid"):
            return 1
        return 0
    except (ResearchError, OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        error = {"error": str(exc)}
        if isinstance(exc, ResearchError) and hasattr(exc, "evidence_status"):
            error["evidence"] = exc.evidence_status
        print(json.dumps(error), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"error": "Interrupted; inspect recorded state before any further action"}), file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
