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


def main():
    """Load saved reports and dispatch the resident menu until the user exits."""
    io_manager.show_message("Condo Fault Report System")

    try:
        reports = data_manager.load_reports()
        io_manager.show_message(f"Saved reports: {len(reports)}")
    except (OSError, ValueError) as error:
        io_manager.show_message(f"Unable to load reports: {error}")
        return

    while True:
        choice = io_manager.show_menu(role="resident")

        if choice == "1":
            process_new_report()
        elif choice in ("back", "quit"):
            # Back exits until the welcome/login helpers are integrated.
            io_manager.show_goodbye()
            break


if __name__ == "__main__":
    main()
