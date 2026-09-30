import json
import re
from pathlib import Path

REPORTS_FILE = Path("reports.json")
ID_FIELD = "complaint_id"

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