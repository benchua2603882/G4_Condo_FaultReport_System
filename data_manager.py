import json
import re
import os
from tempfile import NamedTemporaryFile
from pathlib import Path

REPORTS_FILE = Path("reports.json")
COMPLAINT_STATUSES = ("Contractor contacted", "Pending Action", "Resolved")

def is_accepted_report(report):
    """Check that a seven-item report has accepted, clear processing details."""

    return (
        isinstance(report, list)
        and len(report) == 7
        and isinstance(report[6], dict)
        and report[6].get("accepted") is True
        and report[6].get("is_unclear") is False
    )

def find_report_index(reports, complaint_id):
    """Find a report's position in a loaded list, or raise an unknown-ID error."""

    for index, report in enumerate(reports):
        if isinstance(report, list) and len(report) == 7 and report[0] == complaint_id:
            return index
    raise ValueError(f"Complaint ID '{complaint_id}' was not found.")

def load_reports():
    """Read REPORTS_FILE and return complaint list.

    Take no arguments and return an empty list if the file does not exist.
    Raise an error for unreadable files, invalid JSON, or a non-list result
    so the caller can report the problem without overwriting existing data.
    """

    try:
        with REPORTS_FILE.open(encoding="utf-8-sig") as file:
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

def get_next_complaint_id():
    """Return the next complaint_001-style ID based on saved reports.

    Start at 001 for an empty or missing file. Use the highest saved numeric
    ID or the record count (for older HDB IDs), whichever is larger, plus one.
    Reading the file each time preserves numbering across application restarts.
    No number is reserved until a report is successfully saved. File errors
    are passed to the caller rather than resetting the sequence.
    """

    reports = load_reports()
    highest_number = len(reports)
    for report in reports:
        if isinstance(report, list) and report and isinstance(report[0], str):
            match = re.fullmatch(r"complaint_([0-9]+)", report[0])
            if match:
                highest_number = max(highest_number, int(match.group(1)))

    return f"complaint_{highest_number + 1:03d}"

def save_report(complaint):
    """Save a seven-item complaint list containing accepted processing details.

    Require accepted=True and is_unclear=False in the processing details.
    Reject an invalid record or duplicate ID. Load existing reports, append
    the complaint, and write a temporary file before replacing REPORTS_FILE.
    Return None on success; raise an error if validation or file access fails.
    """

    if (
        not isinstance(complaint, list)
        or len(complaint) != 7
        or not isinstance(complaint[6], dict)
        or complaint[6].get("accepted") is not True
        or complaint[6].get("is_unclear") is not False
    ):
        raise ValueError("Only a processed, accepted complaint with no clarification pending can be saved.")

    # A corrupt existing file raises an error; never overwrite it with an empty list.
    reports = load_reports()
    if any(isinstance(report, list) and report and report[0] == complaint[0] for report in reports):
        raise ValueError("A report with this complaint ID already exists.")
    details = dict(complaint[6])
    details.setdefault("status", "Pending Action")
    if details["status"] not in COMPLAINT_STATUSES:
        raise ValueError("Invalid complaint status.")
    reports.append(complaint[:6] + [details])
    write_reports(reports)
       
def write_reports(reports):
    """Write a report list atomically, preserving the old file on failure.

    Used after validation by save_report() and update_complaint_status().
    Return None on success and pass file errors to the caller.
    """

    temporary_path = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=REPORTS_FILE.parent,
            prefix="reports-", suffix=".tmp", delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(reports, file, indent=2, ensure_ascii=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, REPORTS_FILE)
    finally:
         if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

def update_complaint_status(complaint_id, status):
    """Update one accepted report by ID and persist its new status.

    Accept one of COMPLAINT_STATUSES. Return the updated record; raise
    ValueError for an unknown ID, invalid status, or unaccepted record.
    File errors propagate without replacing the original data.
    """

    if status not in COMPLAINT_STATUSES:
        raise ValueError("Invalid complaint status.")
    reports = load_reports()
    report = reports[find_report_index(reports, complaint_id)]
    if not is_accepted_report(report):
        raise ValueError("Only accepted, clear reports can be updated.")
    report[6]["status"] = status
    write_reports(reports)
    return report

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

def get_report(complaint_id):
    """Return a saved seven-item report by ID, or raise ValueError if missing."""

    reports = load_reports()
    return reports[find_report_index(reports, complaint_id)]


def update_report(complaint):
    """Replace an existing report with an accepted, validated seven-item record.

    Keep its ID and original submission time. Return the saved record, or
    raise an error without writing for invalid data or an unknown ID.
    """

    if not is_accepted_report(complaint) or complaint[6].get("status") not in COMPLAINT_STATUSES:
        raise ValueError("Only accepted, clear reports with a valid status can be updated.")
    reports = load_reports()
    index = find_report_index(reports, complaint[0])
    if complaint[5] != reports[index][5]:
        raise ValueError("The original submission time cannot be changed.")
    reports[index] = complaint
    write_reports(reports)
    return complaint


def delete_report(complaint_id):
    """Remove one report by ID and return it after the file is safely written.

    The caller must obtain user confirmation first. Raise ValueError for an
    unknown ID and propagate storage errors without replacing existing data.
    """

    reports = load_reports()
    index = find_report_index(reports, complaint_id)
    deleted = reports.pop(index)
    write_reports(reports)
    return deleted