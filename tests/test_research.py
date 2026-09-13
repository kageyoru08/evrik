"""Black-box checks of the local runner and the shipped example."""
from __future__ import annotations

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
                         RESEARCH_UNRELATED="preserved")
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
