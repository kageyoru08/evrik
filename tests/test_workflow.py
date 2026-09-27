"""Observable record, recovery and project preflight behavior; no model calls."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_evidence_stream import r, RUNNER


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="evrik workflow ")
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
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

    def test_non_git_compatibility_is_reported_before_setup(self):
        completed = subprocess.run([sys.executable, "-X", "utf8", "-B", str(RUNNER), "preflight", "--project", str(self.project)],
                                   capture_output=True, text=True, encoding="utf-8", timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        status = json.loads(completed.stdout)
        self.assertFalse(status["git_compatible"])
        self.assertFalse(status["ready"])
        self.assertTrue(status["non_git_support"]["immutable_records"])
        self.assertFalse((self.project / ".git").exists())

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
        ready = r.preflight(self.project, self.storage, True)
        self.assertTrue(ready["ready"], ready)
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


if __name__ == "__main__":
    unittest.main()
