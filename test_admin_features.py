"""Offline tests for new notifications, activity history, and report search."""
import json
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from application import ReportApplication
from authentication import DemoAuthenticator
from data_manager import JsonReportRepository
from io_manager import IOManager
from logic_manager import LogicManager


class AdminFeatureTests(unittest.TestCase):
    """Exercise saved data and real menus without API calls or resident data."""

    def setUp(self):
        """Create an isolated repository, sample analysis and captured terminal."""
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "reports.json"
        self.repo = JsonReportRepository(self.path)
        self.messages = []
        self.analysis = {
            "fault_category": "plumbing", "summary": "Water leaking near the lift.",
            "risk_indicators": ["active_leak"], "common_area_hazard": True,
            "is_unclear": False,
        }
        self.ai = Mock()
        self.ai.categories = ("plumbing", "lift", "electrical", "general maintenance")
        self.ai.analyze_complaint.return_value = self.analysis

    def make_app(self, answers=()):
        """Build a real controller with simulated terminal input and AI."""
        responses = iter(answers)
        self.io = IOManager(reader=lambda prompt: next(responses),
                            writer=self.messages.append, password_reader=lambda prompt: "password123")
        return ReportApplication(self.io, self.ai, LogicManager(), self.repo, DemoAuthenticator())

    def report(self, number=1, pending=False, submitted="2026-11-04T10:00:00+08:00"):
        """Return a fresh accepted or pending complaint for repository tests."""
        details = LogicManager().process_fault({"ai_available": False} if pending else self.analysis)
        details.setdefault("status", "Pending Action")
        return [f"complaint_{number:03d}", "Test Resident", "+6591234567",
                "Pipe leaking", "no_image", submitted, details]

    def test_submission_events_and_actors(self):
        """Accepted and AI-failure submissions save one event and the right role."""
        for role, result in [("resident", self.analysis), ("admin", {"ai_available": False})]:
            app = self.make_app(["Test Resident", "91234567", "Pipe leaking", "n"])
            self.ai.analyze_complaint.return_value = result
            saved = app.process_new_report(role)
            self.assertEqual(self.repo.get_report(saved[0]), saved)
            event, = saved[6]["history"]
            self.assertEqual(event["actor"], role.title())
            self.assertEqual(event["action"], "Submitted")
            self.assertEqual(event["changes"]["status"]["new"], saved[6]["status"])
            self.assertIsNotNone(datetime.fromisoformat(event["timestamp"]).tzinfo)

    def test_approval_edit_and_status_keep_history_after_restart(self):
        """Replacing analysis retains prior history and records old/new values."""
        pending = self.repo.save_report(self.report(pending=True))
        approved = self.repo.approve_pending_review(self.report())
        draft = deepcopy(approved)
        draft[1] = "Updated Resident"
        draft[3] = "Lift stopped"
        draft[6] = dict(approved[6], fault_category="lift")
        draft[6].pop("history")
        updated = self.repo.update_report(draft)
        final = self.repo.update_complaint_status(updated[0], "Resolved")
        history = JsonReportRepository(self.path).get_report(final[0])[6]["history"]
        self.assertEqual([h["action"] for h in history],
                         ["Submitted", "Manually approved", "Complaint edited", "Status changed"])
        self.assertEqual(history[:1], pending[6]["history"])
        self.assertEqual(history[1]["changes"]["status"],
                         {"old": "Pending Manual Review", "new": "Pending Action"})
        self.assertEqual(history[2]["changes"]["description"],
                         {"old": "Pipe leaking", "new": "Lift stopped"})
        self.assertEqual(history[3]["changes"]["status"]["new"], "Resolved")
        self.assertNotIn("history", draft[6])

    def test_failed_writes_preserve_record_history_and_draft(self):
        """Submission, edits, approval and status events are atomic with their data."""
        accepted = self.repo.save_report(self.report())
        pending = self.repo.save_report(self.report(2, pending=True))
        edited = deepcopy(accepted)
        edited[1] = "Updated Resident"
        submitted = self.report(3)
        approved = self.report(2)
        draft_copies = deepcopy([edited, submitted, approved])
        before = self.path.read_bytes()
        actions = [lambda: self.repo.save_report(submitted),
                   lambda: self.repo.update_report(edited),
                   lambda: self.repo.approve_pending_review(approved),
                   lambda: self.repo.update_complaint_status(accepted[0], "Resolved")]
        for operation in actions:
            with self.subTest(operation=operation), patch("data_manager.os.replace", side_effect=OSError("Disk full")):
                with self.assertRaises(OSError):
                    operation()
            self.assertEqual(self.path.read_bytes(), before)
            self.assertEqual([edited, submitted, approved], draft_copies)
            self.assertFalse(list(self.path.parent.glob("reports-*.tmp")))
        self.assertEqual(self.repo.load_pending_reviews(), [pending])

    def test_legacy_reports_are_not_given_invented_events(self):
        """Read-only legacy views leave bytes intact; the next change starts history."""
        legacy = self.report()
        legacy[6].pop("status")
        self.path.write_text(json.dumps([legacy]), encoding="utf-8")
        before = self.path.read_bytes()
        self.make_app()
        self.io.show_report_history(self.repo.get_report(legacy[0]))
        self.assertIn("No activity history recorded", "\n".join(self.messages))
        self.assertEqual(self.path.read_bytes(), before)
        updated = self.repo.update_complaint_status(legacy[0], "Resolved")
        self.assertEqual(len(updated[6]["history"]), 1)
        self.assertEqual(updated[6]["history"][0]["action"], "Status changed")

    def test_noop_and_forged_draft_history_do_not_replace_saved_history(self):
        """Selecting the same status or supplying a changed history creates no event."""
        original = self.repo.save_report(self.report())
        before = self.path.read_bytes()
        self.repo.update_complaint_status(original[0], "Pending Action")
        draft = deepcopy(original)
        draft[6]["history"] = []
        self.assertEqual(self.repo.update_report(draft), original)
        self.assertEqual(self.path.read_bytes(), before)
        draft[1] = "Changed Name"
        updated = self.repo.update_report(draft)
        self.assertEqual(updated[6]["history"][:-1], original[6]["history"])

    def test_deleting_report_removes_its_history(self):
        """This basic feature keeps no separate archive of deleted complaints."""
        saved = self.repo.save_report(self.report())
        self.assertEqual(self.repo.delete_report(saved[0]), saved)
        self.assertEqual(JsonReportRepository(self.path).load_reports(), [])

    def test_combined_search_and_filter_are_read_only(self):
        """Case-insensitive criteria combine with AND and ignore historical text."""
        first = self.repo.save_report(self.report())
        second = self.repo.save_report(self.report(2, pending=True))
        draft = deepcopy(first)
        draft[1] = "New Name"
        draft[3] = "Repaired pipe"
        first = self.repo.update_report(draft)
        before = self.path.read_bytes()
        matches = self.repo.filter_reports("medium", query="NEW NAME", status="pending action",
                                          category="PLUMBING", date_from="2026-11-04", date_to="2026-11-04")
        self.assertEqual(matches, [first])
        self.assertEqual(self.repo.filter_reports(query="complaint_002"), [second])
        self.assertEqual(self.repo.filter_reports(query="+659123"), [first, second])
        self.assertEqual(self.repo.filter_reports(query="water leaking", status="Pending Action"), [first])
        self.assertEqual(self.repo.filter_reports(query="Test Resident", status="Pending Action"), [])
        self.assertEqual(self.repo.filter_reports(status="Pending Manual Review"), [second])
        self.assertEqual(self.repo.filter_reports(priority="HIGH"), [])
        self.assertEqual(self.path.read_bytes(), before)

    def test_date_boundaries_invalid_ranges_and_legacy_dates(self):
        """Date filters are inclusive and do not crash on old non-ISO timestamps."""
        first = self.repo.save_report(self.report(submitted="2026-11-01T23:59:59+08:00"))
        second = self.repo.save_report(self.report(2, submitted="2026-11-04T00:00:00+08:00"))
        legacy = self.repo.save_report(self.report(3, submitted="unknown"))
        self.assertEqual(self.repo.filter_reports(date_from="2026-11-01", date_to="2026-11-04"), [first, second])
        self.assertEqual(self.repo.filter_reports(date_from="2026-11-04"), [second])
        self.assertEqual(self.repo.filter_reports(), [first, second, legacy])
        for filters in [dict(date_from="2026-02-30"), dict(date_to="20261104"),
                        dict(date_from="2026-11-05", date_to="2026-11-04")]:
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                self.repo.filter_reports(**filters)

    def test_notification_refreshes_after_admin_action(self):
        """Login shows the pending count; the next menu reflects an approval."""
        self.repo.save_report(self.report(pending=True))
        app = self.make_app(["2", "admin123", "2", "quit"])
        with patch("application.logging.basicConfig"), patch.object(app, "view_reports", side_effect=lambda: self.repo.approve_pending_review(self.report())):
            app.run()
        output = "\n".join(self.messages)
        self.assertIn("[ATTENTION] 1 complaint(s)", output)
        self.assertIn("No complaints are awaiting manual approval.", output)
        self.assertIn("approval (1)", output)
        self.assertIn("approval (0)", output)

    def test_residents_and_failed_logins_do_not_receive_notification(self):
        """Admin-only counts and actions remain hidden until authentication succeeds."""
        for answers in (["1", "2", "3", "quit"], ["2", "wrong", "quit"]):
            app = self.make_app(answers)
            with patch("application.logging.basicConfig"), patch.object(self.repo, "load_pending_reviews") as pending, patch.object(app, "view_reports") as view:
                app.run()
                pending.assert_not_called()
                view.assert_not_called()
        self.assertNotIn("[ATTENTION]", "\n".join(self.messages))

    def test_notification_read_failure_is_not_reported_as_zero(self):
        """Storage errors leave the menu usable and explicitly mark count unavailable."""
        app = self.make_app(["2", "admin123", "quit"])
        with patch("application.logging.basicConfig"), patch.object(self.repo, "load_pending_reviews", side_effect=OSError("Unavailable")):
            app.run()
        output = "\n".join(self.messages)
        self.assertIn("count is unavailable", output)
        self.assertNotIn("No complaints are awaiting", output)

    def test_history_menu_uses_table_for_only_selected_id(self):
        """History rows share the bordered table renderer and preserve long changes."""
        first = self.repo.save_report(self.report())
        self.repo.save_report(self.report(2))
        self.repo.update_complaint_status(first[0], "Contractor contacted")
        app = self.make_app(["5", "missing", "complaint_001", "7"])
        with patch.object(self.io, "show_reports"):
            app.view_reports()
        output = "\n".join(self.messages)
        self.assertIn("Activity history: complaint_001", output)
        self.assertNotIn("complaint_002", output)
        self.assertIn("Status changed", output)
        self.assertIn('"Pending Action" -> "Contractor contacted"', output)
        lines = [line for line in self.messages if line.startswith(("|", "+"))]
        self.assertEqual(len({len(line) for line in lines}), 1)

    def test_search_menu_displays_matches_without_redisplaying_all(self):
        """Search routes through real input, repository filtering and report tables."""
        first = self.repo.save_report(self.report())
        self.repo.save_report(self.report(2))
        app = self.make_app(["6", "complaint_001", "", "", "", "", "", "7"])
        with patch.object(self.io, "show_reports", wraps=self.io.show_reports) as show:
            app.view_reports()
        self.assertEqual(show.call_count, 2)
        self.assertEqual(show.call_args.args, ([first],))
        self.assertIn("Search results: 1 complaint(s) matched.", self.messages)

    def test_empty_search_and_cancellation_do_not_change_storage(self):
        """No matches are explained; cancellation at any filter prompt is safe."""
        self.repo.save_report(self.report())
        before = self.path.read_bytes()
        for index in range(6):
            app = self.make_app([""] * index + ["back"])
            self.assertFalse(app.search_reports())
        app = self.make_app(["unknown", "", "", "", "", ""])
        self.assertTrue(app.search_reports())
        self.assertIn("No complaints match these filters", "\n".join(self.messages))
        self.assertEqual(self.path.read_bytes(), before)

    def test_filter_input_retries_invalid_values_and_dates(self):
        """The form rejects invalid choices/calendar dates and reversed ranges."""
        self.make_app(["", "wrong", "2", "1", "2", "2026-02-30", "2026-11-01", "2026-11-04"])
        result = self.io.collect_report_filters(self.ai.categories)
        self.assertEqual(result, dict(query="", status="Pending Action", category="plumbing",
                                     priority="MEDIUM", date_from="2026-11-01", date_to="2026-11-04"))
        self.make_app(["", "", "", "", "2026-11-05", "2026-11-04", "back"])
        self.assertIsNone(self.io.collect_report_filters(self.ai.categories))
        self.assertIn("Start date must not be after end date", "\n".join(self.messages))


if __name__ == "__main__":
    unittest.main()
