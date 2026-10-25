"""Observable record, recovery and project preflight behavior; no model calls."""
import argparse
import genericpath
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_evidence_stream import r, RUNNER


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="evrik workflow ")
        self.addCleanup(temporary.cleanup)
        # Direct internal calls use the same canonical root as the CLI boundary.
        self.project = Path(temporary.name).resolve()
        self.storage = self.project / ".research"
        self.file = self.project / "review.md"
        self.file.write_bytes(b"Review from saved evidence\r\n")

    def record(self, operation, **values):
        return r.record_action(argparse.Namespace(project=str(self.project), operation=operation, key="review",
                               **values))

    def status(self, since=None):
        return r.workflow_status(argparse.Namespace(project=str(self.project), since=since))

    def test_exclusive_versions_byte_identity_and_delta(self):
        original = self.record("save", input="review.md")
        saved = self.project / original["assets"][0]["saved"]
        self.assertEqual(saved.read_bytes(), self.file.read_bytes())
        self.assertEqual(original["assets"][0]["storage"], "byte_copy")
        self.assertTrue(self.record("save", input="review.md")["deduplicated"])
        first = self.status()
        self.assertEqual(self.status(first["snapshot"])["changes"], {})
        self.file.write_bytes(b"Review from saved evidence\n")
        new = self.record("save", input="review.md")
        self.assertNotEqual(new["id"], original["id"])
        self.assertEqual(saved.read_bytes(), b"Review from saved evidence\r\n")
        self.assertEqual(self.status(first["snapshot"])["changes"]["administration"]["record_count"], 2)

    def test_status_delta_rejects_misbound_snapshot_without_rewriting_it(self):
        first = self.status()
        self.record("save", input="review.md")
        second = self.status()
        previous = self.storage / "status" / (first["snapshot"] + ".json")
        replacement = (self.storage / "status" / (second["snapshot"] + ".json")).read_bytes()
        previous.write_bytes(replacement)
        with self.assertRaisesRegex(r.ResearchError, "Status snapshot identity mismatch"):
            self.status(first["snapshot"])
        self.assertEqual(previous.read_bytes(), replacement)

    def test_record_ledger_rejects_invalid_shapes_and_duplicates_without_writes(self):
        saved = self.record("save", input="review.md")
        candidate = {key: value for key, value in r.record_entries(self.storage)[0].items() if key != "id"}
        candidate["key"] = "new event"
        self.file.write_bytes(b"A new version must not be captured with an invalid ledger")
        ledger = self.storage / "records/ledger.json"
        records = self.storage / "records"
        invalid = ({saved["id"]: None}, [saved["id"], saved["id"]], {}, "", [{}])
        operations = (("status", self.status), ("save", lambda: self.record("save", input="review.md")),
                      ("append", lambda: r.record_append(self.storage, candidate)))
        for value in invalid:
            for name, operation in operations:
                with self.subTest(ledger=value, operation=name):
                    ledger.write_text(json.dumps(value), encoding="utf-8")
                    before = {p.relative_to(records): p.read_bytes() for p in records.rglob("*") if p.is_file()}
                    with self.assertRaisesRegex(r.ResearchError, "record ledger"):
                        operation()
                    self.assertEqual({p.relative_to(records): p.read_bytes() for p in records.rglob("*") if p.is_file()}, before)

    def test_metadata_access_failure_cannot_bypass_preflight_or_reset_record_history(self):
        self.record("save", input="review.md")
        configuration = self.storage / "preflight.json"
        r.atomic_json(configuration, {"checks": [], "required_runs": 1, "result_fixture": None})
        ledger = self.storage / "records/ledger.json"
        before = {p.relative_to(self.storage): p.read_bytes() for p in self.storage.rglob("*") if p.is_file()}
        stat = os.stat
        operations = ((configuration, lambda: r.check_preflight(self.project, self.storage)),
                      (ledger, lambda: r.record_append(self.storage, {"kind": "preserve history"})))
        for target, operation in operations:
            with self.subTest(metadata=target.name):
                def fail_stat(path, *args, **kwargs):
                    if os.fspath(path) == str(target):
                        raise PermissionError("Injected metadata access failure")
                    return stat(path, *args, **kwargs)

                with patch.object(os.path, "exists", genericpath.exists), \
                        patch.object(os, "stat", side_effect=fail_stat), self.assertRaises(OSError):
                    operation()
                self.assertEqual({p.relative_to(self.storage): p.read_bytes() for p in self.storage.rglob("*") if p.is_file()}, before)

    def test_interrupted_record_copy_recovers_without_overwriting_existing_objects(self):
        raw = b"Large immutable record\n" * 4096
        self.file.write_bytes(raw)
        identity = hashlib.sha256(raw).hexdigest()
        target = self.storage / "records/objects" / identity
        real_open = Path.open
        opens = 0

        class InterruptedReader:
            def __init__(self, stream):
                self.stream, self.reads = stream, 0
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.stream.close()
            def read(self, size=-1):
                self.reads += 1
                if self.reads > 1:
                    raise OSError("source read interrupted")
                return self.stream.read(size)

        def opened(path, mode="r", *args, **kwargs):
            nonlocal opens
            stream = real_open(path, mode, *args, **kwargs)
            if path == self.file and mode == "rb":
                opens += 1
                if opens == 2:
                    return InterruptedReader(stream)
            return stream

        with patch.object(Path, "open", opened):
            with self.assertRaisesRegex(OSError, "source read interrupted"):
                self.record("save", input="review.md")
        self.assertFalse(target.exists())
        self.assertFalse((self.storage / "records/ledger.json").exists())
        saved = self.record("save", input="review.md")
        self.assertEqual(target.read_bytes(), raw)
        self.assertFalse(os.path.samestat(self.file.stat(), target.stat()))
        original_entry = (self.project / saved["record"]).read_bytes()
        self.assertTrue(self.record("save", input="review.md")["deduplicated"])
        self.assertEqual((self.project / saved["record"]).read_bytes(), original_entry)
        target.write_bytes(b"pre-existing corruption")
        with self.assertRaises(r.ResearchError):
            self.record("save", input="review.md")
        self.assertEqual(target.read_bytes(), b"pre-existing corruption")

    def test_record_publication_collision_preserves_existing_object(self):
        target = self.storage / "records/objects" / hashlib.sha256(self.file.read_bytes()).hexdigest()
        real_link = os.link

        def collision(source, destination):
            Path(destination).write_bytes(b"existing collision")
            return real_link(source, destination)

        with patch.object(r.os, "link", collision):
            with self.assertRaises(r.ResearchError):
                self.record("save", input="review.md")
        self.assertEqual(target.read_bytes(), b"existing collision")
        self.assertFalse((self.storage / "records/ledger.json").exists())

    def test_frozen_review_failure_recovery_withdrawal_and_staleness(self):
        packet = self.record("freeze", artifact=["review.md"], reviewer=["root", "peer"])["id"]
        self.file.with_name("capacity.txt").write_text("Selected model is at capacity", encoding="utf-8")
        failed = self.record("review", input="capacity.txt", packet=packet, reviewer="peer", status="failed", decision=None, model="reported-model")
        vote = self.record("review", input="review.md", packet=packet, reviewer="root", status="completed", decision="accept", model="reported-model")
        status = self.status()["reviewer_decisions"][0]
        self.assertEqual(status["missing_reviews"], ["peer"])
        self.assertEqual(status["decision"], "unresolved")
        self.record("review", input="review.md", packet=packet, reviewer="peer", status="completed", decision="accept", model="reported-model")
        self.assertEqual(self.status()["reviewer_decisions"][0]["decision"], "accepted")
        self.assertEqual(self.status()["scientific_assessability"], "not_automatically_assessed")
        self.record("withdraw", target=vote["id"], reason="Reviewer corrected the vote")
        self.assertEqual(self.status()["reviewer_decisions"][0]["decision"], "unresolved")
        self.file.write_bytes(b"Materially changed packet")
        status = self.status()["reviewer_decisions"][0]
        self.assertEqual(status["stale_artifacts"], ["review.md"])
        self.assertFalse(status["usable_for_current_scope"])
        self.assertIn(failed["id"], [entry["id"] for entry in r.record_entries(self.storage)])

    def test_empty_reviewer_is_rejected_and_legacy_packet_remains_unresolved(self):
        def cli(*arguments):
            return subprocess.run([sys.executable, "-B", str(RUNNER), "record", *arguments,
                                   "--project", str(self.project)], capture_output=True, text=True, encoding="utf-8", timeout=10)
        for actor in ("", "   "):
            with self.subTest(reviewer=repr(actor)):
                rejected = cli("freeze", "--key", "packet", "--artifact", "review.md", "--reviewer", actor)
                self.assertEqual(rejected.returncode, 2, rejected.stdout or rejected.stderr)
                self.assertIn("nonempty", json.loads(rejected.stderr)["error"])
                # These values were admitted by older versions; keep their original records intact.
                assets = r.record_assets(self.project, self.storage, ["review.md"])
                packet = r.record_append(self.storage, {"kind": "freeze", "key": "legacy", "assets": assets, "reviewers": [actor]})
                r.record_append(self.storage, {"kind": "review", "key": "legacy-vote", "assets": assets,
                    "packet": packet["id"], "reviewer": actor, "status": "completed", "decision": "accept",
                    "model": None, "attribution": "caller_reported; inspect the saved native receipt"})
                before = {path: path.read_bytes() for path in (self.storage / "records").rglob("*") if path.is_file()}
                rejected = cli("review", "--key", "vote", "--packet", packet["id"], "--reviewer", actor,
                               "--status", "completed", "--decision", "accept", "--input", "review.md")
                self.assertEqual(rejected.returncode, 2, rejected.stdout or rejected.stderr)
                status = next(p for p in self.status()["reviewer_decisions"] if p["packet"] == packet["id"])
                self.assertEqual(status["missing_reviews"], [actor])
                self.assertFalse(status["usable_for_current_scope"])
                self.assertEqual(status["decision"], "unresolved")
                self.assertEqual(before, {path: path.read_bytes() for path in (self.storage / "records").rglob("*") if path.is_file()})

    def test_source_import_identity_disagreement_is_not_native_or_semantic_support(self):
        metadata = {"provider": "exa", "call_id": "ordinary-call-1", "requested_url": "https://example.org/v1",
                    "resolved_url": "https://example.org/v2", "title": "Observed title", "version": "v2",
                    "access": "abstract", "expected": {"resolved_url": "https://example.org/v1", "title": "Expected title", "version": "v1"}}
        (self.project / "source.json").write_text(json.dumps(metadata), encoding="utf-8")
        receipt = self.record("source", input="review.md", metadata="source.json")
        self.assertFalse(receipt["native_capture"])
        source = r.record_entries(self.storage)[0]["source"]
        self.assertEqual(set(source["identity_checks"].values()), {"mismatch"})
        self.assertEqual(source["semantic_support"], "unreviewed")
        self.assertFalse(source["identity_verified"])

    def test_source_import_keeps_unknown_redirect_identity_explicit(self):
        first, second = "https://example.org/requested", "https://example.org/resolved"
        cases = ((first, None, None), (None, second, None), (None, None, None),
                 (first, first, False), (first, second, True))
        for requested, resolved, expected in cases:
            with self.subTest(requested=requested, resolved=resolved):
                metadata = {"provider": "manual", "call_id": None, "requested_url": requested,
                            "resolved_url": resolved, "title": None, "version": None,
                            "access": "excerpt", "expected": {}}
                (self.project / "source.json").write_text(json.dumps(metadata), encoding="utf-8")
                completed = subprocess.run(
                    [sys.executable, "-X", "utf8", "-B", str(RUNNER), "record", "source",
                     "--project", str(self.project), "--key", "source-identity",
                     "--input", "review.md", "--metadata", "source.json"],
                    capture_output=True, text=True, encoding="utf-8", timeout=10)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                receipt = json.loads(completed.stdout)
                self.assertFalse(receipt["native_capture"])
                entry = next(item for item in r.record_entries(self.storage) if item["id"] == receipt["id"])
                source = entry["source"]
                self.assertIs(source["redirect_observed"], expected)
                self.assertEqual(source["semantic_support"], "unreviewed")
                self.assertFalse(source["identity_verified"])

    def test_source_import_rejects_disguised_urls_and_preserves_valid_spelling(self):
        cases = (("requested_url", "https://@example.org/p", 2),
                 ("resolved_url", "https://@example.org/p", 2),
                 ("requested_url", "\x01https://example.org/p", 2),
                 ("resolved_url", "https://exam\tple.org/p", 2),
                 ("requested_url", "HTTPS://example.org/?tag=@public", 0),
                 ("resolved_url", "https://example.org/a%20b", 0))
        for field, url, expected in cases:
            with self.subTest(field=field, url=url):
                metadata = {"provider": "manual", "call_id": None, "requested_url": None,
                            "resolved_url": None, "title": None, "version": None,
                            "access": "excerpt", "expected": {}}
                metadata[field] = url
                (self.project / "source.json").write_text(json.dumps(metadata), encoding="utf-8")
                before = r.record_entries(self.storage)
                completed = subprocess.run(
                    [sys.executable, "-X", "utf8", "-B", str(RUNNER), "record", "source",
                     "--project", str(self.project), "--key", "source-url",
                     "--input", "review.md", "--metadata", "source.json"],
                    capture_output=True, text=True, encoding="utf-8", timeout=10)
                self.assertEqual(completed.returncode, expected, completed.stderr or completed.stdout)
                if expected:
                    self.assertIn("error", json.loads(completed.stderr))
                    self.assertEqual(r.record_entries(self.storage), before)
                else:
                    receipt = json.loads(completed.stdout)
                    self.assertFalse(receipt["native_capture"])
                    source = r.record_entries(self.storage)[-1]["source"]
                    self.assertEqual(source[field], url)
                    self.assertFalse(source["identity_verified"])
                    self.assertEqual(source["semantic_support"], "unreviewed")

    def test_non_git_compatibility_is_reported_before_setup(self):
        completed = subprocess.run([sys.executable, "-X", "utf8", "-B", str(RUNNER), "preflight", "--project", str(self.project)],
                                   capture_output=True, text=True, encoding="utf-8", timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        status = json.loads(completed.stdout)
        self.assertFalse(status["git_compatible"])
        self.assertFalse(status["ready"])
        self.assertTrue(status["non_git_support"]["immutable_records"])
        self.assertFalse((self.project / ".git").exists())

    def test_preflight_rejects_stale_pointer_and_accepts_a_fresh_recovery(self):
        def git(*args):
            completed = subprocess.run(["git", "-C", str(self.project), *args], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        git("init", "-q")
        (self.project / ".gitignore").write_text(".research/\n", encoding="utf-8")
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
        self.storage.mkdir()
        r.initialize(self.project, self.storage)
        control = self.storage / "check-exit"
        control.write_text("0", encoding="utf-8")
        config = {"checks": [{"name": "controlled exit", "command": ["{python}", "-c",
                  "from pathlib import Path; raise SystemExit(int(Path('.research/check-exit').read_text()))"],
                  "timeout_seconds": 5}], "required_runs": 1, "result_fixture": None}
        path = self.storage / "preflight.json"
        r.atomic_json(path, config)
        self.assertTrue(r.preflight(self.project, self.storage, True)["ready"])
        ordinary = self.record("save", input="review.md")
        ordinary_path = self.project / ordinary["record"]
        ordinary_bytes = ordinary_path.read_bytes()
        original = r.check_preflight(self.project, self.storage)
        ordinary_path.write_bytes((self.storage / "records/entries" / (original + ".json")).read_bytes())
        with self.assertRaisesRegex(r.ResearchError, "Record identity mismatch"):
            r.check_preflight(self.project, self.storage)
        ordinary_path.write_bytes(ordinary_bytes)
        self.assertEqual(r.check_preflight(self.project, self.storage), original)
        publish = r.atomic_json

        def interrupted_pointer(path, value):
            if path.name == "preflight-latest.json":
                raise OSError("pointer publication interrupted")
            return publish(path, value)

        control.write_text("1", encoding="utf-8")
        with patch.object(r, "atomic_json", side_effect=interrupted_pointer):
            with self.assertRaisesRegex(OSError, "pointer publication interrupted"):
                r.preflight(self.project, self.storage, True)
        self.assertEqual(r.read_json(self.storage / "preflight-latest.json")["record_id"], original)
        failed = r.record_entries(self.storage)[-1]
        self.assertFalse(failed["result"]["ready"])
        self.assertEqual(failed["result"]["checks"][0]["exit_code"], 1)
        with self.assertRaisesRegex(r.ResearchError, "preflight is missing, failed or stale"):
            r.check_preflight(self.project, self.storage)

        ledger = self.storage / "records/ledger.json"
        original_ledger = ledger.read_bytes()
        duplicate = json.dumps([*json.loads(original_ledger), original]).encode("utf-8")
        ledger.write_bytes(duplicate)
        with self.assertRaisesRegex(r.ResearchError, "Duplicate record ledger identity"):
            r.check_preflight(self.project, self.storage)
        self.assertEqual(ledger.read_bytes(), duplicate)
        ledger.write_bytes(original_ledger)

        # A new successful fixture-only check may have the same result as an older one.
        fixture = self.storage / "fixture.json"
        valid = '{"metrics": {"mse": 1}}'
        fixture.write_text(valid, encoding="utf-8")
        config.update(checks=[], result_fixture=".research/fixture.json")
        r.atomic_json(path, config)
        self.assertTrue(r.preflight(self.project, self.storage, True)["ready"])
        self.assertTrue(r.check_preflight(self.project, self.storage))
        fixture.write_text('{"metrics": {"other": 1}}', encoding="utf-8")
        self.assertFalse(r.preflight(self.project, self.storage, True)["ready"])
        fixture.write_text(valid, encoding="utf-8")
        self.assertTrue(r.preflight(self.project, self.storage, True)["ready"])
        self.assertEqual(r.check_preflight(self.project, self.storage), r.record_entries(self.storage)[-1]["id"])
        self.assertEqual(next(entry for entry in r.record_entries(self.storage) if entry["id"] == failed["id"]), failed)

    def test_interrupted_preflight_preserves_partial_failure_and_blocks_prepare(self):
        def git(*args):
            completed = subprocess.run(["git", "-C", str(self.project), *args], capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        git("init", "-q")
        (self.project / ".gitignore").write_text(".research/\n", encoding="utf-8")
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
        self.storage.mkdir()
        r.initialize(self.project, self.storage)
        control = self.storage / "check-exit"
        control.write_text("0", encoding="utf-8")
        config = {"checks": [
            {"name": "first", "command": ["{python}", "-c",
             "from pathlib import Path; print('first'); raise SystemExit(int(Path('.research/check-exit').read_text()))"],
             "timeout_seconds": 5},
            {"name": "second", "command": ["{python}", "-c", "pass"], "timeout_seconds": 5}],
            "required_runs": 1, "result_fixture": None}
        r.atomic_json(self.storage / "preflight.json", config)
        self.assertTrue(r.preflight(self.project, self.storage, True)["ready"])
        original = r.record_entries(self.storage)[-1]
        run = subprocess.run

        def interrupt_second(command, **kwargs):
            if command == [sys.executable, "-c", "pass"]:
                raise KeyboardInterrupt
            return run(command, **kwargs)

        control.write_text("1", encoding="utf-8")
        with patch.object(r.subprocess, "run", side_effect=interrupt_second):
            with self.assertRaises(KeyboardInterrupt):
                r.preflight(self.project, self.storage, True)
        entry = r.record_entries(self.storage)[-1]
        self.assertFalse(entry["result"]["ready"])
        self.assertEqual(entry["result"]["readiness_scope"], "runner_prerequisites_and_declared_project_checks")
        first, second = entry["result"]["checks"]
        self.assertEqual((first["status"], first["exit_code"]), ("failed", 1))
        self.assertEqual((self.project / first["log"]).read_bytes().strip(), b"first")
        self.assertEqual((second["name"], second["status"], second["exit_code"]), ("second", "interrupted", None))
        self.assertNotIn("log", second)
        self.assertEqual(r.read_json(self.storage / "preflight-latest.json")["record_id"], entry["id"])
        with self.assertRaisesRegex(r.ResearchError, "preflight is missing, failed or stale"):
            r.prepare(self.project, self.storage, argparse.Namespace(label="blocked", hypothesis="", replicate=False))
        self.assertEqual(r.record_entries(self.storage)[0], original)

    def test_preflight_real_import_schema_budget_and_stale_candidate(self):
        def git(*args):
            completed = subprocess.run(["git", "-C", str(self.project), *args], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        git("init", "-q")
        (self.project / ".gitignore").write_text(".research/\n", encoding="utf-8")
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
        self.storage.mkdir()
        r.initialize(self.project, self.storage)
        protocol = r.read_json(self.storage / "protocol.json")
        protocol["data_paths"] = []
        r.atomic_json(self.storage / "protocol.json", protocol)
        fixture = self.storage / "fixture.json"
        fixture.write_text(json.dumps({"metrics": {"mse": 1.0}}), encoding="utf-8")
        config = {"checks": [{"name": "real import and numerical fixture", "command": ["{python}", "-c", "import math; assert math.isclose(math.sqrt(4), 2)"], "timeout_seconds": 5}],
                  "required_runs": 2, "result_fixture": ".research/fixture.json"}
        path = self.storage / "preflight.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        not_run = r.preflight(self.project, self.storage)
        self.assertFalse(not_run["ready"])
        self.assertEqual(not_run["readiness_scope"], "runner_prerequisites_and_declared_project_checks")
        self.assertEqual(not_run["project_checks"], "not_run")
        ready = r.preflight(self.project, self.storage, True)
        self.assertTrue(ready["ready"], ready)
        self.assertEqual(ready["project_checks"], "passed")
        self.assertEqual(ready["scientific_acceptance"], "not_automatically_assessed")
        receipt = r.check_preflight(self.project, self.storage)
        completed = subprocess.run([sys.executable, "-X", "utf8", "-B", str(RUNNER), "reconcile", "--project", str(self.project),
                                    "--no-inherited-notes", "--rationale", "New synthetic fixture"], capture_output=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        prepared = r.prepare(self.project, self.storage, argparse.Namespace(label="preflight fixture", hypothesis="", replicate=False))
        directory, manifest = r.read_manifest(self.storage, prepared["id"])
        self.assertEqual(manifest["preflight_record"], receipt)
        r.verify_snapshot(self.storage, directory, manifest)
        self.file.write_bytes(b"new candidate")
        with self.assertRaises(r.ResearchError):
            r.check_preflight(self.project, self.storage)
        git("add", "review.md")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "new candidate")
        with self.assertRaises(r.ResearchError):
            r.check_preflight(self.project, self.storage)
        config["required_runs"] = 999
        path.write_text(json.dumps(config), encoding="utf-8")
        self.assertFalse(r.preflight(self.project, self.storage, True)["ready"])
        config["required_runs"] = 1
        config["checks"][0]["command"] = ["{python}", "-c", "import definitely_missing_evrik_fixture_module"]
        path.write_text(json.dumps(config), encoding="utf-8")
        failed = r.preflight(self.project, self.storage, True)
        self.assertFalse(failed["ready"])
        self.assertEqual(failed["checks"][0]["status"], "failed")
        fixture.write_text('{"metrics": {"wrong": 1}}', encoding="utf-8")
        malformed = r.preflight(self.project, self.storage, True)
        self.assertFalse(malformed["ready"])
        self.assertIn("missing primary metric", malformed["issue"])
        self.assertEqual(r.record_entries(self.storage)[-1]["result"], malformed)

        config["result_fixture"] = None
        config["checks"][0].update(command=["{python}", "-c", "pass"], timeout_seconds=10 ** 400)
        path.write_text(json.dumps(config), encoding="utf-8")
        overflow = r.preflight(self.project, self.storage, True)
        self.assertFalse(overflow["ready"])
        self.assertTrue(overflow["issue"])
        entry = r.record_entries(self.storage)[-1]
        self.assertEqual(entry["result"], overflow)
        self.assertEqual(r.read_json(self.storage / "preflight-latest.json")["record_id"], entry["id"])

        raw = json.dumps(config).replace(str(10 ** 400), "1e400")
        path.write_text(raw, encoding="utf-8")
        nonfinite = r.preflight(self.project, self.storage, True)
        self.assertFalse(nonfinite["ready"])
        self.assertTrue(nonfinite["issue"])
        self.assertEqual(r.record_entries(self.storage)[-1]["result"], nonfinite)
        self.assertEqual(path.read_text(encoding="utf-8"), raw)


if __name__ == "__main__":
    unittest.main()
