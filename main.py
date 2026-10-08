import logging
from pathlib import Path

import ai_manager
import data_manager
import io_manager
import logic_manager


def analyze_report(complaint):
    """Run Gemini and business rules; give accepted reports their initial status."""

    ai_result = ai_manager.analyze_complaint(complaint)
    processed = logic_manager.process_fault(ai_result)
    if processed["accepted"]:
        processed["status"] = "Pending Action"
    return processed


def process_new_report():
    """Run one complaint through the I/O, AI, logic, and data managers.

    Take no arguments; collect input from the user. Append accepted AI/logic
    details to the original list, save it, and return the seven-item record.
    Show a message and return None if analysis fails, the report needs
    clarification, or saving fails.
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

if __name__ == "__main__":
    main()
