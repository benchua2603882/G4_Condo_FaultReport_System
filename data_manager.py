import json
import os
import re
from datetime import date
from activity_history import ActivityHistory
from pathlib import Path
from tempfile import NamedTemporaryFile
from contracts import ReportRepository
from report_policy import ReportPolicy

DEFAULT_REPORTS_FILE = Path(__file__).resolve().parent / "reports.json"
COMPLAINT_STATUSES = ("Contractor contacted", "Pending Action", "Resolved")

# Docker supplies its mounted storage path; native runs keep the project default.
REPORTS_FILE = Path(os.getenv("REPORTS_FILE", Path(__file__).resolve().parent / "reports.json"))
COMPLAINT_STATUSES = ("Contractor contacted", "Pending Action", "Resolved")

class JsonReportRepository(ReportRepository):
    """Persist the existing list records at this instance's selected JSON path."""

    def __init__(self, reports_file=DEFAULT_REPORTS_FILE):
        """Own the record policy and keep storage paths independent per instance."""
        self._reports_file = Path(reports_file)
        self._policy = ReportPolicy()
        # New feature: build history separately, then persist it with the record.
        self._history = ActivityHistory()

    @property
    def reports_file(self):
        """Expose the configured path without allowing accidental reassignment."""
        return self._reports_file

    def find_report_index(self, reports, complaint_id):
        """Find a report's position in a loaded list, or raise an unknown-ID error."""

        for index, report in enumerate(reports):
            if isinstance(report, list) and len(report) == 7 and report[0] == complaint_id:
                return index
        raise ValueError(f"Complaint ID '{complaint_id}' was not found.")

    def load_reports(self):
        """Read self._reports_file and return its stored list of complaint records.

        Take no arguments and return an empty list if the file does not exist.
        Raise an error for unreadable files, invalid JSON, or a non-list result
        so the caller can report the problem without overwriting existing data.
        """

        try:
            with self._reports_file.open(encoding="utf-8-sig") as file:
                reports = json.load(file)
        except FileNotFoundError:
            return []

        if not isinstance(reports, list):
            raise ValueError("The reports JSON file must contain a list of reports.")

        # Older accepted reports have no status yet; display them as pending.
        for report in reports:
            if isinstance(report, list) and len(report) == 7 and isinstance(report[6], dict):
                if report[6].get("accepted") is True:
                    report[6].setdefault("status", "Pending Action")
        return reports


    def save_report(self, complaint, actor="Resident"):
        """Save an accepted or explicitly pending-manual-review seven-item complaint.

        Unclear/rejected AI results are excluded unless awaiting manual review.
        Reject an invalid record or duplicate ID. Load existing reports, append
        the complaint, and write a temporary file before replacing self._reports_file.
        Return the saved copy, including history; raise on validation/file errors.
        """

        pending = self._policy.is_pending_review(complaint)
        if not self._policy.is_accepted_report(complaint) and not pending:
            raise ValueError("Only accepted complaints or complaints pending manual review can be saved.")

        # A corrupt existing file raises an error; never overwrite it with an empty list.
        reports = self.load_reports()
        if any(isinstance(report, list) and report and report[0] == complaint[0] for report in reports):
            raise ValueError("A report with this complaint ID already exists.")
        details = dict(complaint[6])
        details.setdefault("status", "Pending Action")
        if not pending and details["status"] not in COMPLAINT_STATUSES:
            raise ValueError("Invalid complaint status.")
        saved = self._history.record(
            complaint[:6] + [details], "Submitted", actor,
            {"status": {"old": None, "new": details["status"]}},
        )
        reports.append(saved)
        self.write_reports(reports)
        return saved
    
    def write_reports(self, reports):
        """Write a report list atomically, preserving the old file on failure.

        Used after validation by the save, edit, status, and delete functions.
        Return None on success and pass file errors to the caller.
        """

        temporary_path = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self._reports_file.parent,
                prefix="reports-", suffix=".tmp", delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump(reports, file, indent=2, ensure_ascii=False)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self._reports_file)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
                 
    def get_report(self, complaint_id):
        """Return a saved seven-item report by ID, or raise ValueError if missing."""
            
        reports = self.load_reports()
        return reports[self.find_report_index(reports, complaint_id)]
    
    def update_report(self, complaint):
        """Replace an existing report with an accepted or pending-review record.

        Keep its ID and original submission time. Return the saved record, or
        raise an error without writing for invalid data or an unknown ID.
        """

        if not self._policy.is_pending_review(complaint) and (
            not self._policy.is_accepted_report(complaint) or complaint[6].get("status") not in COMPLAINT_STATUSES
        ):
            raise ValueError("Only accepted or pending-manual-review complaints can be updated.")
        reports = self.load_reports()
        index = self.find_report_index(reports, complaint[0])
        if complaint[5] != reports[index][5]:
            raise ValueError("The original submission time cannot be changed.")
        original = reports[index]
        changes = self._history.changes_between(original, complaint)
        if not changes:
            return original
        # New feature: restore history from disk even when reanalysis replaces details.
        updated = self._history.record(complaint, "Complaint edited", "Admin", changes, original)
        reports[index] = updated
        self.write_reports(reports)
        return updated

    def delete_report(self, complaint_id):
        """Remove one report by ID and return it after the file is safely written.

        The caller must obtain user confirmation first. Raise ValueError for an
        unknown ID and propagate storage errors without replacing existing data.
        """

        reports = self.load_reports()
        index = self.find_report_index(reports, complaint_id)
        deleted = reports.pop(index)
        self.write_reports(reports)
        return deleted

    def update_complaint_status(self, complaint_id, status):
        """Update one accepted report by ID and persist its new status.

        Accept one of COMPLAINT_STATUSES. Return the updated record; raise
        ValueError for an unknown ID, invalid status, or unaccepted record.
        File errors propagate without replacing the original data.
        """

        if status not in COMPLAINT_STATUSES:
            raise ValueError("Invalid complaint status.")
        reports = self.load_reports()
        index = self.find_report_index(reports, complaint_id)
        report = reports[index]
        if not self._policy.is_accepted_report(report):
            raise ValueError("Review and approve this complaint using admin option 3 before changing its status.")
        previous_status = report[6].get("status")
        if previous_status == status:
            return report
        # Improved feature: the status change and activity entry share one write.
        updated = self._history.record(report, "Status changed", "Admin", {
            "status": {"old": previous_status, "new": status},
        }, previous=report)
        updated[6]["status"] = status
        reports[index] = updated
        self.write_reports(reports)
        return updated

def filter_reports(priority):
    """Load saved records and return those matching the supplied priority.

    Accept a priority string such as 'high' or 'EMERGENCY', ignoring case.
    Return a list of matching seven-item records, or [] if none match.
    File-loading errors are passed to the caller.
    """

    return [
        report for report in load_reports()
        if isinstance(report, list) and len(report) == 7
        and isinstance(report[6], dict)
        and report[6].get("priority") == priority.upper()
    ]

def load_pending_reviews():
    """Return complaints in reports.json that still need manual review."""

    return [report for report in load_reports() if is_pending_review(report)]

def approve_pending_review(report):
    """Replace one pending record with its approved result in a single atomic write."""

    if not is_accepted_report(report) or report[6].get("status") != "Pending Action":
        raise ValueError("Manual approval requires accepted, clear details.")
    reports = load_reports()
    index = find_report_index(reports, report[0])
    if not is_pending_review(reports[index]):
        raise ValueError("This complaint is no longer pending manual review.")
    if reports[index][:6] != report[:6]:
        raise ValueError("The pending complaint changed; reload it before approval.")
    reports[index] = report
    write_reports(reports)
    return report
