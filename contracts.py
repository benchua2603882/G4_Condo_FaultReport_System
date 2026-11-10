"""Small contracts used by application orchestration and replaceable components.

Repositories return the existing seven-item JSON-compatible records and raise
ValueError for invalid operations, OSError for storage failures. Providers
return parsed dictionaries or raise; AIManager handles failure markers.
"""
from abc import ABC, abstractmethod
from typing import Protocol


class AnalysisProvider(ABC):
    """Boundary for one external analysis request; no domain decisions."""

    @abstractmethod
    def request_analysis(self, complaint: list) -> dict:
        """Return parsed provider output or raise on unavailable/invalid output."""
        raise NotImplementedError

class PriorityRule(ABC):
    """Return a priority when applicable, otherwise None, without mutation."""

    @abstractmethod
    def evaluate(self, report: dict) -> str | None:
        """Evaluate a validated report with a severity score."""
        raise NotImplementedError


class Analyzer(Protocol):
    """Only the AI operations needed by application workflows."""
    @property
    def categories(self) -> tuple: ...
    @property
    def risks(self) -> tuple: ...
    def analyze_complaint(self, complaint: list) -> dict: ...
    def validate_response(self, analysis: dict) -> dict: ...


class FaultProcessor(Protocol):
    """Apply existing domain rules to validated analysis."""
    def process_fault(self, ai_result: dict) -> dict: ...


class Authenticator(Protocol):
    """Check credentials without UI or persistence responsibilities."""
    def authenticate_admin(self, username: str, password: str) -> bool: ...


class ReportReader(ABC):
    """Contract for ReportReader operations."""

    @abstractmethod
    def load_reports(self):
        """Read the repository's configured file and return its stored records."""
        raise NotImplementedError

    @abstractmethod
    def get_next_complaint_id(self):
        """Return the next complaint_001-style ID across accepted and pending reports."""
        raise NotImplementedError

    @abstractmethod
    def get_report(self, complaint_id):
        """Return a saved seven-item report by ID, or raise ValueError if missing."""
        raise NotImplementedError

    @abstractmethod
    def filter_reports(self, priority=None, *, query="", status=None, category=None,
                       date_from=None, date_to=None):
        """Improved feature: return records matching all supplied search criteria."""
        raise NotImplementedError

    @abstractmethod
    def load_pending_reviews(self):
        """Return complaints in reports.json that still need manual review."""
        raise NotImplementedError

    @abstractmethod
    def find_report_index(self, reports, complaint_id):
        """Find a report's position in a loaded list, or raise an unknown-ID error."""
        raise NotImplementedError


class ReportWriter(ABC):
    """Contract for ReportWriter operations."""

    @abstractmethod
    def save_report(self, complaint, actor="Resident"):
        """Save an accepted/pending record and return its copy with activity history."""
        raise NotImplementedError

    @abstractmethod
    def update_report(self, complaint):
        """Replace an existing report with an accepted or pending-review record."""
        raise NotImplementedError

    @abstractmethod
    def delete_report(self, complaint_id):
        """Remove one report by ID and return it after the file is safely written."""
        raise NotImplementedError

    @abstractmethod
    def update_complaint_status(self, complaint_id, status):
        """Update one accepted report by ID and persist its new status."""
        raise NotImplementedError

    @abstractmethod
    def approve_pending_review(self, report):
        """Replace one pending record with its approved result in a single atomic write."""
        raise NotImplementedError


class ReportRepository(ReportReader, ReportWriter):
    """Combined contract for workflows that need reading and writing."""


class UserInterface(Protocol):
    """Contract for UserInterface operations."""

    def show_welcome(self):
        """Ask whether the user is a resident or admin; return '1', '2', or 'quit'."""
        ...

    def collect_admin_credentials(self):
        """Return the entered username and password, or None to cancel login."""
        ...

    def show_menu(self, role='resident', pending_count=None):
        """Show an admin's pending count and return a choice allowed for the role."""
        ...
    def collect_complaint(self, complaint_id):
        """Ask for complaint details and return the initial six-item list."""
        ...

    def show_message(self, message):
        """Print the supplied message or complaint list to the terminal."""
        ...


    def collect_manual_analysis(self, complaint, categories, risks):
        """Collect an admin's classification and explicit approval, or return None."""
        ...

    def show_goodbye(self):
        """Print the goodbye message when the user exits."""
        ...

    def show_reports(self, reports):
        """Display complaints in table rows, with full details for one report."""
        ...

    def show_report_menu(self):
        """Return status, view, edit, delete, history, search or back (1-7)."""
        ...

    # New feature contracts: history presentation and combined search input.
    def show_report_history(self, report):
        """Display activity entries for one complaint as a table."""
        ...

    def collect_report_filters(self, categories):
        """Return optional search criteria or None on cancellation."""
        ...

    def collect_report_id(self):
        """Return the entered complaint ID, or None to go back to the main menu."""
        ...

    def choose_complaint_status(self):
        """Return the chosen status string, or None for Go back to the main menu."""
        ...

    def collect_report_edits(self, report):
        """Return an edited copy on Save, or None on Go back without saving."""
        ...

    def confirm_report_deletion(self, report):
        """Show the selected report and return True only for an explicit Y."""
        ...