"""Synthetic hook contracts; actual native delivery is a separate acceptance check."""
import argparse
import genericpath
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

    def hook(self, phase, command, response=None, name="Bash", **extra):
        cwd = self.root
        event = {"hook_event_name": phase, "tool_name": name, "tool_use_id": str(self.calls),
                 "session_id": self.session, "cwd": str(cwd),
                 "tool_input": {"command": command} if name == "Bash" else command, **extra}
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

    def test_management_calls_do_not_hide_the_first_reader_failure(self):
        self.root = self.project  # Root native sessions route management calls here too.
        activation = self.action("activate")
        command = activation["resume_command"]
        for operation in ("activate", "check", "close", "revise"):
            management = command.replace("'next'", "'" + operation + "'").replace(" evidence next ", " evidence " + operation + " ")
            self.assertNotEqual(management, command)
            self.calls += 1
            self.assertEqual(self.hook("PostToolUse", management, "ordinary status"), {})
        for ordinary in ("Get-Content evidence.md", "Get-Content 'evidence next notes.md'",
                         "Write-Output 'evidence next'", "Write-Output python research.py evidence next",
                         "python -c 'pass' research.py evidence next", "python -m module research.py evidence next"):
            self.calls += 1
            self.assertEqual(self.hook("PreToolUse", ordinary), {})
        self.assertEqual(self.hook("PreToolUse", {"cmd": "Get-Content evidence.md"}, name="unsupported_tool"), {})
        before = self.action("check")["diagnostics"]
        self.assertIsNone(before.get("first_failure"))
        self.calls += 1
        self.hook("PreToolUse", command)
        frame = self.action("next")
        blocked = self.hook("PostToolUse", command, r.evidence_output(frame).decode()[:40])
        self.assertEqual(blocked["decision"], "block")
        self.assertEqual(self.action("check")["diagnostics"]["first_failure"]["stage"], "reader_response_json")
        for invalid in (command + " --wrong", command.replace("research.py", "other.py"), command + "; echo changed"):
            self.calls += 1
            self.hook("PreToolUse", invalid)
        self.calls += 1
        self.hook("PreToolUse", {"cmd": command}, name="unsupported_tool")
        final = self.action("check")
        self.assertEqual(final["diagnostics"]["stages"]["request_unrecognized"], 3)
        self.assertEqual(final["diagnostics"]["stages"]["unsupported_reader_tool"], 1)
        self.assertEqual(final["diagnostics"]["first_failure"]["stage"], "reader_response_json")
        self.assertEqual(final["reader_progress"]["matched_pages"], 0)

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

    def test_interrupted_scope_publication_preserves_history_and_allows_corrected_revision(self):
        self.action("activate")
        initial = (self.directory / "session.json").read_bytes()
        (self.project / "addition.md").write_bytes(b"Required addition\n")
        original = r.os.replace

        def fail_session(source, target):
            if Path(target).name == "session.json":
                raise OSError("Injected session publication failure")
            return original(source, target)

        with mock.patch.object(r.os, "replace", side_effect=fail_session), self.assertRaises(OSError):
            self.action("revise", artifact=["report.md", "addition.md"], reason="Add required evidence")
        self.assertEqual((self.directory / "session.json").read_bytes(), initial)
        orphan, = self.directory.glob("scope-*-2.json")
        saved = orphan.read_bytes()
        revised = self.action("revise", artifact=["report.md", "addition.md"], reason="Corrected scope after recovery")
        self.assertEqual(revised["scope_version"], 3)
        self.assertEqual(orphan.read_bytes(), saved)
        published, = self.directory.glob("scope-*-3.json")
        self.assertEqual(r.evidence_read(published)["previous"], ["report.md"])
        self.assertFalse(self.action("check")["ready_to_close"])
        self.assertIsNone(self.action("check")["latest_readback"])

    def test_unreadable_web_binding_blocks_before_capture_and_ignores_children(self):
        self.action("activate", public_web=True, record="report.md")
        request = {"search_query": [{"q": "synthetic public reference"}]}
        original_read, original_stat = r.evidence_read, Path.stat
        for filename in ("web-route.json", "session.json"):
            for operation in ("read", "stat"):
                with self.subTest(filename=filename, operation=operation):
                    def fail_read(path):
                        if path.name == filename:
                            raise PermissionError("Injected metadata read failure")
                        return original_read(path)

                    def fail_stat(path, *args, **kwargs):
                        if path.name == filename:
                            raise PermissionError("Injected metadata stat failure")
                        return original_stat(path, *args, **kwargs)

                    patch = (mock.patch.object(r, "evidence_read", side_effect=fail_read) if operation == "read"
                             else mock.patch.object(Path, "stat", fail_stat))
                    with patch:
                        before = self.hook("PreToolUse", request, name="webrun")
                        self.assertEqual(before.get("decision"), "block")
                        self.assertIn("no capture attempt", before["reason"])
                        self.assertEqual(self.hook("PostToolUse", request, "Synthetic result", name="webrun").get("decision"), "block")
                        self.assertEqual(self.hook("PreToolUse", request, name="webrun", agent_id="worker"), {})
        self.assertEqual(list(self.directory.glob("web-*.json")), [])
        self.action("close", incomplete=True, reason="End synthetic fixture")
        self.assertEqual(self.hook("PreToolUse", request, name="webrun"), {})

    def test_web_post_binding_failure_retains_pending_attempt_and_prevents_close(self):
        self.action("activate", public_web=True, record="report.md")
        request = {"search_query": [{"q": "synthetic public reference"}]}
        self.assertEqual(self.hook("PreToolUse", request, name="webrun"), {})
        attempt, = self.directory.glob("web-*-pre.json")
        original = attempt.read_bytes()
        read = r.evidence_read

        def fail_route(path):
            if path.name == "web-route.json":
                raise OSError("Injected route read failure after retrieval")
            return read(path)

        with mock.patch.object(r, "evidence_read", side_effect=fail_route):
            self.assertEqual(self.hook("PostToolUse", request, "Synthetic result", name="webrun").get("decision"), "block")
        self.assertEqual(attempt.read_bytes(), original)
        self.assertFalse(self.action("check")["web"]["complete"])
        with self.assertRaises(r.ResearchError):
            self.action("close")


class SnapshotEvidenceTests(StreamEvidenceTests):
    transport = "stream-v2"

    def test_unreadable_diagnostics_remain_optional_and_create_no_proof(self):
        activation = self.action("activate")
        self.finish(activation["resume_command"])
        diagnostic = self.directory / f"diagnostics-{activation['generation']}.json"
        original = diagnostic.read_bytes()
        stat = Path.stat

        def fail_stat(path, *args, **kwargs):
            if path == diagnostic:
                raise PermissionError("Injected optional telemetry metadata failure")
            return stat(path, *args, **kwargs)

        with mock.patch.object(Path, "stat", fail_stat):
            status = self.action("check")
        self.assertEqual(status["diagnostics"]["status"], "unavailable")
        self.assertTrue(status["ready_to_close"])
        self.assertEqual(diagnostic.read_bytes(), original)

    def test_immutable_receipt_survives_metadata_access_failure(self):
        receipt = self.project / "immutable.json"
        r.evidence_write(receipt, {"original": True}, immutable=True)
        original = receipt.read_bytes()
        stat = os.stat

        def fail_stat(path, *args, **kwargs):
            if os.fspath(path) == str(receipt):
                raise PermissionError("Injected metadata access failure")
            return stat(path, *args, **kwargs)

        # Exercise the documented false-on-OSError predicate on Windows too.
        with mock.patch.object(os.path, "exists", genericpath.exists), \
                mock.patch.object(os, "stat", side_effect=fail_stat), self.assertRaises(OSError):
            r.evidence_write(receipt, {"replacement": True}, immutable=True)
        self.assertEqual(receipt.read_bytes(), original)

    def test_web_route_metadata_failure_cannot_replace_another_active_owner(self):
        self.action("activate", public_web=True, record="report.md")
        route = self.root / ".research/evidence" / self.session / "web-route.json"
        original = route.read_bytes()
        other = self.root / "other project"
        other.mkdir()
        stat = os.stat

        def fail_stat(path, *args, **kwargs):
            if os.fspath(path) == str(route):
                raise PermissionError("Injected route metadata failure")
            return stat(path, *args, **kwargs)

        with mock.patch.object(os.path, "exists", genericpath.exists), \
                mock.patch.object(os, "stat", side_effect=fail_stat), self.assertRaises(OSError):
            r.evidence_web_route(other, other / ".research/evidence" / self.session,
                                 {"hook_root": str(self.root), "id": "f" * 32})
        self.assertEqual(route.read_bytes(), original)

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
                mock.patch.object(r, "evidence_read", wraps=r.evidence_read) as metadata, \
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
            self.assertLessEqual(sum(call.args[0].name == "header.json" for call in metadata.call_args_list), 2 * len(frames))
            self.assertLessEqual(sum(call.args[0].name == "cursor.json" for call in metadata.call_args_list), len(frames))
            self.assertLessEqual(sum(call.args[0].name.startswith("batch-") for call in metadata.call_args_list),
                                 2 * len(frames) - 1 + (len(frames) - 1) // 32)
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

    def test_batch_cache_is_local_to_next_and_reads_again_at_group_boundary(self):
        (self.project / "report.md").write_bytes(b"x" * (r.READER_TEXT_LIMIT * 32))
        activation = self.action("activate")
        first = self.page(activation["resume_command"])
        receipt = first["receipt_id"]
        index_dir = self.directory / f"index-{receipt}"
        self.assertEqual(first["page"]["count"], 34)
        with mock.patch.object(r, "evidence_read", wraps=r.evidence_read) as reads:
            pending = self.action("next")
            self.assertEqual(sum(call.args[0].name.startswith("batch-") for call in reads.call_args_list), 1)
        self.assertEqual(pending["page"]["index"], 1)
        group = index_dir / "batch-0.json"
        original = group.read_bytes()
        r.evidence_write(group, {"pages": []})
        with self.assertRaises(r.ResearchError):
            self.action("next")  # Even a same-process call must observe new corruption.
        group.write_bytes(original)
        self.assertEqual(self.action("next"), pending)
        for delivered, following, expected_reads in ((31, 32, 2), (32, 33, 1)):
            literal = activation["readback_command"] + f" --receipt {receipt} --page {delivered}"
            self.calls += 1
            self.assertEqual(self.hook("PreToolUse", literal), {})
            frame = self.action("readback", receipt=receipt, page=delivered)
            self.assertEqual(self.hook("PostToolUse", literal, r.evidence_output(frame).decode()), {})
            r.evidence_write(index_dir / "cursor.json", {"next": delivered})
            with mock.patch.object(r, "evidence_read", wraps=r.evidence_read) as reads:
                frame = self.action("next")
                self.assertEqual(sum(call.args[0].name.startswith("batch-") for call in reads.call_args_list), expected_reads)
            self.assertEqual(frame["page"]["index"], following)
        self.assertFalse(self.action("check")["ready_to_close"])
        with self.assertRaises(r.ResearchError):
            self.action("close")

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
        descriptor = self.directory / f"index-{receipt}" / "batch-0.json"
        value = r.evidence_read(descriptor)
        raw = b"!" * value["pages"][0]["page"]["part"]["bytes"]
        value["pages"][0]["page"]["part"]["sha256"] = r.evidence_blob(self.directory, raw)
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

    def test_batch_boundaries_and_legacy_index_preserve_frames(self):
        (self.project / "report.md").write_bytes(b"x" * (r.READER_TEXT_LIMIT * 32))
        self.action("activate")
        first = self.action("next")
        receipt = first["receipt_id"]
        state = r.evidence_read(self.directory / "session.json")
        activation = state["activations"][-1]
        bundle = r.evidence_read(self.directory / f"readback-{receipt}.json")
        authoritative = r.EvidenceFrames(self.directory, activation, receipt, bundle)
        folder = self.directory / f"index-{receipt}"
        self.assertEqual([len(r.evidence_read(folder / f"batch-{i}.json")["pages"]) for i in range(2)], [32, 2])
        for index in (0, 30, 31, 32, 33):
            self.assertEqual(self.action("readback", receipt=receipt, page=index), authoritative[index])
        with mock.patch.object(r.os, "fsync", wraps=r.os.fsync) as sync:
            r.evidence_index_create(self.directory, activation, receipt, authoritative)
            self.assertEqual(sync.call_count, 0)  # Immutable re-entry needs no rewrite.
        self.assertFalse(self.action("check")["ready_to_close"])
        self.action("close", incomplete=True, reason="Synthetic boundary emission without native delivery")
        (self.project / "report.md").write_bytes(b"legacy index")
        command = self.action("activate")["resume_command"]
        state = r.evidence_read(self.directory / "session.json")
        state["activations"][-1]["reader_index"] = "page-cache-v1"
        r.evidence_save_session(self.directory, state)
        frames = self.finish(command)
        legacy = self.directory / f"index-{frames[0]['receipt_id']}"
        self.assertTrue((legacy / "0.json").exists())
        self.assertNotIn("batch_size", r.evidence_read(legacy / "header.json"))
        self.assertTrue(self.action("close")["ready_to_close"])

    def test_batch_publication_failure_preserves_durable_files_and_recovers(self):
        (self.project / "report.md").write_bytes(b"x" * (r.READER_TEXT_LIMIT * 32))
        original_replace, original_create = r.os.replace, r.evidence_index_create
        boundaries = ("fsync", "batch-0.json", "header.json", "session.json", "reader-state.json", "cursor.json")
        for number, boundary in enumerate(boundaries):
            with self.subTest(boundary=boundary):
                self.session = f"33333333-3333-4333-8333-{number:012d}"
                self.directory = self.project / ".research/evidence" / self.session
                with mock.patch.dict(os.environ, CODEX_SESSION_ID=self.session, CODEX_THREAD_ID=self.session):
                    self.action("activate")
                    before = (self.directory / "session.json").read_bytes()
                    def replace(source, destination):
                        if Path(destination).name == boundary:
                            raise OSError("Injected publication failure")
                        return original_replace(source, destination)
                    def create(*args):
                        with mock.patch.object(r.os, "fsync", side_effect=OSError("Injected fsync failure")):
                            return original_create(*args)
                    target, name, replacement = ((r, "evidence_index_create", create) if boundary == "fsync"
                                                else (r.os, "replace", replace))
                    with mock.patch.object(target, name, replacement), self.assertRaisesRegex(OSError, "Injected"):
                        self.action("next")
                    folder, = self.directory.glob("index-*")
                    if boundary in ("fsync", "batch-0.json", "header.json"):
                        self.assertFalse((folder / "header.json").exists())
                    else:
                        self.assertTrue((folder / "header.json").exists())
                    if boundary not in ("reader-state.json", "cursor.json"):
                        self.assertEqual((self.directory / "session.json").read_bytes(), before)
                    saved = {path: path.read_bytes() for path in folder.glob("batch-*.json")}
                    frame = self.action("next")
                    self.assertEqual(frame["page"]["index"], 0)
                    self.assertEqual({path: path.read_bytes() for path in saved}, saved)
                    self.assertFalse(list(folder.glob("*.tmp")))
                    self.assertFalse(list(self.directory.glob("page-matched-*.json")))
                    self.assertFalse(self.action("check")["ready_to_close"])

    def test_batch_corruption_and_immutable_collision_fail_closed(self):
        self.action("activate")
        frame = self.action("next")
        receipt = frame["receipt_id"]
        path = self.directory / f"index-{receipt}" / "batch-0.json"
        original = path.read_bytes()
        original_value = r.evidence_read(path)
        bad_values = [dict(pages=[]), dict(pages=original_value["pages"][:-1]),
                      dict(pages=[original_value["pages"][0]] * len(original_value["pages"]))]
        for value in bad_values:
            with self.subTest(value=value):
                r.evidence_write(path, value)
                with self.assertRaises(r.ResearchError):
                    self.action("next")
        path.write_bytes(b"x" * (r.READER_INDEX_LIMIT + 1))
        with self.assertRaisesRegex(r.ResearchError, "bounded size"):
            self.action("next")
        path.unlink()
        with self.assertRaisesRegex(r.ResearchError, "Cannot read reader descriptor batch"):
            self.action("next")
        r.evidence_write(path, bad_values[0])
        conflict = path.read_bytes()
        activation = r.evidence_read(self.directory / "session.json")["activations"][-1]
        frames = r.EvidenceFrames(self.directory, activation, receipt,
                                  r.evidence_read(self.directory / f"readback-{receipt}.json"))
        with self.assertRaisesRegex(r.ResearchError, "Conflicting evidence"):
            r.evidence_index_create(self.directory, activation, receipt, frames)
        self.assertEqual(path.read_bytes(), conflict)
        self.assertFalse(self.action("check")["ready_to_close"])
        path.write_bytes(original)
        self.assertEqual(self.action("next"), frame)

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
