"""Synthetic hook contracts; actual native delivery is a separate acceptance check."""
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

RUNNER = Path(__file__).resolve().parents[1] / "plugins/evrik/skills/research/scripts/research.py"
spec = importlib.util.spec_from_file_location("stream_runner", RUNNER)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class StreamEvidenceTests(unittest.TestCase):
    transport = "stream-v1"

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="evrik stream ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.project = self.root / "nested café's project"
        self.project.mkdir()
        self.session = "22222222-2222-4222-8222-222222222222"
        self.directory = self.project / ".research/evidence" / self.session
        self.patch = mock.patch.dict(os.environ, CODEX_SESSION_ID=self.session, CODEX_THREAD_ID=self.session)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        (self.project / "report.md").write_bytes(b"Initial report\r\n")
        self.calls = 0

    def action(self, operation, **changes):
        values = dict(operation=operation, project=str(self.project), artifact=["report.md"], public_web=False,
                      experiment=False, record=None, transport=self.transport, receipt=None, page=None,
                      incomplete=False, reason=None, hook_root=str(self.root))
        values.update(changes)
        return r.evidence_action(argparse.Namespace(**values))

    def hook(self, phase, command, response=None, name="Bash"):
        cwd = self.root
        event = {"hook_event_name": phase, "tool_name": name, "tool_use_id": str(self.calls),
                 "session_id": self.session, "cwd": str(cwd),
                 "tool_input": {"command": command} if name == "Bash" else command}
        if phase == "PostToolUse":
            event["tool_response"] = response
        with io.TextIOWrapper(io.BytesIO(json.dumps(event).encode()), encoding="utf-8") as stdin, \
                mock.patch.object(r.sys, "stdin", stdin), mock.patch.object(r.os, "getcwd", return_value=str(cwd)):
            return r.evidence_hook()

    def page(self, command):
        self.calls += 1
        self.assertEqual(self.hook("PreToolUse", command), {})
        frame = self.action("next")
        output = r.evidence_output(frame).decode("utf-8")
        self.assertLessEqual(len(output.encode()), r.READER_OUTPUT_LIMIT)
        self.assertEqual(self.hook("PostToolUse", command, output), {})
        return frame

    def finish(self, command):
        frames = []
        while not self.action("check")["ready_to_close"]:
            self.assertLess(len(frames), 200)
            frames.append(self.page(command))
        return frames

    def test_large_corpus_companions_exact_bytes_and_scope_reuse(self):
        raw = ('Unicode 漢字 😀 and "quotes"\r\n' * 10000).encode("utf-8")
        (self.project / "report.md").write_bytes(raw)
        activation = self.action("activate")
        command = activation["resume_command"]
        frames = self.finish(command)
        reconstructed = b"".join(f["page"]["text"].encode() for f in frames if f["page"]["part"]["unit"] == "artifact:report.md")
        self.assertEqual(reconstructed, raw)
        self.assertGreater(len(raw), r.EVIDENCE_LIMIT)
        before = self.action("check")
        self.assertIsNone(before["size"]["aggregate_byte_limit"])
        old_receipt = before["latest_readback"]
        old_bytes = (self.directory / f"readback-{old_receipt}.json").read_bytes()
        (self.project / "addition.md").write_bytes(b"Additional required evidence\n")
        self.action("revise", artifact=["report.md", "addition.md"], reason="New required finding")
        self.assertFalse(self.action("check")["ready_to_close"])
        self.page(command)
        status = self.action("check")
        self.assertGreater(status["reader_progress"]["reused_pages"], 40)
        self.assertEqual(status["scope_version"], 2)
        self.finish(command)
        self.assertEqual((self.directory / f"readback-{old_receipt}.json").read_bytes(), old_bytes)
        # CRLF -> LF is a real byte change; the unit must be read again.
        (self.project / "report.md").write_bytes(raw.replace(b"\r\n", b"\n"))
        self.assertFalse(self.action("check")["fresh"])
        self.page(command)
        self.assertLess(self.action("check")["reader_progress"]["reused_pages"], 5)

    def test_companions_larger_than_old_bundle_limit_are_paged(self):
        self.action("activate")
        dependencies = {"ready": True, "experiment_attached": True, "obligations": "metadata " * 33000}
        with mock.patch.object(r, "evidence_dependencies", return_value=dependencies):
            frames = self.finish(self.action("activate")["resume_command"])
            observed = b"".join(f["page"]["text"].encode() for f in frames if f["page"]["part"]["unit"] == "dependencies")
            restored = r.evidence_companion_restore({"dependencies": observed}) if self.transport == "stream-v2" else json.loads(observed)
            self.assertEqual(restored, dependencies)
            self.assertGreater(self.action("check")["size"]["companion_bytes"], r.EVIDENCE_LIMIT)

    def test_rejections_are_diagnostic_and_never_grant_native_credit(self):
        activation = self.action("activate")
        command = activation["resume_command"]
        self.calls += 1
        self.hook("PreToolUse", command)
        frame = self.action("next")
        output = r.evidence_output(frame).decode()
        blocked = self.hook("PostToolUse", command, output[:40])
        self.assertEqual(blocked["decision"], "block")
        status = self.action("check")
        self.assertEqual(status["diagnostics"]["first_failure"]["stage"], "reader_response_json")
        self.assertEqual(status["reader_progress"]["matched_pages"], 0)
        self.finish(command)
        self.assertIsNotNone(self.action("check")["diagnostics"]["first_failure"])
        summary = self.directory / f"diagnostics-{activation['generation']}.json"
        telemetry = r.read_json(summary)
        telemetry["first_failure"] = None  # A stale concurrent summary cannot erase the first failure.
        r.atomic_json(summary, telemetry)
        self.assertEqual(self.action("check")["diagnostics"]["first_failure"]["stage"], "reader_response_json")
        bundle = r.evidence_read(self.directory / f"readback-{frame['receipt_id']}.json")
        blob = self.directory / "blobs" / bundle["parts"][1]["sha256"]
        blob.write_bytes(b"changed")
        self.assertFalse(self.action("check")["ready_to_close"])

    def test_missing_page_prevents_close_and_unchanged_next_resumes_same_receipt(self):
        activation = self.action("activate")
        command = activation["resume_command"]
        first = self.page(command)
        interrupted = self.action("next")  # emitted, no native PostToolUse
        resumed = self.page(command)
        self.assertEqual(interrupted, resumed)
        self.assertEqual(first["receipt_id"], resumed["receipt_id"])
        with self.assertRaises(r.ResearchError):
            self.action("close")
        self.finish(command)
        self.assertTrue(self.action("close")["ready_to_close"])

    def test_source_capture_interoperates_with_stream_and_a_large_working_record(self):
        activation = self.action("activate", public_web=True, record="report.md")
        request = {"open": [{"ref_id": "https://example.org/source"}]}
        self.calls += 1
        self.assertEqual(self.hook("PreToolUse", request, name="webrun"), {})
        self.assertEqual(self.hook("PostToolUse", request, "Ordinary public evidence.", name="webrun"), {})
        self.calls += 1
        command = activation["sources_command"]
        self.assertEqual(self.hook("PreToolUse", command), {})
        frame = self.action("sources")
        self.assertIsNone(frame["next_command"])
        self.assertEqual(self.hook("PostToolUse", command, r.evidence_output(frame).decode()), {})
        bundle = json.loads(frame["page"]["text"])
        (self.project / "report.md").write_bytes(b"Source notes\n" * 25000 + bundle["record_reference"].encode() + b"\n")
        self.assertTrue(self.action("check")["sources"]["ready"])


class SnapshotEvidenceTests(StreamEvidenceTests):
    transport = "stream-v2"

    def test_complete_status_has_no_actionable_reader_and_closed_staleness_is_preserved(self):
        activation = self.action("activate")
        self.finish(activation["resume_command"])
        closed = self.action("close")
        self.assertTrue(closed["ready_to_close"])
        self.assertIsNone(closed["reader_progress"]["next_command"])
        for key in ("next_readback_command", "resume_command", "readback_command", "sources_command"):
            self.assertIsNone(closed[key])
        original = (self.directory / "session.json").read_bytes()
        (self.project / "report.md").write_text("Later correction", encoding="utf-8")
        self.assertFalse(self.action("check")["current_evidence"]["fresh"])
        with self.assertRaises(r.ResearchError):
            self.action("close")
        self.assertEqual((self.directory / "session.json").read_bytes(), original)

    def test_safe_command_spelling_binds_native_proof_but_compound_commands_do_not(self):
        activation = self.action("activate")
        command = activation["resume_command"]
        equivalent = command.replace("\\", "/") if os.name == "nt" else command
        first = self.page(equivalent)
        self.assertEqual(first["current_evidence"], "not_checked; immutable snapshot page only")
        self.assertEqual(self.action("check")["reader_progress"]["matched_pages"], 1)
        if os.name == "nt":
            arguments = r.evidence_command_argv(command)
            quoted = "& " + " ".join('"' + part + '"' for part in arguments)
            self.page(quoted)
        for invalid in (command + "; echo changed", command + "\n", command + " | cat",
                        command.replace("research.py", "other.py"), command.replace("--project", "--wrong"),
                        command + " $(echo injected)", command + " --page 0"):
            self.assertIsNone(r.evidence_reader_request(activation, {"command": invalid}))
        self.finish(command)
        self.assertTrue(self.action("close")["ready_to_close"])

    def test_pagination_bounds_inventory_and_frame_reads_and_close_rechecks_freshness(self):
        (self.project / "report.md").write_bytes(b"x" * (r.READER_TEXT_LIMIT * 20))
        activation = self.action("activate")
        command = activation["resume_command"]
        with mock.patch.object(r, "evidence_inventory", wraps=r.evidence_inventory) as inventories, \
                mock.patch.object(r, "evidence_session", wraps=r.evidence_session) as sessions, \
                mock.patch.object(r, "evidence_reader_bundle", wraps=r.evidence_reader_bundle) as bundles, \
                mock.patch.object(r.EvidenceFrames, "__getitem__", autospec=True,
                                  side_effect=r.EvidenceFrames.__getitem__) as reads:
            frames = []
            while True:
                frames.append(self.page(command))
                if frames[-1]["next_command"] is None:
                    break
            self.assertEqual(inventories.call_count, 1)
            self.assertEqual(sessions.call_count, 1)
            self.assertEqual(bundles.call_count, 0)
            self.assertLessEqual(reads.call_count, 3 * len(frames))
        self.assertFalse((self.directory / f"matched-{frames[-1]['receipt_id']}.json").exists())
        self.assertTrue(self.action("check")["ready_to_close"])
        self.action("close")
        activation = self.action("activate")
        command = activation["resume_command"]
        first = self.page(command)
        (self.project / "report.md").write_bytes(b"y" * (r.READER_TEXT_LIMIT * 20))
        while True:
            self.calls += 1
            self.assertEqual(self.hook("PreToolUse", command), {})
            frame = self.action("next")
            response = self.hook("PostToolUse", command, r.evidence_output(frame).decode())
            self.assertEqual(response, {})
            if frame["next_command"] is None:
                break
            self.assertEqual(frame["receipt_id"], first["receipt_id"])
        status = self.action("check")
        self.assertFalse(status["fresh"])
        self.assertFalse(status["ready_to_close"])
        self.assertTrue(status["native_response_matched"])
        with self.assertRaises(r.ResearchError):
            self.action("close")
        closed = self.action("close", incomplete=True, reason="Current source changed after snapshot delivery")
        self.assertTrue(closed["incomplete"])
        for fields in (closed, closed.get("reader_progress", {}), closed.get("sources", {})):
            for key, value in fields.items():
                if key.endswith(("_command", "_functions_exec_source")):
                    self.assertIsNone(value)

    def test_companion_factoring_preserves_edges_failures_and_rejects_invalid_references(self):
        shared = {"source": "preserved source\n" * 300, "failed_attempt": {"exit": 1, "status": "unresolved"}}
        dependencies = {"ready": False, "reconciliation": shared, "runs": [
            {"id": "first", "reconciliation": shared, "status": "failed", "empty": []},
            {"id": "second", "reconciliation": shared, "status": "prepared", "empty": None}]}
        units = r.evidence_companion_units(dependencies)
        self.assertEqual(r.canonical(r.evidence_companion_restore(units)), r.canonical(dependencies))
        self.assertLess(sum(map(len, units.values())), len(r.canonical(dependencies)) // 2)
        dangling = dict(units)
        del dangling[next(name for name in units if name != "dependencies")]
        with self.assertRaises(r.ResearchError):
            r.evidence_companion_restore(dangling)
        invalid = dict(units)
        root = json.loads(invalid["dependencies"])
        root["references"].append(root["references"][0])
        invalid["dependencies"] = r.canonical(root)
        with self.assertRaises(r.ResearchError):
            r.evidence_companion_restore(invalid)

    def test_progress_markers_are_hints_not_native_credit(self):
        activation = self.action("activate")
        frame = self.page(activation["resume_command"])
        marker = self.directory / f"page-matched-readback-{frame['receipt_id']}-1.json"
        r.evidence_write(marker, {"status": "invented"})
        self.assertFalse(self.action("check")["ready_to_close"])
        with self.assertRaises(r.ResearchError):
            self.action("close")

    def test_index_resume_survives_cursor_loss_and_out_of_order_delivery(self):
        (self.project / "report.md").write_bytes(b"x" * (r.READER_TEXT_LIMIT * 3))
        activation = self.action("activate")
        command = activation["resume_command"]
        first = self.page(command)
        receipt = first["receipt_id"]
        cursor = self.directory / f"index-{receipt}" / "cursor.json"
        pending = self.action("next")
        self.assertEqual(self.action("next"), pending)  # Emission alone cannot advance.
        self.assertEqual(self.hook("PostToolUse", command, r.evidence_output(first).decode()), {})
        self.assertEqual(self.action("next"), pending)  # Duplicate delivery cannot advance twice.
        later = first["page"]["count"] - 1
        literal = activation["readback_command"] + f" --receipt {receipt} --page {later}"
        self.calls += 1
        self.assertEqual(self.hook("PreToolUse", literal), {})
        frame = self.action("readback", receipt=receipt, page=later)
        self.assertEqual(self.hook("PostToolUse", literal, r.evidence_output(frame).decode()), {})
        self.assertEqual(self.action("next"), pending)
        # A durable page marker followed by a lost cursor update must resume correctly.
        r.evidence_write(cursor, {"next": 0})
        self.assertEqual(self.action("next"), pending)
        cursor.unlink()
        (self.directory / "reader-state.json").unlink()
        (self.project / "report.md").write_bytes(b"Current artifact changed after capture")
        self.assertEqual(self.action("next"), pending)
        for expected_index in range(pending["page"]["index"], later):
            self.assertEqual(self.page(command)["page"]["index"], expected_index)
        status = self.action("check")
        self.assertTrue(status["native_response_matched"])
        self.assertFalse(status["fresh"])
        with self.assertRaises(r.ResearchError):
            self.action("close")

    def test_valid_alternate_cache_blob_cannot_grant_aggregate_native_credit(self):
        activation = self.action("activate")
        command = activation["resume_command"]
        original = self.action("next")
        receipt = original["receipt_id"]
        descriptor = self.directory / f"index-{receipt}" / "0.json"
        value = r.evidence_read(descriptor)
        raw = b"!" * value["page"]["part"]["bytes"]
        value["page"]["part"]["sha256"] = r.evidence_blob(self.directory, raw)
        r.evidence_write(descriptor, value)  # Valid envelope and blob, wrong authoritative content.
        returned = self.page(command)
        self.assertNotEqual(returned, original)
        proof = self.directory / f"page-matched-readback-{receipt}-0.json"
        saved = proof.read_bytes()
        self.assertEqual(r.evidence_read(proof)["status"], "reader_page_matched")
        status = self.action("check")
        self.assertFalse(status["ready_to_close"])
        self.assertIn("Invalid native reader page binding", status["issue"])
        with self.assertRaises(r.ResearchError):
            self.action("close")
        self.assertEqual(proof.read_bytes(), saved)
        self.assertFalse((self.directory / f"matched-{receipt}.json").exists())

    def test_reader_cache_invalidates_on_scope_and_session_changes(self):
        activation = self.action("activate")
        first = self.page(activation["resume_command"])
        cache = self.directory / "reader-state.json"
        before = cache.read_bytes()
        (self.project / "addition.md").write_bytes(b"Required new scope")
        self.action("revise", artifact=["report.md", "addition.md"], reason="Add evidence")
        cache.write_bytes(before)  # Interrupted cache update after authoritative scope commit.
        with self.assertRaises(r.ResearchError):
            self.action("readback", receipt=first["receipt_id"], page=0)
        self.assertEqual(r.evidence_read(cache)["activation"]["scope_version"], 2)
        self.assertEqual(r.evidence_read(self.directory / "session.json")["activations"][-1]["artifacts"],
                         ["addition.md", "report.md"])
        stale = cache.read_bytes()
        self.action("close", incomplete=True, reason="Bounded cache invalidation test")
        cache.write_bytes(stale)
        self.assertEqual(self.action("next")["status"], "closed")
        self.assertEqual(r.evidence_read(cache)["activation"]["state"], "closed")

    def test_text_metadata_and_unsupported_public_response_remain_recoverable(self):
        activation = self.action("activate", public_web=True, record="report.md")
        request = {"open": [{"ref_id": "https://example.org/source"}]}
        response = [{"type": "text", "text": "Public text", "annotations": {"audience": ["user"]}}]
        self.calls += 1
        self.assertEqual(self.hook("PreToolUse", request, name="webrun"), {})
        self.assertEqual(self.hook("PostToolUse", request, response, name="webrun"), {})
        self.calls += 1
        self.hook("PreToolUse", activation["sources_command"])
        frame = self.action("sources")
        self.assertEqual(self.hook("PostToolUse", activation["sources_command"], r.evidence_output(frame).decode()), {})
        bundle = json.loads(frame["page"]["text"])
        self.assertEqual(bundle["capture"]["returned_text"]["content"], response)
        (self.project / "report.md").write_text(bundle["record_reference"], encoding="utf-8")
        ordinary = [{"type": "new_public_format", "body": "Preserve this ordinary returned output"}]
        self.calls += 1
        self.assertEqual(self.hook("PreToolUse", request, name="webrun"), {})
        blocked = self.hook("PostToolUse", request, ordinary, name="webrun")
        self.assertEqual(blocked["decision"], "block")
        status = self.action("check")
        recovery = status["web"]["recoverable_failures"][0]
        self.assertEqual((self.project / recovery["path"]).read_bytes(), r.canonical(ordinary))
        self.assertFalse(recovery["native_capture"])
        self.assertFalse(status["web"]["complete"])
        self.assertFalse(status["ready_to_close"])
        self.assertIsInstance(status["diagnostics"]["first_failure"]["response_bytes"], int)
        self.assertIsNone(r.evidence_text([{"type": "text", "text": "secret", "_meta": {"authorization": "secret"}}], enriched=True))


if __name__ == "__main__":
    unittest.main()
