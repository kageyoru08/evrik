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
                      experiment=False, record=None, transport="stream-v1", receipt=None, page=None,
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
            self.assertEqual(json.loads(observed), dependencies)
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


if __name__ == "__main__":
    unittest.main()
