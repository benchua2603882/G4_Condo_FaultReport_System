"""Offline tests for admin notifications and the history and search menus."""
import unittest
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