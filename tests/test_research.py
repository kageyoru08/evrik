"""Black-box checks of the local runner and the shipped example."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from run_demo import RUNNER, command, git, make_project


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="research lab test ")
        self.addCleanup(self.temporary.cleanup)
        self.project = make_project(Path(self.temporary.name) / "project")

    def protocol(self, change):
        path = self.project / ".research/protocol.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        change(value)
        path.write_text(json.dumps(value) + "\n", encoding="utf-8")

    def prepare(self, label="test", *extra):
        return command(self.project, "prepare", "--label", label, *extra)["id"]

    def run_path(self, run_id):
        return self.project / ".research/runs" / run_id

    def invoke(self, action, *args, expected):
        result = subprocess.run(
            [sys.executable, str(RUNNER), action, "--project", str(self.project), *args],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, expected, result.stderr or result.stdout)
        payload = json.loads(result.stderr if expected == 2 else result.stdout)
        if expected == 2:
            self.assertIsInstance(payload["error"], str)
        return payload

    def commit_file(self, name, contents):
        (self.project / name).write_text(contents, encoding="utf-8")
        git(self.project, "add", name)
        git(self.project, "commit", "-m", "Change isolated test fixture")

    def inherited_review(self):
        self.commit_file("protected.txt", "Preserve the inherited calibration.\n")
        raw = b"The earlier trial is historical context.\r\n\r\nPreserve the reference calibration in current committed source.\r\n"
        (self.project / ".research/history.md").write_bytes(raw)
        (self.project / ".research/reference.txt").write_bytes((self.project / "protected.txt").read_bytes())
        review = command(self.project, "reconcile", "--note", ".research/history.md")
        units = review["coverage"]
        self.assertEqual("".join(unit["text"] for unit in units).encode("utf-8"), raw)
        self.assertEqual(units[-1]["end_byte"], len(raw))
        return [unit["id"] for unit in units]

    def disposition(self, unit, value, *extra):
        return command(self.project, "reconcile", "--unit", unit, "--disposition", value,
                       "--rationale", "Explicit test classification of the inherited text.", *extra)

    def verify_inherited(self, unit):
        return self.disposition(unit, "verify", "--reference", ".research/reference.txt",
                                "--current", "protected.txt")

    def test_reconciliation_covers_all_text_and_keeps_failed_prerequisites(self):
        context, obligation = self.inherited_review()
        self.disposition(context, "context")
        failure = self.invoke("prepare", "--label", "omitted", expected=2)
        self.assertIn("pending or unresolved", failure["error"])
        self.assertEqual(command(self.project, "inspect")["runs"], [])
        original = (self.project / ".research/reference.txt").read_bytes()
        (self.project / ".research/reference.txt").write_bytes(b"A different recorded calibration.\n")
        failed = self.verify_inherited(obligation)
        self.assertFalse(failed["coverage"][1]["required_comparison"]["equal"])
        self.assertNotEqual(failed["coverage"][1]["required_comparison"]["reference"]["sha256"],
                            failed["coverage"][1]["required_comparison"]["committed"]["sha256"])
        self.disposition(obligation, "context")
        failure = self.invoke("prepare", "--label", "label-is-not-resolution", expected=2)
        self.assertIn("comparison failed", failure["error"])
        (self.project / ".research/reference.txt").write_bytes(original)
        resolved = self.verify_inherited(obligation)
        self.assertTrue(resolved["coverage"][1]["required_comparison"]["equal"])
        self.assertEqual(len(resolved["review"]["events"]), 4)
        self.assertEqual(resolved["review"]["events"][1], failed["review"]["events"][1])
        run_id = self.prepare("resolved")
        self.assertEqual(command(self.project, "run", "--id", run_id)["status"], "completed")

    def test_entry_decision_required_and_no_history_retained(self):
        self.project = make_project(Path(self.temporary.name) / "cold-project", declare_entry=False)
        storage = self.project / ".research"
        protocol = (storage / "protocol.json").read_bytes()
        self.assertEqual(command(self.project, "init")["entry_status"], "required")
        self.assertEqual((storage / "protocol.json").read_bytes(), protocol)
        self.assertEqual(command(self.project, "reconcile")["entry_status"], "required")
        self.assertIn("Entry decision required", self.invoke("prepare", "--label", "missing", expected=2)["error"])
        self.assertFalse((storage / "runs").exists())
        self.assertFalse((storage / "launches.json").exists())
        for options in [("--no-inherited-notes",), ("--no-inherited-notes", "--rationale", " "),
                        ("--no-inherited-notes", "--rationale", "none", "--note", "history.md")]:
            self.invoke("reconcile", *options, expected=2)
        self.assertFalse((storage / "reconciliation").exists())
        rationale = "Fresh synthetic test; no inherited investigation."
        declared = command(self.project, "reconcile", "--no-inherited-notes", "--rationale", rationale)
        self.assertFalse(declared["registered"])
        self.assertFalse(declared["machine_verified"])
        self.assertEqual(declared["entry_status"], "no_inherited_material_declared")
        self.assertEqual(declared["review"]["sources"], [])
        record_path = storage / "reconciliation/review.json"
        original = record_path.read_bytes()
        command(self.project, "reconcile", "--no-inherited-notes", "--rationale", rationale)
        self.invoke("reconcile", "--no-inherited-notes", "--rationale", "Replace the assertion", expected=2)
        self.assertEqual(record_path.read_bytes(), original)
        self.assertEqual(command(self.project, "init")["entry_status"], declared["entry_status"])
        # Even with a recomputed checksum, an empty source list needs a valid declaration.
        invalid = json.loads(original)
        invalid["review"]["no_inherited_material"] = None
        invalid["sha256"] = hashlib.sha256(json.dumps(invalid["review"], sort_keys=True,
                                                      separators=(",", ":")).encode()).hexdigest()
        record_path.write_text(json.dumps(invalid), encoding="utf-8")
        self.invoke("prepare", "--label", "invalid-entry", expected=2)
        self.assertFalse((storage / "runs").exists())
        record_path.write_bytes(original)
        completed = self.prepare("declared")
        self.assertEqual(self.prepare("same-declaration"), completed)
        self.assertEqual(command(self.project, "run", "--id", completed)["status"], "completed")
        unclaimed = self.prepare("before-selected-notes", "--replicate")
        previous_manifest = (self.run_path(unclaimed) / "manifest.json").read_bytes()
        (storage / "history.md").write_text("The earlier result is baseline context.\n", encoding="utf-8")
        selected = command(self.project, "reconcile", "--note", ".research/history.md")
        self.assertEqual(selected["review"]["id"], declared["review"]["id"])
        self.assertEqual(selected["review"]["no_inherited_material"], declared["review"]["no_inherited_material"])
        self.assertIn("pending or unresolved", self.invoke("prepare", "--label", "pending", expected=2)["error"])
        self.assertIn("cannot be cleared", self.invoke("reconcile", "--no-inherited-notes",
                                                      "--rationale", rationale, expected=2)["error"])
        self.disposition(selected["coverage"][0]["id"], "context")
        failure = self.invoke("run", "--id", unclaimed, expected=2)
        self.assertIn("predates selected-note registration", failure["error"])
        self.assertEqual((self.run_path(unclaimed) / "manifest.json").read_bytes(), previous_manifest)
        self.assertEqual(command(self.project, "inspect")["launch_claims_used"], 1)
        fresh = self.prepare("selected-notes")
        self.assertNotEqual(fresh, unclaimed)
        self.assertEqual(command(self.project, "run", "--id", fresh)["status"], "completed")

    def test_registration_preserves_legacy_run_and_reprepare_can_allocate(self):
        self.assertFalse(command(self.project, "reconcile")["registered"])
        baseline = self.prepare("legacy-baseline")
        command(self.project, "run", "--id", baseline)
        self.commit_file("model.json", '{"method":"linear"}\n')
        candidate = self.prepare("legacy-candidate")
        command(self.project, "run", "--id", candidate)
        legacy = self.prepare("legacy-prepared", "--replicate")
        # Isolated legacy-shaped records, not fabricated historical qualification evidence.
        for run_id in (baseline, candidate, legacy):
            path = self.run_path(run_id) / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest.pop("reconciliation")
            path.write_text(json.dumps(manifest), encoding="utf-8")
        record_path = self.project / ".research/reconciliation/review.json"
        record_path.unlink()
        record_path.parent.rmdir()
        preserved = {path: path.read_bytes() for path in [self.project / ".research/launches.json"] + [
            self.run_path(run_id) / name for run_id in (baseline, candidate, legacy)
            for name in ("manifest.json", "source.zip")]}
        self.assertEqual(command(self.project, "reconcile")["entry_status"], "required")
        self.assertEqual(command(self.project, "inspect")["launch_claims_used"], 2)
        self.assertEqual(command(self.project, "compare", "--baseline", baseline,
                                 "--candidate", candidate)["outcome"], "win")
        self.assertIn("already has a launch claim", self.invoke("run", "--id", baseline, expected=2)["error"])
        self.assertIn("Entry decision required", self.invoke("run", "--id", legacy, expected=2)["error"])
        (self.project / ".research/history.md").write_text("The previous result is only a baseline.\n", encoding="utf-8")
        registered = command(self.project, "reconcile", "--note", ".research/history.md")
        unit = registered["coverage"][0]["id"]
        # An existing schema-1 selected-note record is accepted and updated without migration.
        schema_one = json.loads(record_path.read_text(encoding="utf-8"))
        schema_one["review"]["schema_version"] = 1
        schema_one["review"].pop("no_inherited_material")
        schema_one["sha256"] = hashlib.sha256(json.dumps(schema_one["review"], sort_keys=True,
                                                        separators=(",", ":")).encode()).hexdigest()
        record_path.write_text(json.dumps(schema_one), encoding="utf-8")
        saved_schema_one = record_path.read_bytes()
        self.assertEqual(command(self.project, "reconcile")["review"]["schema_version"], 1)
        self.assertEqual(record_path.read_bytes(), saved_schema_one)
        self.disposition(unit, "context")
        self.assertEqual(command(self.project, "reconcile")["review"]["schema_version"], 1)
        original = (self.run_path(legacy) / "manifest.json").read_bytes()
        failure = self.invoke("run", "--id", legacy, expected=2)
        self.assertIn("prepare a new attributable run", failure["error"])
        fresh = self.prepare("after-registration")
        self.assertNotEqual(fresh, legacy)
        self.assertEqual(self.prepare("same-review"), fresh)
        old = json.loads(original)
        new = command(self.project, "inspect", "--id", fresh)
        self.assertEqual(old["fingerprint"], new["fingerprint"], "Review metadata is not scientific identity")
        self.assertEqual((self.run_path(legacy) / "manifest.json").read_bytes(), original)
        for path, raw in preserved.items():
            self.assertEqual(path.read_bytes(), raw, str(path))
        self.assertEqual(command(self.project, "inspect")["launch_claims_used"], 2)
        self.assertEqual(command(self.project, "run", "--id", fresh)["status"], "completed")
        self.assertEqual(command(self.project, "inspect")["launch_claims_used"], 3)

    def test_reconciliation_is_current_at_launch_but_protects_each_prepared_snapshot(self):
        context, obligation = self.inherited_review()
        self.disposition(context, "context")
        self.verify_inherited(obligation)
        old_id = self.prepare("old-source")
        original_receipt = command(self.project, "inspect", "--id", old_id)["reconciliation"]
        # Unrelated source commits do not require semantic reclassification.
        self.commit_file("model.json", '{"method":"linear"}\n')
        new_id = self.prepare("unrelated-change")
        self.assertEqual(command(self.project, "inspect", "--id", new_id)["reconciliation"], original_receipt)
        # Changed protected bytes require fresh computed evidence before any claim.
        self.commit_file("protected.txt", "An explicitly revised calibration.\n")
        failure = self.invoke("run", "--id", old_id, expected=2)
        self.assertIn("Stale reconciliation", failure["error"])
        self.assertEqual(command(self.project, "inspect")["launch_claims_used"], 0)
        (self.project / ".research/reference.txt").write_bytes((self.project / "protected.txt").read_bytes())
        self.verify_inherited(obligation)
        history = self.project / ".research/history.md"
        history.write_bytes(history.read_bytes() + b"\nAn unresolved external survey can wait while this independent regression runs.\n")
        self.invoke("run", "--id", old_id, expected=2)
        updated = command(self.project, "reconcile", "--note", ".research/history.md")
        self.invoke("run", "--id", old_id, expected=2)
        for unit in updated["coverage"]:
            if unit["disposition"] is None:
                if "Preserve the reference" in unit["text"]:
                    self.verify_inherited(unit["id"])
                else:
                    self.disposition(unit["id"], "independent")
        old = command(self.project, "run", "--id", old_id)
        new = command(self.project, "run", "--id", new_id)
        self.assertEqual(old["reconciliation"], original_receipt)
        self.assertEqual(old["evidence"]["metrics"]["mse"], 21.0)
        self.assertEqual(new["evidence"]["metrics"]["mse"], 0.0)
        self.assertEqual(command(self.project, "compare", "--baseline", old_id, "--candidate", new_id)["outcome"], "win")
        latest = command(self.project, "reconcile")
        self.assertEqual(len(latest["review"]["sources"]), 2)
        self.assertIn("independent", [item["disposition"]["disposition"] for item in latest["coverage"]])

    def test_note_refresh_carries_pending_and_failed_units_until_explicit_revalidation(self):
        context, obligation = self.inherited_review()
        original = (self.project / ".research/reference.txt").read_bytes()
        (self.project / ".research/reference.txt").write_bytes(b"The wrong calibration.\n")
        self.verify_inherited(obligation)
        (self.project / ".research/history.md").write_bytes(b"An updated handoff note.\n")
        updated = command(self.project, "reconcile", "--note", ".research/history.md")
        self.assertEqual({unit["id"] for unit in updated["coverage"] if unit["carried_forward"]}, {context, obligation})
        for unit in updated["coverage"]:
            if not unit["carried_forward"]:
                self.disposition(unit["id"], "context")
        self.assertIn("pending or unresolved", self.invoke("prepare", "--label", "pending-history", expected=2)["error"])
        self.disposition(context, "completed")
        self.disposition(obligation, "independent")
        self.assertIn("comparison failed", self.invoke("prepare", "--label", "failed-history", expected=2)["error"])
        (self.project / ".research/reference.txt").write_bytes(original)
        self.verify_inherited(obligation)
        self.prepare("explicitly-revalidated-history")
        current = command(self.project, "reconcile")
        carried = [unit for unit in current["coverage"] if unit["carried_forward"]]
        self.assertEqual([unit["id"] for unit in carried], [obligation])
        self.assertTrue(carried[0]["required_comparison"]["equal"])
        self.assertEqual(len(current["review"]["sources"]), 2)

    def test_new_protected_selector_requires_a_new_preparation(self):
        context, obligation = self.inherited_review()
        self.disposition(context, "context")
        self.verify_inherited(obligation)
        old_id = self.prepare("before-new-dependency")
        original = (self.run_path(old_id) / "manifest.json").read_bytes()
        (self.project / ".research/new-history.md").write_bytes(b"The committed evaluator must also preserve the inherited version.\n")
        (self.project / ".research/reference.py").write_bytes((self.project / "evaluate.py").read_bytes())
        updated = command(self.project, "reconcile", "--note", ".research/new-history.md")
        new_unit = next(unit["id"] for unit in updated["coverage"] if unit["path"] == ".research/new-history.md")
        self.disposition(new_unit, "verify", "--reference", ".research/reference.py", "--current", "evaluate.py")
        failure = self.invoke("run", "--id", old_id, expected=2)
        self.assertIn("new protected selector", failure["error"])
        self.assertEqual((self.run_path(old_id) / "manifest.json").read_bytes(), original)
        self.assertEqual(command(self.project, "inspect")["launch_claims_used"], 0)
        new_id = self.prepare("after-new-dependency")
        self.assertNotEqual(old_id, new_id)
        self.assertEqual(command(self.project, "run", "--id", new_id)["status"], "completed")

    def test_reconciliation_byte_ranges_and_git_reference_read_actual_content(self):
        self.commit_file("protected.txt", "prefix\nretained\nsuffix\n")
        reference_bytes = (self.project / "protected.txt").read_bytes()
        retained = reference_bytes.splitlines(keepends=True)[1]
        start = reference_bytes.index(retained)
        selected_range = f"{start}:{start + len(retained)}"
        reference_commit = git(self.project, "rev-parse", "HEAD")
        (self.project / ".research/history.md").write_text("Only the retained line is protected.\n", encoding="utf-8")
        review = command(self.project, "reconcile", "--note", ".research/history.md")
        unit = review["coverage"][0]["id"]
        self.commit_file("protected.txt", "PREFIX\nretained\nSUFFIX\n")
        # Neither whole-file identity nor a commit subject can satisfy this relation.
        result = self.disposition(unit, "verify", "--reference", "protected.txt",
                                  "--reference-revision", reference_commit,
                                  "--current", "protected.txt", "--reference-range", selected_range,
                                  "--current-range", selected_range)
        observed = result["coverage"][0]["required_comparison"]
        self.assertNotEqual(observed["reference"]["file_sha256"], observed["current"]["file_sha256"])
        self.assertEqual(observed["reference"]["sha256"], hashlib.sha256(retained).hexdigest())
        self.assertEqual(observed["reference"]["origin"]["commit"], reference_commit)
        self.assertEqual(command(self.project, "run", "--id", self.prepare("partial-content"))["status"], "completed")
        self.disposition(unit, "verify", "--reference", "protected.txt", "--reference-revision", reference_commit,
                         "--current", "protected.txt")
        self.assertIn("comparison failed", self.invoke("prepare", "--label", "whole-file-mismatch", expected=2)["error"])

    def test_prepared_code_is_unchanged_by_later_checkout_edits(self):
        baseline = self.prepare("baseline")
        self.commit_file("model.json", '{"method":"linear"}\n')
        candidate = self.prepare("candidate")
        old = command(self.project, "run", "--id", baseline)
        new = command(self.project, "run", "--id", candidate)
        self.assertEqual(old["evidence"]["metrics"]["mse"], 21.0)
        self.assertEqual(new["evidence"]["metrics"]["mse"], 0.0)
        comparison = command(self.project, "compare", "--baseline", baseline, "--candidate", candidate)
        self.assertEqual(comparison["outcome"], "win")
        self.assertEqual(comparison["absolute_improvement"], 21.0)
        for run_id in (baseline, candidate):
            for name in ("manifest.json", "source.zip", "result.json", "run.log"):
                self.assertTrue((self.run_path(run_id) / name).is_file(), name)

    def test_dirty_source_is_rejected_without_allocating_a_run(self):
        (self.project / "model.json").write_text('{"method":"linear"}\n', encoding="utf-8")
        self.invoke("prepare", "--label", "dirty", expected=2)
        self.assertEqual(command(self.project, "inspect")["runs"], [])

    def test_duplicate_json_keys_are_rejected_in_every_evidence_document(self):
        protocol_path = self.project / ".research/protocol.json"
        original_protocol = protocol_path.read_text(encoding="utf-8")
        protocol_path.write_text(original_protocol.rstrip()[:-1] + ',"name":"ambiguous"}', encoding="utf-8")
        self.invoke("prepare", "--label", "duplicate-protocol", expected=2)
        self.assertEqual(command(self.project, "inspect")["runs"], [])
        protocol_path.write_text(original_protocol, encoding="utf-8")
        baseline = self.prepare("valid-json")
        command(self.project, "run", "--id", baseline)
        payload = '{"metrics":{"mse":100,"mse":0}}'
        self.commit_file("evaluate.py", "import sys\nfrom pathlib import Path\nPath(sys.argv[2]).write_text(" + repr(payload) + ", encoding='utf-8')\n")
        candidate = self.prepare("duplicate-result")
        result = self.invoke("run", "--id", candidate, expected=1)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["evidence"]["status"], "invalid")
        self.assertIn("Duplicate JSON", result["evidence"]["reason"])
        self.invoke("compare", "--baseline", baseline, "--candidate", candidate, expected=2)
        for path in (self.project / ".research/launches.json", self.run_path(baseline) / "manifest.json"):
            with self.subTest(document=path.name):
                original = path.read_text(encoding="utf-8")
                path.write_text(original.rstrip()[:-1] + ',"schema_version":1}', encoding="utf-8")
                try:
                    failure = self.invoke("inspect", expected=2)
                    self.assertIn("Duplicate JSON", failure["error"])
                finally:
                    path.write_text(original, encoding="utf-8")

    def test_ledger_reconciliation_rejects_loss_and_preserves_crash_claims(self):
        self.protocol(lambda p: p["budget"].update(max_runs=1))
        first = self.prepare("launched")
        second = self.prepare("unlaunched", "--replicate")
        command(self.project, "run", "--id", first)
        ledger_path = self.project / ".research/launches.json"
        original_ledger = ledger_path.read_text(encoding="utf-8")
        ledger_path.write_text('{"schema_version":1,"claims":{}}', encoding="utf-8")
        try:
            failure = self.invoke("run", "--id", second, expected=2)
            self.assertIn("missing its claim", failure["error"])
            self.invoke("inspect", expected=2)
            self.assertFalse((self.run_path(second) / "run.log").exists())
        finally:
            ledger_path.write_text(original_ledger, encoding="utf-8")
        directory = self.run_path(first)
        held = directory.with_name(directory.name + ".held")
        self.assertTrue(directory.resolve().is_relative_to(self.project.resolve()))
        self.assertTrue(held.resolve().is_relative_to(self.project.resolve()))
        directory.rename(held)
        try:
            failure = self.invoke("inspect", expected=2)
            self.assertIn("missing run evidence", failure["error"])
            self.invoke("run", "--id", second, expected=2)
        finally:
            held.rename(directory)
        # A durable claim may precede the manifest's transition out of prepared.
        crash_ledger = json.loads(original_ledger)
        crash_ledger["claims"][second] = {"claimed_at": "2026-01-01T00:00:00+00:00"}
        ledger_path.write_text(json.dumps(crash_ledger), encoding="utf-8")
        inspected = command(self.project, "inspect", "--id", second)
        self.assertEqual(inspected["status"], "prepared")
        self.assertTrue(inspected["launch_claimed"])
        self.assertTrue(inspected["unresolved"])
        self.invoke("run", "--id", second, expected=2)
        self.assertFalse((self.run_path(second) / "run.log").exists())
        self.assertEqual(command(self.project, "inspect")["launch_claims_used"], 2)

    def test_manifest_status_and_schema_versions_fail_with_json_errors(self):
        baseline = self.prepare("baseline")
        candidate = self.prepare("candidate", "--replicate")
        for run_id in (baseline, candidate):
            command(self.project, "run", "--id", run_id)
        path = self.run_path(candidate) / "manifest.json"
        original = path.read_text(encoding="utf-8")
        for field, value in (("status", []), ("status", "future-state"),
                             ("schema_version", True), ("schema_version", 999)):
            with self.subTest(field=field, value=value):
                changed = json.loads(original)
                changed[field] = value
                path.write_text(json.dumps(changed), encoding="utf-8")
                try:
                    self.invoke("inspect", "--id", candidate, expected=2)
                    self.invoke("compare", "--baseline", baseline, "--candidate", candidate, expected=2)
                finally:
                    path.write_text(original, encoding="utf-8")
        ledger_path = self.project / ".research/launches.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["schema_version"] = True
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
        self.invoke("inspect", expected=2)

    def test_nested_manifest_containers_reject_before_any_new_launch(self):
        baseline = self.prepare("valid-baseline")
        candidate = self.prepare("valid-candidate", "--replicate")
        for run_id in (baseline, candidate):
            command(self.project, "run", "--id", run_id)
        prepared = self.prepare("not-yet-launched", "--replicate")
        ledger_path = self.project / ".research/launches.json"
        ledger_before = ledger_path.read_bytes()
        missing = object()
        mutations = {
            "source": (missing, None, [], "malformed", 17),
            "evidence": (missing, None, [], "malformed", 17),
            "source.commit": (missing, None, [], 17, "", "bad\u0000commit"),
        }
        for run_id in (prepared, candidate):
            path = self.run_path(run_id) / "manifest.json"
            original = path.read_bytes()
            for field, values in mutations.items():
                for value in values:
                    with self.subTest(state=run_id == prepared, field=field,
                                      value="<missing>" if value is missing else value):
                        mutated = json.loads(original)
                        parent = mutated["source"] if field == "source.commit" else mutated
                        key = "commit" if field == "source.commit" else field
                        if value is missing:
                            del parent[key]
                        else:
                            parent[key] = value
                        path.write_text(json.dumps(mutated), encoding="utf-8")
                        try:
                            self.invoke("inspect", "--id", run_id, expected=2)
                            self.invoke("run", "--id", run_id, expected=2)
                            if run_id == candidate:
                                self.invoke("compare", "--baseline", baseline, "--candidate", candidate, expected=2)
                            self.assertEqual(ledger_before, ledger_path.read_bytes())
                            self.assertFalse((self.run_path(prepared) / "run.log").exists())
                        finally:
                            path.write_bytes(original)
        self.assertEqual(command(self.project, "compare", "--baseline", baseline,
                                 "--candidate", candidate)["outcome"], "no_improvement")

    def test_source_commit_is_validated_before_persisting_a_launch_claim(self):
        for index, value in enumerate((None, [], 17, "", "bad\u0000commit")):
            with self.subTest(value=value):
                self.project = make_project(Path(self.temporary.name) / f"commit-value-{index}")
                run_id = self.prepare("environment-value")
                path = self.run_path(run_id) / "manifest.json"
                original = path.read_bytes()
                mutated = json.loads(original)
                mutated["source"]["commit"] = value
                # Deliberately update the fixture checksum to reach the environment
                # value boundary. This is not a coherent-tampering security claim.
                inputs = {key: mutated[key] for key in ("source", "protocol_sha256", "data", "environment")}
                raw = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                mutated["fingerprint"] = hashlib.sha256(raw).hexdigest()
                path.write_text(json.dumps(mutated), encoding="utf-8")
                try:
                    self.invoke("run", "--id", run_id, expected=2)
                    self.assertFalse((self.project / ".research/launches.json").exists())
                    self.assertFalse((self.run_path(run_id) / "run.log").exists())
                    self.assertFalse((self.run_path(run_id) / "result.json").exists())
                finally:
                    path.write_bytes(original)

    def test_comparison_rejects_exit_and_secondary_metric_type_lookalikes(self):
        evaluator = (
            "import sys\nfrom pathlib import Path\n"
            "Path(sys.argv[2]).write_text('{\"metrics\":{\"mse\":2,\"secondary\":1}}', encoding='utf-8')\n"
        )
        self.commit_file("evaluate.py", evaluator)
        baseline = self.prepare("baseline-types")
        candidate = self.prepare("candidate-types", "--replicate")
        for run_id in (baseline, candidate):
            command(self.project, "run", "--id", run_id)
        path = self.run_path(candidate) / "manifest.json"
        original = path.read_bytes()
        ledger_before = (self.project / ".research/launches.json").read_bytes()
        for field, value in (("exit_code", False), ("exit_code", 0.0), ("secondary", True)):
            with self.subTest(field=field, value=value):
                mutated = json.loads(original)
                if field == "secondary":
                    mutated["evidence"]["metrics"][field] = value
                else:
                    mutated[field] = value
                path.write_text(json.dumps(mutated), encoding="utf-8")
                try:
                    self.invoke("compare", "--baseline", baseline, "--candidate", candidate, expected=2)
                    self.assertEqual(ledger_before, (self.project / ".research/launches.json").read_bytes())
                finally:
                    path.write_bytes(original)
        # Numeric integer/float equivalence is permitted; Boolean substitution is not.
        numeric = json.loads(original)
        numeric["evidence"]["metrics"]["secondary"] = 1.0
        path.write_text(json.dumps(numeric), encoding="utf-8")
        self.assertEqual(command(self.project, "compare", "--baseline", baseline,
                                 "--candidate", candidate)["outcome"], "no_improvement")

    def test_advisory_metadata_preserves_claims_and_conservative_uncertainty(self):
        run_id = self.prepare("advisory-metadata")
        command(self.project, "run", "--id", run_id)
        path = self.run_path(run_id) / "manifest.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        ledger_path = self.project / ".research/launches.json"
        original_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        for value in (None, {}, [], False, 0, "uninterpreted"):
            with self.subTest(value=value):
                manifest = dict(original, status="launch_failed", cleanup=value)
                manifest.pop("process", None)
                path.write_text(json.dumps(manifest), encoding="utf-8")
                ledger = json.loads(json.dumps(original_ledger))
                ledger["claims"][run_id] = value
                ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
                detail = command(self.project, "inspect", "--id", run_id)
                self.assertTrue(detail["launch_claimed"])
                self.assertTrue(detail["unresolved"])
                self.assertEqual(command(self.project, "inspect")["launch_claims_used"], 1)
                self.invoke("run", "--id", run_id, expected=2)

    def test_changed_active_execution_caps_require_new_preparation(self):
        original_budget = json.loads((self.project / ".research/protocol.json").read_text(encoding="utf-8"))["budget"]
        run_id = self.prepare("prepared-budget")
        for change in ({"max_runs": 1}, {"timeout_seconds": 0.01}):
            with self.subTest(changed_cap=change):
                self.protocol(lambda p: p.update(budget={**original_budget, **change}))
                failure = self.invoke("run", "--id", run_id, expected=2)
                self.assertIn("prepare a new run", failure["error"])
                self.assertEqual(command(self.project, "inspect")["launch_claims_used"], 0)
                self.assertEqual(command(self.project, "inspect", "--id", run_id)["status"], "prepared")
                self.assertFalse((self.run_path(run_id) / "run.log").exists())
                self.assertFalse((self.run_path(run_id) / "result.json").exists())
        # Scientific metadata stays frozen; only changed execution caps block launch.
        self.protocol(lambda p: p.update(budget=original_budget, question="A changed active research question"))
        completed = command(self.project, "run", "--id", run_id)
        self.assertEqual(completed["status"], "completed")
        self.assertNotEqual(completed["protocol"]["question"], "A changed active research question")
        self.protocol(lambda p: p["budget"].update(max_runs=2))
        fresh = self.prepare("new-active-budget")
        command(self.project, "run", "--id", fresh)
        self.assertEqual(command(self.project, "inspect")["launch_claims_used"], 2)

    def test_git_discovery_cannot_attribute_live_checkout_data_to_snapshot(self):
        self.project = make_project(Path(self.temporary.name) / ("git" + os.pathsep + "project"))
        other = make_project(Path(self.temporary.name) / "other-project")
        self.commit_file("live_metric.txt", "123")
        evaluator = (
            "import json,os,subprocess,sys\nfrom pathlib import Path\n"
            "snapshot = Path(os.environ['RESEARCH_SOURCE_ROOT'])\n"
            "assert snapshot == Path.cwd()\n"
            "assert os.environ['RESEARCH_UNRELATED'] == 'preserved'\n"
            "print('snapshot_value=' + (snapshot / 'live_metric.txt').read_text(), flush=True)\n"
            "print('snapshot_commit=' + os.environ['RESEARCH_SOURCE_COMMIT'], flush=True)\n"
            "root = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip())\n"
            "metric = int((root / 'live_metric.txt').read_text())\n"
            "Path(sys.argv[2]).write_text(json.dumps({'metrics': {'mse': metric}}))\n"
        )
        self.commit_file("evaluate.py", evaluator)
        self.protocol(lambda p: p["data_paths"].append("live_metric.txt"))
        # Inherited routing must not override the runner's explicit --project.
        inherited = dict(os.environ, GIT_DIR=str(other / ".git"), GIT_WORK_TREE=str(other),
                         RESEARCH_UNRELATED="preserved", GIT_CONFIG_COUNT="2",
                         GIT_CONFIG_KEY_0="safe.directory", GIT_CONFIG_VALUE_0=str(self.project),
                         GIT_CONFIG_KEY_1="safe.directory", GIT_CONFIG_VALUE_1=str(self.project) + "/*")
        prepared = subprocess.run(
            [sys.executable, str(RUNNER), "prepare", "--project", str(self.project), "--label", "git-aware"],
            env=inherited, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        run_id = json.loads(prepared.stdout)["id"]
        recorded = command(self.project, "inspect", "--id", run_id)
        self.assertEqual(recorded["source"]["commit"], git(self.project, "rev-parse", "HEAD"))
        self.commit_file("live_metric.txt", "999")
        inherited.update(GIT_DIR=str(self.project / ".git"), GIT_WORK_TREE=str(self.project))
        executed = subprocess.run(
            [sys.executable, str(RUNNER), "run", "--project", str(self.project), "--id", run_id],
            env=inherited, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(executed.returncode, 1, executed.stderr or executed.stdout)
        result = json.loads(executed.stdout)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["evidence"]["status"], "invalid")
        self.assertFalse((self.run_path(run_id) / "result.json").exists())
        log = (self.run_path(run_id) / "run.log").read_text(encoding="utf-8")
        self.assertIn("snapshot_value=123", log)
        self.assertIn("snapshot_commit=" + recorded["source"]["commit"], log)
        self.assertIn("invalid gitfile format", log.lower())

    def test_integer_metric_improvement_preserves_exact_precision(self):
        self.protocol(lambda p: p["budget"].update(max_runs=16))
        cases = (
            (9007199254740993, 9007199254740992, "minimize", 1, "win"),
            (10 ** 400 + 1, 10 ** 400, "minimize", 1, "win"),
            (9007199254740995, 9007199254740994.0, "minimize", 2, "reject"),
            (10 ** 400, 1.0, "minimize", 1, "reject"),
            (3.0, 4, "maximize", 1, "win"),
            (6.0, 5.0, "minimize", 2, "no_improvement"),
            (7, 7.0, "minimize", 0, "no_improvement"),
        )
        for baseline_value, candidate_value, direction, threshold, outcome in cases:
            with self.subTest(baseline=baseline_value, candidate=candidate_value, direction=direction):
                self.protocol(lambda p: p["metric"].update(direction=direction, min_improvement=threshold))
                run_ids = []
                for value in (baseline_value, candidate_value):
                    payload = json.dumps({"metrics": {"mse": value}})
                    evaluator = "import sys\nfrom pathlib import Path\nPath(sys.argv[2]).write_text(" + repr(payload) + ", encoding='utf-8')\n"
                    self.commit_file("evaluate.py", evaluator)
                    run_id = self.prepare("numeric-metric")
                    command(self.project, "run", "--id", run_id)
                    run_ids.append(run_id)
                if outcome == "reject":
                    self.invoke("compare", "--baseline", run_ids[0], "--candidate", run_ids[1], expected=2)
                    continue
                comparison = command(self.project, "compare", "--baseline", run_ids[0], "--candidate", run_ids[1])
                self.assertEqual(comparison["baseline_value"], baseline_value)
                self.assertEqual(comparison["candidate_value"], candidate_value)
                self.assertEqual(comparison["absolute_improvement"], 0 if baseline_value == candidate_value else 1)
                self.assertEqual(comparison["outcome"], outcome)

    def test_deduplication_replication_and_launch_budget(self):
        self.protocol(lambda p: p["budget"].update(max_runs=1))
        first = command(self.project, "prepare", "--label", "first")
        reused = command(self.project, "prepare", "--label", "same-input")
        repeated = command(self.project, "prepare", "--label", "repeat", "--replicate")
        self.assertEqual(first["id"], reused["id"])
        self.assertTrue(reused["deduplicated"])
        self.assertNotEqual(first["id"], repeated["id"])
        command(self.project, "run", "--id", first["id"])
        self.invoke("run", "--id", repeated["id"], expected=2)
        overview = command(self.project, "inspect")
        self.assertEqual(overview["launch_claims_used"], 1)
        self.assertEqual(command(self.project, "inspect", "--id", repeated["id"])["status"], "prepared")

    def test_invalid_metric_is_not_valid_evidence(self):
        self.protocol(lambda p: p["budget"].update(max_runs=5))
        baseline = self.prepare("valid")
        command(self.project, "run", "--id", baseline)
        for label, payload in (("nonfinite", '{"metrics":{"mse":NaN}}'),
                               ("missing", '{"metrics":{"other":0}}'),
                               ("boolean", '{"metrics":{"mse":true}}'),
                               ("malformed", '{"metrics":')):
            with self.subTest(case=label):
                evaluator = "import sys\nfrom pathlib import Path\nPath(sys.argv[2]).write_text(" + repr(payload) + ", encoding='utf-8')\n"
                self.commit_file("evaluate.py", evaluator)
                candidate = self.prepare(label)
                result = self.invoke("run", "--id", candidate, expected=1)
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["exit_code"], 0)
                self.assertEqual(result["evidence"]["status"], "invalid")
                self.invoke("compare", "--baseline", baseline, "--candidate", candidate, expected=2)

    def test_concurrent_run_claims_enforce_single_launch_and_project_budget(self):
        for distinct in (False, True):
            with self.subTest(distinct_run_ids=distinct):
                if distinct:
                    self.project = make_project(Path(self.temporary.name) / "distinct-runs")
                marker = Path(self.temporary.name) / f"launches-{distinct}.txt"
                evaluator = (
                    "import sys,time\nfrom pathlib import Path\n"
                    f"with Path({str(marker)!r}).open('a') as stream: stream.write('launch\\n')\n"
                    "time.sleep(0.3)\n"
                    "Path(sys.argv[2]).write_text('{\"metrics\":{\"mse\":1}}')\n"
                )
                self.commit_file("evaluate.py", evaluator)
                self.protocol(lambda p: p["budget"].update(max_runs=1))
                first = self.prepare("first")
                second = self.prepare("second", "--replicate") if distinct else first
                processes = [subprocess.Popen(
                    [sys.executable, str(RUNNER), "run", "--project", str(self.project), "--id", run_id],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                ) for run_id in (first, second)]
                try:
                    outputs = [process.communicate(timeout=15) for process in processes]
                finally:
                    for process in processes:
                        if process.poll() is None:
                            process.kill()
                            process.communicate(timeout=5)
                self.assertEqual(sorted(process.returncode for process in processes), [0, 2], outputs)
                self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["launch"])
                overview = command(self.project, "inspect")
                self.assertEqual(overview["launch_claims_used"], 1)
                self.assertEqual(sum(run["launch_claimed"] for run in overview["runs"]), 1)

    def test_protocol_changes_make_runs_incomparable(self):
        baseline = self.prepare("original-protocol")
        command(self.project, "run", "--id", baseline)
        self.protocol(lambda p: p["comparability"].update(split="a different split"))
        candidate = self.prepare("changed-protocol")
        command(self.project, "run", "--id", candidate)
        self.invoke("compare", "--baseline", baseline, "--candidate", candidate, expected=2)

    def test_data_changes_make_runs_incomparable(self):
        baseline = self.prepare("original-data")
        command(self.project, "run", "--id", baseline)
        data = json.loads((self.project / "data.json").read_text(encoding="utf-8"))
        data["test"][0][1] += 1
        self.commit_file("data.json", json.dumps(data) + "\n")
        candidate = self.prepare("changed-data")
        command(self.project, "run", "--id", candidate)
        self.invoke("compare", "--baseline", baseline, "--candidate", candidate, expected=2)

    def test_tampered_source_is_rejected_before_launch(self):
        run_id = self.prepare()
        with (self.run_path(run_id) / "source.zip").open("ab") as archive:
            archive.write(b"changed after prepare")
        self.invoke("run", "--id", run_id, expected=2)
        self.assertFalse((self.run_path(run_id) / "result.json").exists())
        self.assertEqual(command(self.project, "inspect")["launch_claims_used"], 0)

    def test_changed_results_cannot_be_compared_as_original_evidence(self):
        baseline = self.prepare("baseline")
        candidate = self.prepare("replica", "--replicate")
        command(self.project, "run", "--id", baseline)
        command(self.project, "run", "--id", candidate)
        same = command(self.project, "compare", "--baseline", baseline, "--candidate", candidate)
        self.assertEqual(same["outcome"], "no_improvement")
        log = self.run_path(candidate) / "run.log"
        original_log = log.read_bytes()
        log.write_bytes(original_log + b"changed after completion")
        self.invoke("compare", "--baseline", baseline, "--candidate", candidate, expected=2)
        log.write_bytes(original_log)
        (self.run_path(candidate) / "result.json").write_text('{"metrics":{"mse":0}}\n', encoding="utf-8")
        self.invoke("compare", "--baseline", baseline, "--candidate", candidate, expected=2)

    def test_completed_and_unresolved_claims_are_never_relaunched(self):
        run_id = self.prepare()
        command(self.project, "run", "--id", run_id)
        directory = self.run_path(run_id)
        original_log = (directory / "run.log").read_bytes()
        original_result = (directory / "result.json").read_bytes()
        self.invoke("run", "--id", run_id, expected=2)
        # Simulate a stale on-disk state from an interrupted supervisor. No PID is used.
        path = directory / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["status"] = "running"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        inspected = command(self.project, "inspect", "--id", run_id)
        self.assertTrue(inspected["unresolved"])
        self.assertTrue(inspected["launch_claimed"])
        self.invoke("run", "--id", run_id, expected=2)
        self.assertEqual(command(self.project, "inspect")["launch_claims_used"], 1)
        self.assertEqual((directory / "run.log").read_bytes(), original_log)
        self.assertEqual((directory / "result.json").read_bytes(), original_result)

    def test_timeout_stops_the_owned_child_tree(self):
        marker = Path(self.temporary.name) / "child-survived.txt"
        started = Path(self.temporary.name) / "child-started.txt"
        child = "import sys,time; from pathlib import Path; Path(sys.argv[2]).write_text('started'); time.sleep(2); Path(sys.argv[1]).write_text('survived')"
        parent = "import subprocess,sys,time\nsubprocess.Popen([sys.executable, '-c', " + repr(child) + ", sys.argv[2], sys.argv[3]])\ntime.sleep(30)\n"
        self.commit_file("timeout.py", parent)
        def configure(protocol):
            protocol["command"] = ["{python}", "timeout.py", "{result}", str(marker), str(started)]
            protocol["budget"]["timeout_seconds"] = 1
        self.protocol(configure)
        run_id = self.prepare("timeout")
        result = self.invoke("run", "--id", run_id, expected=1)
        self.assertEqual(result["status"], "timed_out")
        self.assertEqual(result["evidence"]["status"], "invalid")
        self.assertTrue(started.exists(), "Child did not start, so cleanup was not exercised")
        self.assertTrue(result["cleanup"]["direct_child_reaped"])
        self.assertEqual(result["cleanup"]["descendant_state"], "unknown")
        self.assertNotIn("tree_termination_confirmed", result["cleanup"])
        self.assertTrue(command(self.project, "inspect", "--id", run_id)["unresolved"])
        time.sleep(1.3)
        self.assertFalse(marker.exists(), "Child survived timeout cleanup")
        self.invoke("run", "--id", run_id, expected=2)

    @unittest.skipIf(os.name == "nt", "POSIX detached-process regression")
    def test_detached_child_demonstrates_why_descendant_state_stays_unknown(self):
        started = Path(self.temporary.name) / "detached-started.txt"
        marker = Path(self.temporary.name) / "detached-completed.txt"
        child = "import sys,time; from pathlib import Path; Path(sys.argv[1]).write_text('started'); time.sleep(1); Path(sys.argv[2]).write_text('completed')"
        parent = (
            "import subprocess,sys,time\n"
            "subprocess.Popen([sys.executable, '-c', " + repr(child) + ", sys.argv[2], sys.argv[3]], "
            "start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
            "time.sleep(30)\n"
        )
        self.commit_file("detached.py", parent)
        def configure(protocol):
            protocol["command"] = ["{python}", "detached.py", "{result}", str(started), str(marker)]
            protocol["budget"]["timeout_seconds"] = 0.5
        self.protocol(configure)
        run_id = self.prepare("detached-child")
        result = self.invoke("run", "--id", run_id, expected=1)
        # The detached child exits itself after one second; wait before fixture cleanup.
        time.sleep(1.2)
        self.assertTrue(started.exists())
        self.assertTrue(marker.exists(), "Detached child did not exercise the unsupported cleanup scope")
        self.assertTrue(result["cleanup"]["signal_succeeded"])
        self.assertTrue(result["cleanup"]["direct_child_reaped"])
        self.assertEqual(result["cleanup"]["descendant_state"], "unknown")
        self.assertTrue(command(self.project, "inspect", "--id", run_id)["unresolved"])

    def test_failed_foreground_evaluator_leaves_descendants_unresolved(self):
        started = Path(self.temporary.name) / "worker-started.txt"
        heartbeat = Path(self.temporary.name) / "worker-heartbeat.txt"
        release = Path(self.temporary.name) / "worker-release.txt"
        finished = Path(self.temporary.name) / "worker-finished.txt"
        worker = (
            "import sys,time\nfrom pathlib import Path\n"
            "Path(sys.argv[1]).write_text('started')\n"
            "deadline = time.monotonic() + 10\n"
            "while not Path(sys.argv[3]).exists() and time.monotonic() < deadline:\n"
            " Path(sys.argv[2]).write_text(str(time.monotonic()))\n time.sleep(0.02)\n"
            "Path(sys.argv[4]).write_text('finished')\n"
        )
        evaluator = (
            "import os,subprocess,sys,threading,time\nfrom pathlib import Path\n"
            "def fail_after_start():\n"
            " deadline = time.monotonic() + 5\n"
            " while not Path(sys.argv[2]).exists() and time.monotonic() < deadline: time.sleep(0.01)\n"
            " os._exit(3)\n"
            "threading.Thread(target=fail_after_start, daemon=True).start()\n"
            "subprocess.run([sys.executable, '-c', " + repr(worker)
            + ", sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]], check=True)\n"
        )
        self.commit_file("failed.py", evaluator)
        self.protocol(lambda p: p.update(command=["{python}", "failed.py", "{result}",
                                                 str(started), str(heartbeat), str(release), str(finished)]))
        run_id = self.prepare("failed-foreground-evaluator")
        try:
            result = self.invoke("run", "--id", run_id, expected=1)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["exit_code"], 3)
            self.assertTrue(started.exists())
            before_inspect = heartbeat.stat().st_mtime_ns
            self.assertFalse(finished.exists())
            detail = command(self.project, "inspect", "--id", run_id)
            overview = command(self.project, "inspect")
            self.assertTrue(detail["unresolved"])
            self.assertTrue(overview["runs"][0]["unresolved"])
            self.assertEqual(overview["launch_claims_used"], 1)
            self.assertGreater(heartbeat.stat().st_mtime_ns, before_inspect, "Worker was not alive during inspection")
            self.assertFalse(finished.exists(), "Worker should remain held until the test releases it")
            self.invoke("run", "--id", run_id, expected=2)
        finally:
            release.write_text("stop", encoding="utf-8")
            deadline = time.monotonic() + 3
            while not finished.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(finished.exists(), "Worker did not finish after the test released it")

    def test_inspect_preserves_cleanup_uncertainty_in_detail_and_list(self):
        run_id = self.prepare("cleanup-state")
        command(self.project, "run", "--id", run_id)
        path = self.run_path(run_id) / "manifest.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for status in ("failed", "timed_out", "interrupted", "launch_failed"):
            for cleanup in (None, {}, {"tree_termination_confirmed": False}, {"tree_termination_confirmed": True}):
                with self.subTest(status=status, cleanup=cleanup):
                    manifest = dict(original, status=status, exit_code=-9 if status == "failed" else original["exit_code"])
                    manifest.pop("process", None)
                    if cleanup is not None:
                        manifest["cleanup"] = cleanup
                    path.write_text(json.dumps(manifest), encoding="utf-8")
                    expected = True  # Even a legacy true claim cannot certify detached descendants.
                    if status == "launch_failed" and cleanup is None:
                        expected = False  # Spawn failed before any child handle existed.
                    detail = command(self.project, "inspect", "--id", run_id)
                    listed = command(self.project, "inspect")["runs"][0]
                    self.assertEqual(detail["unresolved"], expected)
                    self.assertEqual(listed["unresolved"], expected)


class DemoTests(unittest.TestCase):
    def test_complete_demo_emits_a_traceable_report(self):
        with tempfile.TemporaryDirectory(prefix="research-lab-demo-test-") as temporary:
            result = subprocess.run(
                [sys.executable, str(ROOT / "examples/run_demo.py"), "--workspace", str(Path(temporary) / "demo")],
                capture_output=True, text=True, timeout=45,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            output = json.loads(result.stdout)
            report = json.loads(Path(output["report"]).read_text(encoding="utf-8"))
            self.assertEqual(report["comparison"]["baseline_value"], 21.0)
            self.assertEqual(report["comparison"]["candidate_value"], 0.0)
            self.assertEqual(report["comparison"]["outcome"], "win")
            self.assertEqual(report["baseline"]["evidence"]["status"], "valid")
            self.assertEqual(report["candidate"]["evidence"]["status"], "valid")


if __name__ == "__main__":
    unittest.main()
