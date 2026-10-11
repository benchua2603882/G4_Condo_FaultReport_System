import logging
from pathlib import Path

import ai_manager
import data_manager
import io_manager
import logic_manager


def analyze_report(complaint):
    """Run AI and rules; return accepted details or a manual-review marker."""

    ai_result = ai_manager.analyze_complaint(complaint)
    processed = logic_manager.process_fault(ai_result)
    if processed["accepted"]:
        processed["status"] = "Pending Action"
    # Emergency instructions must be visible even if a later save fails.
    if processed.get("emergency_action"):
        io_manager.show_message(processed["emergency_action"])
    return processed


def process_new_report():
    """Run one complaint through the I/O, AI, logic, and data managers.

    Collect input and return the saved seven-item record. AI failures go to
    reports.json as Pending Manual Review; accepted reports use Pending Action.
    Return None for unclear reports, unexpected processing errors or failed writes.
    """

    try:
        complaint_id = data_manager.get_next_complaint_id()
    except (OSError, ValueError) as error:
        io_manager.show_message(f"Unable to generate complaint ID: {error}")
        return None

    complaint = io_manager.collect_complaint(complaint_id)

    io_manager.show_message("\nComplaint details collected:")
    io_manager.show_message(complaint)

    io_manager.show_message("\nSending complaint to Gemini for analysis...")
    try:
        processed = analyze_report(complaint)
    except Exception as error:
        # Report the failure and let the user return to the menu.
        io_manager.show_message(f"AI analysis failed: {error}")
        io_manager.show_message("Complaint not saved. Please try again.")
        return None

    if processed.get("manual_input_required"):
        report = complaint + [processed]
        try:
            data_manager.save_report(report)
        except (OSError, ValueError) as error:
            io_manager.show_message(f"Unable to save complaint for review: {error}")
            return None
        io_manager.show_message(
            f"Complaint {complaint[0]} saved with status Pending Manual Review because AI analysis is unavailable."
        )
        return report

    if not processed["accepted"]:
        io_manager.show_message(processed["reason"])
        io_manager.show_message("Complaint not saved.")
        return None

    # Preserve the original six fields and append the AI/logic results.
    complaint.append(processed)
    try:
        data_manager.save_report(complaint)
    except (OSError, ValueError) as error:
        io_manager.show_message(f"Unable to save complaint: {error}")
        return None

    io_manager.show_message(f"\nComplaint {complaint[0]} saved successfully.")
    io_manager.show_message(processed["alert"])

    return complaint

    if not processed["accepted"]:
        io_manager.show_message(processed["reason"])
        io_manager.show_message("Complaint not saved.")
        return None

    # Preserve the original six fields and append the AI/logic results.
    complaint.append(processed)
    try:
        data_manager.save_report(complaint)
    except (OSError, ValueError) as error:
        io_manager.show_message(f"Unable to save complaint: {error}")
        return None

    io_manager.show_message(f"\nComplaint {complaint[0]} saved successfully.")
    io_manager.show_message(processed["alert"])

    return complaint

def manually_analyze_report(complaint):
    """Collect approved admin details and apply the usual severity/routing rules.

    Return processed details marked as a manual review, or None on cancellation.
    This workflow is called only from authenticated admin actions.
    """

    analysis = io_manager.collect_manual_analysis(
        complaint, ai_manager.FAULT_CATEGORIES, ai_manager.RISK_INDICATORS
    )
    if analysis is None:
        return None
    processed = logic_manager.process_fault(ai_manager.validate_response(analysis))
    processed["status"] = "Pending Action"
    processed["review_source"] = "manual"
    if processed.get("emergency_action"):
        io_manager.show_message(processed["emergency_action"])
    return processed

def review_pending_reports():
    """Let an authenticated admin select and approve queued complaints by ID."""

    while True:
        try:
            pending = data_manager.load_pending_reviews()
        except (OSError, ValueError) as error:
            io_manager.show_message(f"Unable to load manual reviews: {error}")
            return
        if not pending:
            io_manager.show_message("No complaints are awaiting manual review.")
            return
        io_manager.show_message("Complaints awaiting manual review:")
        io_manager.show_reports(pending)
        complaint_id = io_manager.collect_report_id()
        if complaint_id is None:
            return
        try:
            complaint = pending[data_manager.find_report_index(pending, complaint_id)]
        except ValueError:
            io_manager.show_message("Complaint ID not found. Please try again.")
            continue
        try:
            processed = manually_analyze_report(complaint)
            if processed is None:
                io_manager.show_message("Review cancelled. Complaint remains awaiting review.")
                return
            data_manager.approve_pending_review(complaint[:6] + [processed])
        except (OSError, ValueError) as error:
            io_manager.show_message(f"Unable to approve complaint: {error}")
            return
        io_manager.show_message(f"Complaint {complaint_id} approved and saved with Pending Action status.")
        io_manager.show_message(processed["alert"])


def view_reports():
    """Load and display the latest saved reports without changing storage.

    Adapted from HDB prototype app commit 6d688fb for the 7 October scope.
    The I/O manager handles formatting and the empty-list message. Show a
    readable error and return if storage cannot be read or contains bad JSON.
    """

    try:
        reports = data_manager.load_reports()
    except (OSError, ValueError) as error:
        io_manager.show_message(f"Unable to load reports: {error}")
        return

    io_manager.show_reports(reports)

def select_report(reports):
    """Prompt for an existing report ID and load its current saved record.

    Retry IDs missing from the supplied list. Return None on Go back or
    storage errors. Reload the selected record before editing or deleting it.
    """

    while True:
        complaint_id = io_manager.collect_report_id()
        if complaint_id is None:
            return None
        try:
            data_manager.find_report_index(reports, complaint_id)
        except ValueError:
            io_manager.show_message("Complaint ID not found. Please try again.")
            continue
        try:
            return data_manager.get_report(complaint_id)
        except (OSError, ValueError) as error:
            io_manager.show_message(f"Unable to load complaint: {error}")
            return None

def view_one_report(reports):
    """Display one report selected by ID; return False if selection is cancelled."""

    report = select_report(reports)
    if report is None:
        return False
    io_manager.show_reports([report])
    return True

def edit_report(reports):
    """Edit a selected complaint and save only after any fault changes are accepted.

    Contact-only edits preserve analysis/status. Description or image edits
    rerun AI and business rules and reset status to Pending Action. If AI is
    unavailable, offer manual admin approval. Failed or cancelled edits keep
    the original report intact. Return False on Go back.
    """

    original = select_report(reports)
    if original is None:
        return False
    draft = io_manager.collect_report_edits(original)
    if draft is None:
        return False
    if draft == original:
        io_manager.show_message("No changes to save.")
        return True
    if draft[3:5] != original[3:5]:
        io_manager.show_message("Analyzing the updated complaint with Gemini...")
        try:
            processed = analyze_report(draft[:6])
        except Exception as error:
            io_manager.show_message(f"Analysis failed; original complaint kept: {error}")
            return True
        if processed.get("manual_input_required"):
            io_manager.show_message("AI analysis is unavailable. Review this edit manually or go back to keep the original.")
            try:
                processed = manually_analyze_report(draft)
            except ValueError as error:
                io_manager.show_message(f"Invalid review; original complaint kept: {error}")
                return True
            if processed is None:
                io_manager.show_message("Changes not saved. Original complaint kept.")
                return True
        if not processed["accepted"]:
            io_manager.show_message(processed["reason"])
            io_manager.show_message("Changes not saved. Original complaint kept.")
            return True
        draft[6] = processed
    try:
        data_manager.update_report(draft)
    except (OSError, ValueError) as error:
        io_manager.show_message(f"Unable to save changes: {error}")
        return False
    io_manager.show_message(f"Complaint {draft[0]} updated successfully.")
    return True

def remove_report(reports):
    """Delete a selected report only after confirmation; return False on Go back."""

    report = select_report(reports)
    if report is None:
        return False
    if not io_manager.confirm_report_deletion(report):
        io_manager.show_message("Deletion cancelled.")
        return True
    try:
        data_manager.delete_report(report[0])
    except (OSError, ValueError) as error:
        io_manager.show_message(f"Unable to delete complaint: {error}")
        return False
    io_manager.show_message(f"Complaint {report[0]} deleted.")
    return True


def update_report_status(reports):
    """Select a saved complaint by ID and persist the selected status.

    Take the currently loaded report list and retry unknown IDs. Return True
    after saving, or False for Go back or a storage error.
    """

    report = select_report(reports)
    if report is None:
        return False
    complaint_id = report[0]

    status = io_manager.choose_complaint_status()
    if status is None:
        return False
    try:
        data_manager.update_complaint_status(complaint_id, status)
    except (OSError, ValueError) as error:
        io_manager.show_message(f"Unable to update complaint status: {error}")
        return False
    io_manager.show_message(f"Complaint {complaint_id} status updated to {status}.")
    return True

def main():
    """Start the application and handle menu choices until the user quits.

    Configure logging and load records, then ask for Resident or Admin.
    Authenticate admins before permitting report management. Back clears
    the role; quit exits. Take no arguments and return None when finished.
    """

    logging.basicConfig(
        filename=Path(__file__).resolve().parent / "application.log",
        level=logging.ERROR,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        data_manager.load_reports()
    except (OSError, ValueError) as error:
        io_manager.show_message(f"Unable to load saved reports: {error}")

    role = None
    while True:
        if role is None:
            welcome_choice = io_manager.show_welcome()
            if welcome_choice == "quit":
                io_manager.show_goodbye()
                break
            if welcome_choice == "1":
                role = "resident"
            else:
                credentials = io_manager.collect_admin_credentials()
                if credentials is None:
                    continue
                if not logic_manager.authenticate_admin(*credentials):
                    io_manager.show_message("Invalid username or password. Please try again.")
                    continue
                role = "admin"
                io_manager.show_message("Admin login successful.")

        choice = io_manager.show_menu(role)

        if choice == "quit":
            io_manager.show_goodbye()
            break

        elif choice == "back":
            role = None

        elif choice == "1":
            process_new_report()

        elif choice == "2" and role == "admin":
            view_reports()

        elif choice == "3" and role == "admin":
            review_pending_reports()

if __name__ == "__main__":
    main()
