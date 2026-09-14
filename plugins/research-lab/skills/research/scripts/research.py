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
        _, units, dispositions, comparisons = review_state(envelope)
        current_units = {unit["id"] for source in sources.values() for unit in source["units"]}
        if changed:
            safe_path(storage, "reconciliation").mkdir(exist_ok=True)
            atomic_json(safe_path(storage, "reconciliation", "review.json"), envelope)
        return {"registered": bool(record["sources"]), "entry_status": entry_status(envelope),
                "machine_verified": False, **envelope,
                "coverage": [{**unit, "disposition": dispositions.get(unit["id"]),
                              "carried_forward": unit["id"] not in current_units,
                              "required_comparison": comparisons.get(unit["id"])} for unit in units],
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
            git(project, "archive", "--format=zip", "--output=" + str(archive_path), commit)
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
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"error": "Interrupted; inspect recorded state before any further action"}), file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
