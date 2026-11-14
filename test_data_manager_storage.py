"""Storage tests"""

import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from data_manager import JsonReportRepository


class DataManagerTests(unittest.TestCase):
    """Test storage using temporary files, not real complaints."""

    def setUp(self):
        """Create a separate temporary repository for each test."""
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

        self.path = Path(self.folder.name) / "reports.json"
        self.repository = JsonReportRepository(self.path)

        self.complaint = [
            "complaint_001",
            "Test Resident",
            "91234567",
            "Pipe leaking in corridor",
            "no_image",
            "2026-11-12T10:00:00+08:00",
            {
                "accepted": True,
                "is_unclear": False,
                "fault_category": "plumbing",
                "issue_summary": "A pipe is leaking in the corridor.",
                "status": "Pending Action",
            },
        ]

    def test_load_legacy_record(self):
        """Load an older complaint without adding invented history."""
        self.path.write_text(
            json.dumps([self.complaint]),
            encoding="utf-8",
        )
        before = self.path.read_bytes()

        reports = self.repository.load_reports()

        self.assertEqual(reports, [self.complaint])
        self.assertNotIn("history", reports[0][6])
        self.assertEqual(self.path.read_bytes(), before)

    def test_edit_preserves_history(self):
        """Keep saved history even when the edited draft omits it."""
        saved = self.repository.save_report(
            self.complaint, actor="Resident"
        )
        previous_history = deepcopy(saved[6]["history"])

        draft = deepcopy(saved)
        draft[1] = "Updated Resident"
        draft[6].pop("history")

        self.repository.update_report(draft)
        reloaded = self.repository.get_report("complaint_001")
        history = reloaded[6]["history"]

        self.assertEqual(reloaded[1], "Updated Resident")
        self.assertEqual(history[:-1], previous_history)
        self.assertEqual(len(history), len(previous_history) + 1)
        self.assertEqual(history[-1]["action"], "Complaint edited")
        self.assertEqual(history[-1]["actor"], "Admin")
        self.assertEqual(
            history[-1]["changes"]["name"],
            {"old": "Test Resident", "new": "Updated Resident"},
        )

    def test_status_and_history_saved_together(self):
        """Save the new status and its corresponding history entry."""
        saved = self.repository.save_report(self.complaint)
        previous_history = deepcopy(saved[6]["history"])

        self.repository.update_complaint_status(
            "complaint_001", "Resolved"
        )
        reloaded = self.repository.get_report("complaint_001")
        history = reloaded[6]["history"]

        self.assertEqual(reloaded[6]["status"], "Resolved")
        self.assertEqual(history[:-1], previous_history)
        self.assertEqual(history[-1]["action"], "Status changed")
        self.assertEqual(
            history[-1]["changes"]["status"],
            {"old": "Pending Action", "new": "Resolved"},
        )

    def test_failed_write_preserves_original_file(self):
        """Keep the original status and history if replacement fails."""
        self.repository.save_report(self.complaint)
        before = self.path.read_bytes()

        with patch(
            "data_manager.os.replace",
            side_effect=OSError("Simulated write failure"),
        ) as replace:
            with self.assertRaises(OSError):
                self.repository.update_complaint_status(
                    "complaint_001", "Resolved"
                )
            replace.assert_called_once()

        self.assertEqual(self.path.read_bytes(), before)
        reloaded = self.repository.get_report("complaint_001")
        self.assertEqual(reloaded[6]["status"], "Pending Action")

    def test_history_survives_repository_restart(self):
        """Load the same saved record using a new repository object."""
        self.repository.save_report(
            self.complaint, actor="Resident"
        )
        self.repository.update_complaint_status(
            "complaint_001", "Contractor contacted"
        )
        expected = self.repository.get_report("complaint_001")

        restarted_repository = JsonReportRepository(self.path)
        actual = restarted_repository.get_report("complaint_001")

        self.assertEqual(actual, expected)
        self.assertEqual(len(actual[6]["history"]), 2)
        self.assertEqual(
            actual[6]["status"], "Contractor contacted"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)