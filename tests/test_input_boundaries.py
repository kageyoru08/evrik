"""Missing integrity, portable-path, argv, and numerical boundary checks.

The existing test_research suite owns duplicate JSON/schema/status, mutated
result/log bytes, dirty tracked files, frozen-checkout/GIT_* isolation, and
large/mixed integer controls. These tests extend those cases rather than repeat
them. Rewritten ZIP hashes below are a deliberate fixture device for reaching
the archive validator, not a claim of resistance to coherent evidence forgery.
"""
from __future__ import annotations

from contextlib import contextmanager
from fractions import Fraction
import hashlib
import io
import json
import math
import os
from pathlib import Path
import runpy
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from run_demo import RUNNER, git, make_project


def identity(value):
    """Serialize the documented identity format without importing the runner."""
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class InputBoundaryTests(unittest.TestCase):
    def setUp(self):
        utf8 = patch.dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        utf8.start()
        self.addCleanup(utf8.stop)
        self.temporary = tempfile.TemporaryDirectory(prefix="research inputs ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = make_project(self.root / "project")
        self.marker = self.root / "evaluator-starts.txt"
        self.canary = self.root / "outside-canary.txt"
        self.canary.write_bytes(b"owned outside canary\n")
        original = (self.project / "evaluate.py").read_text(encoding="utf-8")
        self.commit_file("evaluate.py", self.launch_marker_code() + original)

    def launch_marker_code(self):
        return ("from pathlib import Path\n"
                f"with Path({str(self.marker)!r}).open('a', encoding='utf-8') as stream: stream.write('launch\\n')\n")

    def invoke(self, operation, *args, expected=0):
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(RUNNER), operation,
             "--project", str(self.project), *args],
            capture_output=True, text=True, encoding="utf-8", timeout=30, env=dict(os.environ),
        )
        self.assertEqual(proc.returncode, expected, proc.stderr or proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)
        payload = json.loads(proc.stderr if expected == 2 else proc.stdout)
        if expected == 2:
            self.assertIsInstance(payload["error"], str)
        return payload

    def prepare(self, label="boundary", *extra):
        return self.invoke("prepare", "--label", label, *extra)["id"]

    def registered_review(self):
        note = self.project / ".research/history.md"
        note.write_bytes(b"Preserve the committed evaluator before another launch.\n")
        (self.project / ".research/reference.py").write_bytes((self.project / "evaluate.py").read_bytes())
        unit = self.invoke("reconcile", "--note", ".research/history.md")["coverage"][0]["id"]
        self.invoke("reconcile", "--unit", unit, "--disposition", "verify", "--rationale", "Check the inherited evaluator.",
                    "--reference", ".research/reference.py", "--current", "evaluate.py")
        return unit

    def test_reconciliation_path_and_range_inputs_cannot_escape_or_activate_empty_review(self):
        before = self.inventory()
        self.invoke("reconcile", "--unit", "invented", "--disposition", "context",
                    "--rationale", "No source was registered.", expected=2)
        self.assertEqual(self.inventory(), before)
        for name in (str(self.canary), "../outside-canary.txt", "nested/../../outside-canary.txt",
                     ".git/config", ".research/reconciliation/review.json", "nested\\note.md"):
            with self.subTest(path=name):
                self.invoke("reconcile", "--note", name, expected=2)
                self.assertEqual(self.inventory(), before)
        unit = self.registered_review()
        for extra in (("--reference", "../outside-canary.txt"), ("--current", ".git/config"),
                      ("--current-range", "-1:2"), ("--current-range", "0:999999"),
                      ("--reference-range", "1:1"), ("--reference-revision", "--help")):
            with self.subTest(selector=extra):
                before = self.inventory()
                argv = ["--reference", ".research/reference.py", "--current", "evaluate.py"]
                if extra[0] in argv:
                    index = argv.index(extra[0])
                    argv[index:index + 2] = extra
                else:
                    argv.extend(extra)
                argv = [argv[index] + "=" + argv[index + 1] for index in range(0, len(argv), 2)]
                self.invoke("reconcile", "--unit", unit, "--disposition", "verify", "--rationale", "Invalid selector control.",
                            *argv, expected=2)
                self.assertEqual(self.inventory(), before)
        self.assert_no_execution()

    def test_reconciliation_missing_stale_and_invalid_receipts_refuse_without_claim_effects(self):
        self.registered_review()
        run_id = self.prepare("registered-snapshot")
        path = self.project / ".research/reconciliation/review.json"
        original = path.read_bytes()
        envelope = json.loads(original)
        cases = [None, original[:len(original) // 2]]
        for field, value in (("sources", []), ("events", []), ("events", None), ("id", [])):
            changed = json.loads(original)
            changed["review"][field] = value
            changed["sha256"] = identity(changed["review"])
            cases.append(json.dumps(changed).encode("utf-8"))
        cases.append(json.dumps(dict(envelope, sha256="0" * 64)).encode("utf-8"))
        changed = json.loads(original)
        changed["review"]["events"][0]["observation"]["equal"] = False
        changed["sha256"] = identity(changed["review"])
        cases.append(json.dumps(changed).encode("utf-8"))
        for value in cases:
            with self.subTest(record=value is None), self.altered_file(path, value):
                before = self.inventory()
                self.invoke("prepare", "--label", "invalid-review", expected=2)
                self.invoke("run", "--id", run_id, expected=2)
                self.assertEqual(self.inventory(), before)
                self.assert_no_execution()
        reference = self.project / ".research/reference.py"
        with self.altered_file(reference, b"changed reference\n"):
            before = self.inventory()
            self.assertIn("Stale reconciliation reference", self.invoke("run", "--id", run_id, expected=2)["error"])
            self.assertEqual(self.inventory(), before)
            self.assert_no_execution()
        manifest = self.run_path(run_id) / "manifest.json"
        changed = json.loads(manifest.read_bytes())
        changed["reconciliation"]["sha256"] = "0" * 64
        with self.altered_file(manifest, json.dumps(changed).encode("utf-8")):
            before = self.inventory()
            self.invoke("run", "--id", run_id, expected=2)
            self.assertEqual(self.inventory(), before)
            self.assert_no_execution()

    def test_reconciliation_interrupted_atomic_publication_preserves_previous_evidence(self):
        unit = self.registered_review()
        run_id = self.prepare("before-publication-failure")
        path = self.project / ".research/reconciliation/review.json"
        original = path.read_bytes()
        ready, release = self.root / "review-ready", self.root / "review-release"
        wrapper = self.root / "review_barrier.py"
        wrapper.write_text(
            "import importlib.util,os,sys,time\nfrom pathlib import Path\n"
            f"spec = importlib.util.spec_from_file_location('tested_runner', {str(RUNNER)!r})\n"
            "runner = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(runner)\n"
            "real_replace = os.replace\n"
            "def held_replace(source, destination):\n"
            " if Path(destination).name == 'review.json':\n"
            f"  Path({str(ready)!r}).write_text('ready')\n"
            "  deadline = time.monotonic() + 15\n"
            f"  while not Path({str(release)!r}).exists():\n"
            "   if time.monotonic() > deadline: raise RuntimeError('Test release missing')\n"
            "   time.sleep(0.01)\n"
            " return real_replace(source, destination)\n"
            "os.replace = held_replace\nraise SystemExit(runner.main())\n", encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "-B", str(wrapper), "reconcile", "--project", str(self.project), "--unit", unit,
             "--disposition", "unresolved", "--rationale", "Controlled interrupted reclassification."],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(ready.exists(), "The real flushed review temporary was not reached")
            process.kill()
            process.communicate(timeout=5)
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(list(path.parent.glob(".review.json.*.tmp")))
            self.assertEqual(self.invoke("run", "--id", run_id)["status"], "completed")
        finally:
            release.write_text("release", encoding="utf-8")
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    def test_lost_registration_directory_cannot_reenter_as_a_legacy_project(self):
        self.registered_review()
        run_id = self.prepare("retained-registration-receipt")
        directory = self.project / ".research/reconciliation"
        held = self.project / ".research/held-reconciliation"
        self.assertTrue(directory.resolve().is_relative_to(self.project.resolve()))
        self.assertTrue(held.resolve().is_relative_to(self.project.resolve()))
        directory.rename(held)
        try:
            original = self.inventory()
            for action, arguments in (("prepare", ("--label", "cannot-drop-known-history")),
                                      ("run", ("--id", run_id)),
                                      ("reconcile", ("--note", ".research/history.md"))):
                with self.subTest(action=action):
                    failure = self.invoke(action, *arguments, expected=2)
                    self.assertIn("retained run receipts prove prior registration", failure["error"])
                    self.assertEqual(self.inventory(), original)
                    self.assert_no_execution()
        finally:
            held.rename(directory)
        self.assertEqual(self.invoke("run", "--id", run_id)["status"], "completed")

    def test_reconciliation_unicode_json_survives_legacy_stdout_encoding(self):
        original = "前の較正を保持する。\n\nCafé evidence remains historical.\n"
        (self.project / ".research/history.md").write_bytes(original.encode("utf-8"))
        with patch.dict(os.environ, PYTHONIOENCODING="cp1252"):
            review = self.invoke("reconcile", "--note", ".research/history.md")
            inspected = self.invoke("reconcile")
            missing = self.invoke("reconcile", "--note", ".research/存在しない.md", expected=2)
        self.assertEqual(review["review"], inspected["review"])
        self.assertEqual("".join(unit["text"] for unit in review["coverage"]), original)
        self.assertIn("存在しない.md", missing["error"])
        self.assert_no_execution()

    def test_concurrent_reconciliation_dispositions_retain_both_workers(self):
        (self.project / ".research/history.md").write_bytes(b"The first result is historical context.\n\nThe second survey is independent work.\n")
        review = self.invoke("reconcile", "--note", ".research/history.md")
        processes = [subprocess.Popen(
            [sys.executable, "-B", str(RUNNER), "reconcile", "--project", str(self.project), "--unit", item["id"],
             "--disposition", "context" if index == 0 else "independent", "--rationale", f"Worker {index} source disposition."],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ) for index, item in enumerate(review["coverage"])]
        try:
            outputs = [process.communicate(timeout=20) for process in processes]
            self.assertEqual([process.returncode for process in processes], [0, 0], outputs)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
        completed = self.invoke("reconcile")
        self.assertEqual(len(completed["review"]["events"]), 2)
        self.assertEqual({item["disposition"]["disposition"] for item in completed["coverage"]}, {"context", "independent"})
        self.prepare("both-dispositions-retained")
        self.assert_no_execution()

    def test_live_git_keeps_inherited_trust_without_routing_or_child_leaks(self):
        runner = runpy.run_path(str(RUNNER), run_name="runner_under_test")
        alternate = make_project(self.root / "unrelated repository")
        original = (self.project / "evaluate.py").read_text(encoding="utf-8")
        self.commit_file("evaluate.py", "import os\nassert not any(k.upper().startswith('GIT_') for k in os.environ)\n" + original)
        values = [str(alternate), "", str(self.project), str(self.project) + "/*"]
        environment = {
            "GIT_CONFIG_COUNT": "5", "GIT_DIR": str(alternate / ".git"),
            "GIT_WORK_TREE": str(alternate),
            "GIT_CONFIG_KEY_4": "researchlab.should-not-survive",
            "GIT_CONFIG_VALUE_4": "discard-this-injected-setting",
        }
        for index, value in enumerate(values):
            environment[f"GIT_CONFIG_KEY_{index}"] = "safe.directory" if index != 2 else "SAFE.directory"
            environment[f"GIT_CONFIG_VALUE_{index}"] = value
        with patch.dict(os.environ, environment):
            actual = runner["git"](self.project, "config", "--get-all", "safe.directory").decode("utf-8").splitlines()
            self.assertEqual(actual[-len(values):], values)
            with self.assertRaises(runner["ResearchError"]):
                runner["git"](self.project, "config", "--get", "researchlab.should-not-survive")
            top = runner["git"](self.project, "rev-parse", "--show-toplevel").decode().strip()
            self.assertEqual(Path(top).resolve(), self.project.resolve())
            self.assertTrue(runner["ignored"](self.project))
            self.registered_review()
            run_id = self.prepare("native trust context")
            result = self.invoke("run", "--id", run_id)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(self.marker.read_text(encoding="utf-8").splitlines()), 1)

    def test_live_git_environment_preserves_only_active_ordered_trust(self):
        runner = runpy.run_path(str(RUNNER), run_name="runner_under_test")
        inherited = {"RESEARCH_UNRELATED": "unchanged", "GIT_DIR": "elsewhere",
                     "GIT_CONFIG_COUNT": "0005", "GIT_CONFIG_KEY_0": "SAFE.directory",
                     "GIT_CONFIG_VALUE_0": " first path ", "GIT_CONFIG_KEY_1": "other.setting",
                     "GIT_CONFIG_VALUE_1": "discard", "GIT_CONFIG_KEY_2": "safe.directory",
                     "GIT_CONFIG_VALUE_2": "", "GIT_CONFIG_KEY_3": "safe.directory",
                     "GIT_CONFIG_VALUE_3": "repo/*", "GIT_CONFIG_KEY_4": "safe.directory",
                     "GIT_CONFIG_VALUE_4": "repo/*", "GIT_CONFIG_KEY_9": "safe.directory",
                     "GIT_CONFIG_VALUE_9": "*"}
        expected = {"RESEARCH_UNRELATED": "unchanged", "GIT_CONFIG_COUNT": "4"}
        for index, value in enumerate([" first path ", "", "repo/*", "repo/*"]):
            expected[f"GIT_CONFIG_KEY_{index}"] = "safe.directory"
            expected[f"GIT_CONFIG_VALUE_{index}"] = value
        with patch.dict(os.environ, inherited, clear=True):
            self.assertEqual(runner["live_git_environment"](), expected)
            self.assertEqual(runner["without_git_environment"](), {"RESEARCH_UNRELATED": "unchanged"})
        for count in (None, "", "0"):
            case = dict(inherited)
            case.pop("GIT_CONFIG_COUNT")
            if count is not None:
                case["GIT_CONFIG_COUNT"] = count
            with self.subTest(inactive_count=count), patch.dict(os.environ, case, clear=True):
                self.assertEqual(runner["live_git_environment"](), {"RESEARCH_UNRELATED": "unchanged"})
        lowercase = {"git_config_count": "1", "git_config_key_0": "safe.directory",
                     "git_config_value_0": "repo"}
        with patch.dict(os.environ, lowercase, clear=True):
            outgoing = runner["live_git_environment"]()
            self.assertEqual(outgoing, {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
                                       "GIT_CONFIG_VALUE_0": "repo"} if os.name == "nt" else lowercase)

    def test_live_git_rejects_malformed_and_mixed_trust_configuration(self):
        runner = runpy.run_path(str(RUNNER), run_name="runner_under_test")
        valid = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": "repo"}
        cases = [dict(valid, GIT_CONFIG_COUNT=value)
                 for value in ("-1", "+1", " 1", "1.0", "١", "9" * 5000, "2")]
        cases += [{key: value for key, value in valid.items() if key != missing}
                  for missing in ("GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0")]
        cases.append(dict(valid, GIT_CONFIG_KEY_0=""))
        for name in ("GIT_CONFIG_PARAMETERS", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
                     "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG"):
            cases.append(dict(valid, **{name: "'safe.directory'=''"}))
        for key in ("include.path", "includeIf.gitdir:repo.path", "INCLUDE.path"):
            cases.append(dict(valid, GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_1=key,
                              GIT_CONFIG_VALUE_1="other-config"))
        for index, case in enumerate(cases):
            with self.subTest(case=index), patch.dict(os.environ, case, clear=True):
                with self.assertRaises(runner["ResearchError"]):
                    runner["live_git_environment"]()
        before = self.inventory()
        with patch.dict(os.environ, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="", GIT_CONFIG_VALUE_0="x"):
            self.invoke("inspect", expected=2)
        self.assertEqual(self.inventory(), before)
        self.assert_no_execution()

    def test_check_ignore_distinguishes_not_ignored_from_git_failure(self):
        runner = runpy.run_path(str(RUNNER), run_name="runner_under_test")
        for status, expected in ((0, True), (1, False), (128, None)):
            with self.subTest(status=status), patch.object(subprocess, "run", return_value=
                    subprocess.CompletedProcess([], status, b"", b"fatal fixture")):
                if expected is None:
                    with self.assertRaisesRegex(runner["ResearchError"], "Git check-ignore failed"):
                        runner["ignored"](self.project)
                else:
                    self.assertEqual(runner["ignored"](self.project), expected)

    def run_path(self, run_id):
        return self.project / ".research/runs" / run_id

    def commit_file(self, name, text):
        target = self.project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git(self.project, "add", "--", name)
        git(self.project, "commit", "-m", "Record owned boundary fixture")

    def protocol(self, change):
        path = self.project / ".research/protocol.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        change(value)
        path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")

    def inventory(self):
        return {str(path.relative_to(self.project / ".research")): path.read_bytes()
                for path in (self.project / ".research").rglob("*") if path.is_file()}

    def assert_no_execution(self):
        self.assertFalse(self.marker.exists(), "The evaluator started before rejection")
        self.assertEqual(self.canary.read_bytes(), b"owned outside canary\n")
        self.assertEqual(self.invoke("inspect")["launch_claims_used"], 0)

    @contextmanager
    def altered_file(self, path, value):
        original = path.read_bytes()
        if value is None:
            path.unlink()
        else:
            path.write_bytes(value)
        try:
            yield
        finally:
            path.write_bytes(original)

    def test_missing_evidence_and_frozen_identity_reject_without_reconstruction(self):
        baseline = self.prepare("baseline")
        candidate = self.prepare("candidate", "--replicate")
        for run_id in (baseline, candidate):
            self.invoke("run", "--id", run_id)
        self.assertEqual(self.invoke("compare", "--baseline", baseline, "--candidate", candidate)["outcome"],
                         "no_improvement")
        original_inventory = self.inventory()
        original_marker = self.marker.read_bytes()
        directory = self.run_path(candidate)
        manifest_path = directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # Existing controls own byte mutation of source/result/log and deletion
        # of individual claims. Here each absent file stays absent until the
        # fixture restores it, and frozen identity is changed one field at a time.
        cases = [(name + " removed", directory / name, None)
                 for name in ("source.zip", "result.json", "run.log", "manifest.json")]
        cases.append(("ledger removed", self.project / ".research/launches.json", None))
        for field in ("protocol_sha256", "data", "id", "fingerprint"):
            changed = json.loads(json.dumps(manifest))
            if field == "data":
                changed[field][0]["sha256"] = "0" * 64
            elif field == "id":
                changed[field] = baseline
            else:
                changed[field] = "0" * 64
            cases.append((field + " changed", manifest_path, json.dumps(changed).encode("utf-8")))
        for label, path, contents in cases:
            with self.subTest(corruption=label), self.altered_file(path, contents):
                corrupted_inventory = self.inventory()
                self.invoke("compare", "--baseline", baseline, "--candidate", candidate, expected=2)
                self.invoke("run", "--id", candidate, expected=2)
                self.assertEqual(self.inventory(), corrupted_inventory,
                                 "Rejecting corruption must not reconstruct or rewrite evidence")
                self.assertEqual(self.marker.read_bytes(), original_marker)
                self.assertEqual(self.canary.read_bytes(), b"owned outside canary\n")
            self.assertEqual(self.inventory(), original_inventory)
        self.assertEqual(self.invoke("compare", "--baseline", baseline, "--candidate", candidate)["outcome"],
                         "no_improvement")

    def rewrite_archive_fixture(self, run_id, extra_members, truncated=False):
        directory = self.run_path(run_id)
        archive_path = directory / "source.zip"
        with zipfile.ZipFile(archive_path) as original:
            members = [(entry, original.read(entry)) for entry in original.infolist()]
        output = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # Intentional duplicate-member fixture.
            with zipfile.ZipFile(output, "w") as archive:
                for name, contents in [*members, *extra_members]:
                    if isinstance(name, str):
                        # ZipInfo's constructor normalizes Windows backslashes.
                        # Preserve the intended on-disk bytes explicitly, then
                        # independently inspect orig_filename after reopening.
                        entry = zipfile.ZipInfo(name)
                        entry.filename = entry.orig_filename = name
                    else:
                        entry = name
                    archive.writestr(entry, contents)
        raw = output.getvalue()
        with zipfile.ZipFile(io.BytesIO(raw)) as check:
            expected_names = [entry.orig_filename for entry, _ in members] + [
                name.orig_filename if isinstance(name, zipfile.ZipInfo) else name for name, _ in extra_members]
            self.assertEqual([entry.orig_filename for entry in check.infolist()], expected_names)
            for entry, _ in extra_members:
                if isinstance(entry, zipfile.ZipInfo):
                    stored = check.getinfo(entry.filename)
                    self.assertEqual((stored.create_system, stored.external_attr),
                                     (entry.create_system, entry.external_attr))
        archive_path.write_bytes(raw[:len(raw) // 2] if truncated else raw)
        manifest_path = directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["source"]["archive_sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        manifest["fingerprint"] = identity({key: manifest[key] for key in
                                            ("source", "protocol_sha256", "data", "environment")})
        manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    def test_archive_validator_rejects_unsafe_members_before_extraction(self):
        source_placeholder = self.project / ".research/runs/run-placeholder/source-placeholder"
        traversal = os.path.relpath(self.canary, source_placeholder).replace(os.sep, "/")
        drive_path = (self.canary.as_posix() if self.canary.drive else
                      "C:/" + self.canary.as_posix().lstrip("/"))
        unc_path = ("//localhost/" + self.canary.drive[0] + "$" + self.canary.as_posix()[2:]
                    if self.canary.drive else "//localhost" + self.canary.as_posix())
        unsafe_names = {
            "traversal": traversal,
            "absolute": "/" + self.canary.as_posix().lstrip("/"),
            "drive": drive_path,
            "unc": unc_path,
            "backslash": "nested\\owned-path-probe.txt",
            "raw_nul": "nested/null\x00suffix.txt",
            "reserved": "nested/CON.txt",
            "reserved_extension": "nested/lPt9.log",
            "trailing_dot": "nested/name.",
            "trailing_space": "nested/name ",
            "git_metadata": ".git/config",
            "research_metadata": ".research/launches.json",
        }
        cases = [(label, [(name, b"rejected")], "snapshot path")
                 for label, name in unsafe_names.items()]
        cases.extend([
            ("case collision", [("DATA.JSON", b"rejected")], "case-colliding"),
            ("duplicate member", [("data.json", b"rejected")], "Duplicate"),
            ("file parent overlap", [("occupied", b"file"), ("occupied/child", b"child")], "overlaps"),
            ("file directory overlap", [("occupied/", b""), ("occupied", b"file")], "Duplicate"),
        ])
        # Safe names reach the ZIP member-type consumer, independently of the
        # prepare-time Git symlink/submodule guard. No special OS file is made.
        for label, kind in (("symlink", stat.S_IFLNK), ("character device", stat.S_IFCHR),
                            ("fifo", stat.S_IFIFO)):
            entry = zipfile.ZipInfo("typed-member-" + label.replace(" ", "-"))
            entry.create_system = 3  # Unix mode bits, including on Windows.
            entry.external_attr = (kind | 0o600) << 16
            cases.append((label, [(entry, str(self.canary).encode("utf-8"))], "Unsupported snapshot file"))
        self.protocol(lambda p: p["budget"].update(max_runs=len(cases)))
        for label, entries, reason in cases:
            with self.subTest(archive=label):
                # Keep each deliberately malformed archive in its own run. If a
                # regression launches one, its claim and result stay intact and
                # cannot turn later cases into misleading relaunch failures.
                run_id = self.prepare("archive " + label, "--replicate")
                marker_before = self.marker.read_bytes() if self.marker.exists() else None
                claims_before = self.invoke("inspect")["launch_claims_used"]
                self.rewrite_archive_fixture(run_id, entries)
                before = self.inventory()
                failure = self.invoke("run", "--id", run_id, expected=2)
                self.assertIn(reason, failure["error"], "Must reach the path validator, not the stale hash guard")
                self.assertEqual(self.inventory(), before)
                self.assertEqual(sorted(path.name for path in self.run_path(run_id).iterdir()),
                                 ["manifest.json", "source.zip"])
                self.assertEqual(self.marker.read_bytes() if self.marker.exists() else None, marker_before)
                self.assertEqual(self.invoke("inspect")["launch_claims_used"], claims_before)
                self.assertEqual(self.canary.read_bytes(), b"owned outside canary\n")

    def test_wrong_shape_identity_fields_fail_at_their_actual_consumers(self):
        baseline = self.prepare("shape baseline")
        candidate = self.prepare("shape candidate", "--replicate")
        pending = self.prepare("shape pending", "--replicate")
        for run_id in (baseline, candidate):
            self.invoke("run", "--id", run_id)
        marker_before = self.marker.read_bytes()
        cases = [(field, value) for field in ("environment", "runtime_environment")
                 for value in (None, [], "malformed")]
        cases.extend(("data", value) for value in ([None], [42], [{}]))
        for field, value in cases:
            # Prepared runtime_environment is overwritten by launch and is not a
            # consumer input. Comparison must validate the recorded runtime.
            consumers = [(candidate, "compare", ("--baseline", baseline, "--candidate", candidate))]
            if field != "runtime_environment":
                consumers.append((pending, "run", ("--id", pending)))
            for run_id, operation, args in consumers:
                with self.subTest(field=field, value=value, consumer=operation):
                    path = self.run_path(run_id) / "manifest.json"
                    changed = json.loads(path.read_text(encoding="utf-8"))
                    changed[field] = value
                    with self.altered_file(path, json.dumps(changed).encode("utf-8")):
                        before = self.inventory()
                        detail = self.invoke("inspect", "--id", run_id)
                        self.assertEqual(detail[field], value)
                        self.invoke(operation, *args, expected=2)
                        self.assertEqual(self.inventory(), before)
                        self.assertEqual(self.marker.read_bytes(), marker_before)
                        self.assertEqual(self.invoke("inspect")["launch_claims_used"], 2)

    def test_truncated_archive_is_rejected_with_a_matching_fixture_hash(self):
        run_id = self.prepare("truncated-zip")
        self.rewrite_archive_fixture(run_id, [], truncated=True)
        before = self.inventory()
        failure = self.invoke("run", "--id", run_id, expected=2)
        self.assertIn("zip file", failure["error"].lower())
        self.assertEqual(self.inventory(), before)
        self.assert_no_execution()

    def test_committed_symlink_and_submodule_modes_reject_before_allocation(self):
        for mode, name in (("120000", "committed-link"), ("160000", "committed-module")):
            with self.subTest(git_mode=mode):
                if mode == "120000":
                    git(self.project, "config", "core.symlinks", "false")
                    hashed = subprocess.run(
                        ["git", "-C", str(self.project), "hash-object", "-w", "--stdin"],
                        input=str(self.canary), capture_output=True, text=True, encoding="utf-8", check=True,
                    ).stdout.strip()
                else:
                    hashed = git(self.project, "rev-parse", "HEAD")
                git(self.project, "update-index", "--add", "--cacheinfo", f"{mode},{hashed},{name}")
                if mode == "120000":
                    git(self.project, "checkout-index", "--force", "--", name)
                else:
                    (self.project / name).mkdir()
                git(self.project, "commit", "-m", "Record unsupported Git mode")
                self.assertEqual(git(self.project, "status", "--porcelain=v1"), "")
                self.assertIn(mode, git(self.project, "ls-tree", "HEAD", "--", name))
                failure = self.invoke("prepare", "--label", mode, expected=2)
                self.assertIn("symlinks or submodules", failure["error"])
                self.assert_no_execution()
                self.assertEqual(self.invoke("inspect")["runs"], [])
                git(self.project, "rm", "--cached", "--", name)
                path = self.project / name
                path.rmdir() if path.is_dir() else path.unlink()
                git(self.project, "commit", "-m", "Remove owned unsupported-mode fixture")

    @contextmanager
    def redirected_storage(self, junction=False):
        storage = self.project / ".research"
        held = self.root / "held-research"
        self.assertTrue(storage.resolve().is_relative_to(self.root.resolve()))
        self.assertTrue(held.resolve().is_relative_to(self.root.resolve()))
        storage.rename(held)
        linked = False
        try:
            if junction:
                powershell = shutil.which("powershell.exe")
                if powershell is None:
                    self.skipTest("Windows junction construction unavailable: powershell.exe not installed")
                proc = subprocess.run(
                    [powershell, "-NoProfile", "-NonInteractive", "-Command",
                     "$ErrorActionPreference = 'Stop'; New-Item -ItemType Junction -Path $env:RESEARCH_TEST_LINK -Target $env:RESEARCH_TEST_TARGET | Out-Null"],
                    env=dict(os.environ, RESEARCH_TEST_LINK=str(storage), RESEARCH_TEST_TARGET=str(held)),
                    capture_output=True, text=True, encoding="utf-8", timeout=60,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
            else:
                try:
                    storage.symlink_to(held, target_is_directory=True)
                except OSError as exc:
                    if os.name == "nt" and getattr(exc, "winerror", None) in (1, 50, 1314):
                        self.skipTest(f"Windows storage symlink construction unsupported: {exc}")
                    raise
            linked = True
            self.assertEqual(storage.resolve(), held.resolve())
            yield held
        finally:
            if linked:
                if junction:
                    os.rmdir(storage)  # Removes the owned junction itself, never its target.
                else:
                    storage.unlink()
            held.rename(storage)

    def check_redirected_storage(self, junction):
        run_id = self.prepare("storage-link")
        original = self.inventory()
        with self.redirected_storage(junction) as held:
            for operation, args in (("inspect", ()), ("prepare", ("--label", "blocked")),
                                    ("run", ("--id", run_id))):
                with self.subTest(operation=operation):
                    failure = self.invoke(operation, *args, expected=2)
                    self.assertRegex(failure["error"], "link|junction")
            self.assertEqual({str(path.relative_to(held)): path.read_bytes()
                              for path in held.rglob("*") if path.is_file()}, original)
            self.assertFalse(self.marker.exists())
            self.assertEqual(self.canary.read_bytes(), b"owned outside canary\n")
        self.assertEqual(self.inventory(), original)
        self.assert_no_execution()

    def test_storage_symlink_is_rejected_without_touching_its_target(self):
        self.check_redirected_storage(junction=False)

    @unittest.skipUnless(os.name == "nt", "Junctions are a Windows storage boundary")
    def test_storage_junction_is_rejected_without_touching_its_target(self):
        self.check_redirected_storage(junction=True)

    def test_unicode_space_paths_and_shell_metacharacters_are_literal_argv(self):
        unicode_project = self.root / "project café 測定"
        self.project.rename(unicode_project)
        self.project = unicode_project
        script = "experiments space/測定 café.py"
        data_path = "données space/数値.txt"
        self.commit_file(data_path, "portable Unicode data\n")
        received = self.root / "received-argv.json"
        shell_canary = self.root / "shell-interpreted.txt"
        values = ["two words", "測定 café", "; echo injected", "&& echo injected", "| echo injected",
                  f"> {shell_canary}", "$(echo injected)", "`echo injected`", "%PATH%", "$HOME", "*.json", 'a"b']
        evaluator = (self.launch_marker_code() + "import json,sys\n"
                     f"assert Path({data_path!r}).read_text(encoding='utf-8') == 'portable Unicode data\\n'\n"
                     f"Path({str(received)!r}).write_text(json.dumps(sys.argv[2:], ensure_ascii=False), encoding='utf-8')\n"
                     "Path(sys.argv[1]).write_text('{\"metrics\":{\"mse\":1}}', encoding='utf-8')\n")
        self.commit_file(script, evaluator)
        self.protocol(lambda p: p.update(command=["{python}", script, "{result}", *values], data_paths=[data_path]))
        run_id = self.prepare("Unicode path control")
        result = self.invoke("run", "--id", run_id)
        self.assertEqual(result["evidence"]["status"], "valid")
        self.assertEqual(json.loads(received.read_text(encoding="utf-8")), values)
        self.assertFalse(shell_canary.exists())
        self.assertEqual(self.marker.read_text(encoding="utf-8").splitlines(), ["launch"])
        self.assertEqual(result["data"][0]["path"], data_path)
        self.assertEqual(self.canary.read_bytes(), b"owned outside canary\n")

    def test_missing_declared_data_and_untracked_source_reject_before_allocation(self):
        self.protocol(lambda p: p.update(data_paths=["missing.csv"]))
        failure = self.invoke("prepare", "--label", "missing-data", expected=2)
        self.assertIn("Declared data file missing", failure["error"])
        self.assertEqual(self.invoke("inspect")["runs"], [])
        self.protocol(lambda p: p.update(data_paths=["data.json"]))
        untracked = self.project / "untracked analysis.txt"
        untracked.write_bytes(b"preserve untracked work\n")
        failure = self.invoke("prepare", "--label", "untracked", expected=2)
        self.assertIn("Git tree must be clean", failure["error"])
        self.assertEqual(untracked.read_bytes(), b"preserve untracked work\n")
        self.assertEqual(self.invoke("inspect")["runs"], [])
        self.assert_no_execution()

    def test_git_change_during_prepare_rejects_at_a_deterministic_archive_barrier(self):
        reached, release = self.root / "archive-ready", self.root / "release-archive"
        wrapper = self.root / "prepare_barrier.py"
        # Test-only adapter: the real Git archive finishes first; no production
        # hooks or timing guess determines when the source commit changes.
        wrapper.write_text(
            "import importlib.util,sys,time\nfrom pathlib import Path\n"
            f"spec = importlib.util.spec_from_file_location('tested_runner', {str(RUNNER)!r})\n"
            "runner = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(runner)\n"
            "real_git = runner.git\n"
            "def blocked_git(project, *args):\n"
            " result = real_git(project, *args)\n"
            " if 'archive' in args and '--format=zip' in args:\n"
            f"  Path({str(reached)!r}).write_text('ready', encoding='utf-8')\n"
            "  deadline = time.monotonic() + 15\n"
            f"  while not Path({str(release)!r}).exists():\n"
            "   if time.monotonic() > deadline: raise RuntimeError('Test barrier release missing')\n"
            "   time.sleep(0.01)\n"
            " return result\n"
            "runner.git = blocked_git\nraise SystemExit(runner.main())\n", encoding="utf-8")
        previous_commit = git(self.project, "rev-parse", "HEAD")
        proc = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-B", str(wrapper), "prepare", "--project", str(self.project),
             "--label", "controlled-change"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        )
        try:
            deadline = time.monotonic() + 10
            while not reached.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(reached.exists(), "Archive barrier was not reached")
            self.commit_file("model.json", '{"method":"linear"}\n')
            changed_commit = git(self.project, "rev-parse", "HEAD")
            self.assertNotEqual(changed_commit, previous_commit)
            release.write_text("release", encoding="utf-8")
            stdout, stderr = proc.communicate(timeout=20)
            self.assertEqual(proc.returncode, 2, stderr or stdout)
            self.assertNotIn("Traceback", stderr)
            self.assertIn("Git state changed during prepare", json.loads(stderr)["error"])
            self.assertEqual(git(self.project, "rev-parse", "HEAD"), changed_commit)
            self.assertEqual(git(self.project, "status", "--porcelain=v1"), "")
            self.assertEqual(list((self.project / ".research/runs").iterdir()), [])
            self.assert_no_execution()
        finally:
            release.write_text("release", encoding="utf-8")
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)

    def numeric_pair(self, baseline, candidate, label):
        ids = []
        for index, value in enumerate((baseline, candidate)):
            raw_result = json.dumps({"metrics": {"mse": value}}, allow_nan=False)
            evaluator = (self.launch_marker_code() + f"# {label} side {index}\nimport sys\n"
                         f"Path(sys.argv[2]).write_text({raw_result!r}, encoding='utf-8')\n")
            self.commit_file("evaluate.py", evaluator)
            run_id = self.prepare(label)
            self.invoke("run", "--id", run_id)
            self.assertEqual((self.run_path(run_id) / "result.json").read_text(encoding="utf-8"), raw_result)
            ids.append(run_id)
        return ids

    def test_adjacent_floats_match_an_independent_exact_rational_oracle(self):
        self.protocol(lambda p: p["budget"].update(max_runs=12))
        for direction, candidate in (("maximize", math.nextafter(1.0, math.inf)),
                                     ("minimize", math.nextafter(1.0, 0.0))):
            exact_gain = abs(Fraction.from_float(candidate) - Fraction(1))
            exact_threshold = float(exact_gain)
            thresholds = (math.nextafter(exact_threshold, 0.0), exact_threshold,
                          math.nextafter(exact_threshold, math.inf))
            for index, threshold in enumerate(thresholds):
                with self.subTest(direction=direction, threshold_position=index):
                    self.protocol(lambda p: p["metric"].update(direction=direction, min_improvement=threshold))
                    baseline_id, candidate_id = self.numeric_pair(1.0, candidate, f"{direction}-{index}")
                    result = self.invoke("compare", "--baseline", baseline_id, "--candidate", candidate_id)
                    expected = "win" if exact_gain >= Fraction.from_float(threshold) else "no_improvement"
                    self.assertEqual(Fraction.from_float(result["absolute_improvement"]), exact_gain)
                    self.assertEqual(result["outcome"], expected)

    def test_finite_float_metrics_with_overflowing_difference_reject(self):
        baseline, candidate = self.numeric_pair(sys.float_info.max, -sys.float_info.max, "float-overflow")
        before = self.inventory()
        failure = self.invoke("compare", "--baseline", baseline, "--candidate", candidate, expected=2)
        self.assertIn("finite number", failure["error"])
        self.assertEqual(self.inventory(), before)
        self.assertEqual(self.invoke("inspect")["launch_claims_used"], 2)


if __name__ == "__main__":
    unittest.main()
