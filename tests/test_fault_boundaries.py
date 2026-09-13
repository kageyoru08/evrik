"""Real subprocess fault and contention checks (standard library only).

R04 runs two repetitions of eight crash boundaries and five injected I/O
failures. R05 runs five synchronized mixed-contention waves. CI supplies the
OS/Python matrix; a local execution proves only its actual interpreter and OS.
The test-only driver instruments actual operations; no manifest is rewritten
to simulate a crash. Failed fixtures and a case report are retained at
RESEARCH_FAULT_EVIDENCE, or the system temporary fault-evidence directory.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from run_demo import RUNNER, git, make_project

DRIVER = Path(__file__).with_name("fault_driver.py")
PYTHON = [sys.executable, "-X", "utf8", "-B"]
CHILD_ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
CRASH_BOUNDARIES = (
    "prepare_published", "ledger_temp_before_replace", "claim_before_launching",
    "launching_before_popen", "popen_before_running", "active_execution",
    "result_before_terminal", "terminal_before_return",
)

# No worker spawns descendants. A release file and a hard deadline bound every
# evaluator left behind by abrupt supervisor death. The parent never kills a
# process obtained from a persisted PID; it kills only its own Popen handles.
EVALUATOR = '''import json,sys,time,uuid
from pathlib import Path
result, markers, release = map(Path, sys.argv[1:4])
token = result.parent.name + "-" + uuid.uuid4().hex
with (markers / (token + ".started")).open("x", encoding="utf-8") as stream:
    stream.write(token)
print(token, flush=True)
deadline = time.monotonic() + 15
while sys.argv[4] == "hold" and not release.exists():
    if time.monotonic() >= deadline:
        raise SystemExit("Test worker release timed out")
    time.sleep(0.01)
result.write_text(json.dumps({"metrics":{"mse":1},"launch_token":token}) + "\\n", encoding="utf-8")
(markers / (token + ".finished")).write_text(token, encoding="utf-8")
'''


class FaultBoundaryTests(unittest.TestCase):
    @contextmanager
    def case(self, label, *, hold=False):
        evidence = Path(os.environ.get(
            "RESEARCH_FAULT_EVIDENCE", str(Path(tempfile.gettempdir()) / "research-lab-fault-evidence")
        )).resolve()
        evidence.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix=label + "-", dir=evidence))
        record = {"case": label, "platform": sys.platform, "python": sys.version,
                  "runner_sha256": hashlib.sha256(RUNNER.read_bytes()).hexdigest(),
                  "instrumentation": str(DRIVER), "events": []}
        self.case_root = root
        self.record = record
        self.handles = []
        self.markers = root / "markers"
        self.markers.mkdir()
        self.worker_release = root / "worker-release"
        self.project = make_project(root / "project")
        (self.project / "evaluate.py").write_text(EVALUATOR, encoding="utf-8")
        git(self.project, "add", "evaluate.py")
        git(self.project, "commit", "-m", "Add bounded fault-test evaluator")
        protocol_path = self.project / ".research/protocol.json"
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        protocol["command"] = ["{python}", "-X", "utf8", "-B", "evaluate.py", "{result}",
                               str(self.markers), str(self.worker_release), "hold" if hold else "quick"]
        protocol["budget"].update(max_runs=4, timeout_seconds=20)
        protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
        succeeded = False
        try:
            yield
            succeeded = True
        except BaseException as exc:
            record["failure"] = repr(exc)
            print(f"Fault evidence retained: {root}", file=sys.stderr)
            raise
        finally:
            self.worker_release.write_text("release", encoding="utf-8")
            for process in self.handles:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)
            # Killed supervisors do not own live handles in this test process.
            # All test evaluators are finite and cooperative, with no children.
            deadline = time.monotonic() + 20
            while (len(list(self.markers.glob("*.finished"))) < len(list(self.markers.glob("*.started")))
                   and time.monotonic() < deadline):
                time.sleep(0.02)
            workers_finished = len(list(self.markers.glob("*.finished"))) == len(list(self.markers.glob("*.started")))
            record["cooperative_workers_finished"] = workers_finished
            record["behavior_passed"] = succeeded
            record["status"] = "passed" if succeeded and workers_finished else "failed"
            reports = evidence / "reports"
            reports.mkdir(exist_ok=True)
            if succeeded and workers_finished and label in {
                "crash-claim_before_launching-0", "crash-result_before_terminal-0"
            }:
                # Preserve actual interrupted records for the read-only A02
                # recovery walkthrough; never synthesize them by editing JSON.
                preserved = evidence / ("a02-" + root.name)
                record["preserved_fixture"] = str(preserved)
                (root / "case.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
                shutil.copytree(root, preserved)
            (root / "case.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            try:
                if succeeded and workers_finished:
                    self.assertTrue(root.resolve().is_relative_to(evidence))

                    def remove_readonly(operation, path, error):
                        target = Path(path)
                        self.assertTrue(target.resolve().is_relative_to(root.resolve()))
                        if not isinstance(error, PermissionError):
                            raise error
                        target.chmod(stat.S_IREAD | stat.S_IWRITE)
                        operation(path)

                    # Git objects are read-only on Windows. Handle only this
                    # observed permission failure inside the owned fixture.
                    if sys.version_info >= (3, 12):
                        shutil.rmtree(root, onexc=remove_readonly)
                    else:
                        shutil.rmtree(root, onerror=lambda op, path, info: remove_readonly(op, path, info[1]))
                    record["fixture_cleanup"] = "completed"
                elif not workers_finished and succeeded:
                    self.fail(f"Test worker did not finish; evidence retained at {root}")
            except BaseException as exc:
                record.update(status="failed", cleanup_error=repr(exc))
                raise
            finally:
                (reports / (root.name + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")

    def cli(self, action, *args, expected=0):
        result = subprocess.run(
            [*PYTHON, str(RUNNER), action, "--project", str(self.project), *args],
            capture_output=True, text=True, encoding="utf-8", env=CHILD_ENV, timeout=30,
        )
        self.record["events"].append({"action": action, "arguments": list(args),
                                      "returncode": result.returncode,
                                      "stdout": result.stdout, "stderr": result.stderr})
        self.assertEqual(result.returncode, expected, result.stderr or result.stdout)
        payload = json.loads(result.stderr if expected == 2 else result.stdout)
        if expected == 2:
            self.assertIsInstance(payload["error"], str)
        return payload

    def prepare(self, label="fault-test"):
        return self.cli("prepare", "--label", label, "--replicate")["id"]

    def run_path(self, run_id):
        return self.project / ".research/runs" / run_id

    def start_driver(self, mode, boundary, action, *args, gate=None):
        token = uuid.uuid4().hex
        ready = self.case_root / (token + ".ready")
        release = gate or self.case_root / (token + ".release")
        process = subprocess.Popen(
            [*PYTHON, str(DRIVER), "--runner", str(RUNNER), "--mode", mode,
             "--boundary", boundary, "--ready", str(ready), "--release", str(release),
             "--markers", str(self.markers), action, "--project", str(self.project), *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=CHILD_ENV,
        )
        self.handles.append(process)
        return process, ready

    def wait_ready(self, process, ready):
        deadline = time.monotonic() + 20
        attempts = {"path": str(ready), "read_attempts": 0, "last_transient_error": None}
        self.record["events"].append({"ready_wait": attempts})
        while True:
            if process.poll() is not None:
                output = process.communicate(timeout=5)
                self.fail(f"Instrumentation exited before boundary: {process.returncode}, {output}")
            if time.monotonic() >= deadline:
                self.fail("Instrumentation did not reach requested boundary within 20 seconds")
            attempts["read_attempts"] += 1
            try:
                payload = json.loads(ready.read_text(encoding="utf-8"))
            except (PermissionError, FileNotFoundError) as error:
                attempts["last_transient_error"] = repr(error)
                time.sleep(0.01)
            else:
                self.record["events"].append({"ready": payload})
                return

    def finish_driver(self, process):
        stdout, stderr = process.communicate(timeout=30)
        self.record["events"].append({"driver_returncode": process.returncode,
                                      "stdout": stdout, "stderr": stderr})
        return stdout, stderr

    def evidence_hashes(self, run_id):
        directory = self.run_path(run_id)
        return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                for name in ("manifest.json", "source.zip", "result.json", "run.log")
                if (directory / name).exists()}

    def assert_no_automatic_recovery(self, run_id, expected_status, claimed, existing_claims=0):
        before = self.evidence_hashes(run_id)
        detail = self.cli("inspect", "--id", run_id)
        self.assertEqual(detail["status"], expected_status)
        self.assertEqual(detail["launch_claimed"], claimed)
        self.assertEqual(detail["unresolved"], claimed and expected_status != "completed")
        overview = self.cli("inspect")
        self.assertEqual(overview["launch_claims_used"], existing_claims + int(claimed))
        if claimed:
            self.cli("run", "--id", run_id, expected=2)
            self.assertEqual(self.evidence_hashes(run_id), before, "Rejected relaunch changed evidence")
            self.assertEqual(self.cli("inspect")["launch_claims_used"], existing_claims + 1)
        if expected_status != "completed":
            self.assertNotEqual(detail["evidence"]["status"], "valid")
            peer = self.prepare("comparison-peer")
            self.cli("compare", "--baseline", run_id, "--candidate", peer, expected=2)

    def test_real_subprocess_crashes_at_eight_boundaries_twice(self):
        states = {
            "prepare_published": ("prepared", False, 0),
            "ledger_temp_before_replace": ("prepared", False, 0),
            "claim_before_launching": ("prepared", True, 0),
            "launching_before_popen": ("launching", True, 0),
            "popen_before_running": ("launching", True, 1),
            "active_execution": ("running", True, 1),
            "result_before_terminal": ("running", True, 1),
            "terminal_before_return": ("completed", True, 1),
        }
        for repetition in range(2):
            for boundary in CRASH_BOUNDARIES:
                with self.subTest(boundary=boundary, repetition=repetition):
                    hold = boundary in {"popen_before_running", "active_execution"}
                    with self.case(f"crash-{boundary}-{repetition}", hold=hold):
                        # Keep an actual completed claim in the ledger so a
                        # reset or lost historical claim cannot pass as empty.
                        self.worker_release.write_text("release seed", encoding="utf-8")
                        seed = self.prepare("historical-evidence")
                        self.cli("run", "--id", seed)
                        self.worker_release.unlink()
                        seed_evidence = self.evidence_hashes(seed)
                        if boundary == "prepare_published":
                            process, ready = self.start_driver("crash", boundary, "prepare", "--label", "interrupted-publication", "--replicate")
                            run_id = None
                        else:
                            run_id = self.prepare()
                            process, ready = self.start_driver("crash", boundary, "run", "--id", run_id)
                        self.wait_ready(process, ready)
                        self.assertIsNone(process.poll(), "Supervisor must be alive when interrupted")
                        process.kill()  # Only this parent-owned Popen handle is targeted.
                        self.finish_driver(process)
                        self.assertNotEqual(process.returncode, 0)
                        self.worker_release.write_text("release", encoding="utf-8")
                        if run_id is None:
                            runs = [item for item in self.cli("inspect")["runs"] if item["id"] != seed]
                            self.assertEqual(len(runs), 1)
                            run_id = runs[0]["id"]
                        expected_status, claimed, launches = states[boundary]
                        deadline = time.monotonic() + 10
                        while (len(list(self.markers.glob(run_id + "-*.finished"))) < launches
                               and time.monotonic() < deadline):
                            time.sleep(0.01)
                        self.assertEqual(len(list(self.markers.glob(run_id + "-*.started"))), launches)
                        self.assertEqual(len(list(self.markers.glob(run_id + "-*.finished"))), launches)
                        self.assert_no_automatic_recovery(run_id, expected_status, claimed, existing_claims=1)
                        if not claimed:
                            self.cli("run", "--id", run_id)
                            self.cli("run", "--id", run_id, expected=2)
                            self.assertEqual(self.cli("inspect")["launch_claims_used"], 2)
                            self.assertEqual(len(list(self.markers.glob(run_id + "-*.started"))), 1)
                        self.assertEqual(self.evidence_hashes(seed), seed_evidence)
                        ledger = json.loads((self.project / ".research/launches.json").read_text(encoding="utf-8"))
                        self.assertEqual(set(ledger["claims"]), {seed, run_id})
                        if boundary == "ledger_temp_before_replace":
                            self.assertTrue(list((self.project / ".research").glob(".launches.json.*.tmp")),
                                            "Real flushed ledger temporary was not preserved by abrupt death")
                        if boundary in {"result_before_terminal", "terminal_before_return"}:
                            self.assertEqual(json.loads((self.run_path(run_id) / "result.json").read_text(encoding="utf-8"))["metrics"], {"mse": 1})

    def test_injected_io_errors_preserve_claims_and_fail_closed(self):
        for boundary in ("write", "flush", "replace", "log_open", "finalization"):
            with self.subTest(boundary=boundary):
                with self.case("io-" + boundary):
                    seed = self.prepare("historical-evidence")
                    self.cli("run", "--id", seed)
                    seed_evidence = self.evidence_hashes(seed)
                    run_id = self.prepare()
                    process, ready = self.start_driver("fault", boundary, "run", "--id", run_id)
                    stdout, stderr = self.finish_driver(process)
                    self.assertTrue(ready.exists(), "Requested injected failure did not execute")
                    self.assertNotEqual(process.returncode, 0, stdout or stderr)
                    self.assertIn("Injected test-only " + boundary, stdout + stderr)
                    claimed = boundary in {"log_open", "finalization"}
                    status = "launch_failed" if boundary == "log_open" else "running" if boundary == "finalization" else "prepared"
                    detail = self.cli("inspect", "--id", run_id)
                    self.assertEqual(detail["status"], status)
                    self.assertEqual(detail["launch_claimed"], claimed)
                    self.assertEqual(self.cli("inspect")["launch_claims_used"], 1 + int(claimed))
                    self.assertEqual(len(list(self.markers.glob(run_id + "-*.started"))), int(boundary == "finalization"))
                    self.assertFalse(list((self.project / ".research").glob(".launches.json.*.tmp")))
                    before = self.evidence_hashes(run_id)
                    if claimed:
                        self.cli("run", "--id", run_id, expected=2)
                        self.assertEqual(self.evidence_hashes(run_id), before)
                        peer = self.prepare("failure-peer")
                        self.cli("compare", "--baseline", run_id, "--candidate", peer, expected=2)
                    else:
                        self.cli("run", "--id", run_id)
                        self.assertEqual(self.cli("inspect")["launch_claims_used"], 2)
                    self.assertEqual(self.evidence_hashes(seed), seed_evidence)
                    ledger = json.loads((self.project / ".research/launches.json").read_text(encoding="utf-8"))
                    self.assertEqual(set(ledger["claims"]), {seed, run_id})
                    if boundary == "finalization":
                        self.assertTrue(detail["unresolved"])
                        self.assertEqual(detail["evidence"]["status"], "pending")
                        self.assertTrue((self.run_path(run_id) / "result.json").exists())

    def test_five_synchronized_contention_waves(self):
        for wave in range(5):
            with self.subTest(wave=wave):
                with self.case(f"contention-{wave}", hold=True):
                    ids = [self.prepare(f"contender-{index}") for index in range(7)]
                    gate = self.case_root / "contention-release"
                    observer_gate = self.case_root / "observer-release"
                    # Seven distinct IDs exceed the four-launch budget; the first
                    # ID also races against two duplicate requests in every wave.
                    actions = [("run", ("--id", run_id)) for run_id in [*ids, ids[0], ids[0]]]
                    actions.extend([
                        ("prepare", ("--label", "concurrent-replicate", "--replicate")),
                        ("inspect", ()),
                        ("compare", ("--baseline", ids[0], "--candidate", ids[1])),
                    ])
                    pending = [(action, arguments, *self.start_driver(
                        "gate", "", action, *arguments, gate=gate if action == "run" else observer_gate
                    ))
                               for action, arguments in actions]
                    for _, _, process, ready in pending:
                        self.wait_ready(process, ready)
                    gate.write_text("go", encoding="utf-8")
                    deadline = time.monotonic() + 10
                    while len(list(self.markers.glob("*.started"))) < 4 and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertEqual(len(list(self.markers.glob("*.started"))), 4)
                    self.assertFalse(list(self.markers.glob("*.finished")))
                    # Observers execute while all four real evaluators are held
                    # active. Their own gate prevents scheduling from turning
                    # the concurrent-read exercise into post-run inspection.
                    observer_gate.write_text("go", encoding="utf-8")
                    successful_ids = []
                    extra_prepared = None
                    for action, arguments, process, _ in sorted(pending, key=lambda item: item[0] == "run"):
                        if action == "run":
                            self.worker_release.write_text("release", encoding="utf-8")
                        stdout, stderr = self.finish_driver(process)
                        self.assertIn(process.returncode, (0, 2), (action, stdout, stderr))
                        payload = json.loads(stdout if process.returncode == 0 else stderr)
                        if action == "run" and process.returncode == 0:
                            self.assertEqual(payload["status"], "completed")
                            self.assertEqual(payload["evidence"]["status"], "valid")
                            successful_ids.append(arguments[1])
                        elif action == "prepare":
                            self.assertEqual(process.returncode, 0, stderr)
                            extra_prepared = payload["id"]
                            self.assertFalse(payload["deduplicated"])
                        elif action == "inspect":
                            self.assertEqual(process.returncode, 0, stderr)
                            self.assertEqual(payload["launch_claims_used"], 4)
                            self.assertEqual(sum(item["launch_claimed"] for item in payload["runs"]), payload["launch_claims_used"])
                            self.assertTrue(all(item["unresolved"] for item in payload["runs"] if item["launch_claimed"]))
                        elif action == "compare":
                            self.assertEqual(process.returncode, 2, "Active runs were treated as comparable")
                            self.assertIn("incomplete or has invalid evidence", payload["error"])
                        elif process.returncode == 2:
                            # The frozen oracle requires fail-closed excess
                            # requests, not one specific rejection message.
                            # Exact successes, claims, starts, inspection, and
                            # final comparisons remain mandatory below.
                            self.assertIsInstance(payload["error"], str)
                            self.assertTrue(payload["error"].strip())
                    self.assertEqual(len(successful_ids), 4)
                    self.assertEqual(len(set(successful_ids)), 4, "An ID launched more than once")
                    starts = list(self.markers.glob("*.started"))
                    self.assertEqual(len(starts), 4, "Actual evaluator start count differs from successes")
                    self.assertEqual(len(list(self.markers.glob("*.finished"))), 4)
                    self.assertEqual({path.name[:29] for path in starts}, set(successful_ids))
                    overview = self.cli("inspect")
                    self.assertEqual(overview["launch_claims_used"], 4)
                    self.assertEqual({item["id"] for item in overview["runs"]}, {*ids, extra_prepared})
                    self.assertEqual({item["id"] for item in overview["runs"] if item["launch_claimed"]}, set(successful_ids))
                    ledger = json.loads((self.project / ".research/launches.json").read_text(encoding="utf-8"))
                    self.assertEqual(set(ledger["claims"]), set(successful_ids))
                    original = {run_id: self.evidence_hashes(run_id) for run_id in ids}
                    for index, baseline in enumerate(successful_ids):
                        for candidate in successful_ids[index + 1:]:
                            comparison = self.cli("compare", "--baseline", baseline, "--candidate", candidate)
                            self.assertEqual(comparison["outcome"], "no_improvement")
                            self.assertEqual(comparison["absolute_improvement"], 0)
                    for run_id in [*ids, extra_prepared]:
                        self.cli("run", "--id", run_id, expected=2)
                    self.assertEqual({run_id: self.evidence_hashes(run_id) for run_id in ids}, original,
                                     "Inspection, comparison, or rejected retry overwrote evidence")
                    self.assertEqual(len(list(self.markers.glob("*.started"))), 4)
                    self.assertEqual(self.cli("inspect")["launch_claims_used"], 4)


if __name__ == "__main__":
    unittest.main()
