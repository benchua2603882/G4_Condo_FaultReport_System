import io_manager
import data_manager


def main():
    """Test the menu, report loading, and complaint ID generation."""
    io_manager.show_message("Condo Fault Report System - development test")

    # Check whether existing reports can be loaded.
    try:
        reports = data_manager.load_reports()
        io_manager.show_message(f"Saved reports: {len(reports)}")
    except (OSError, ValueError) as error:
        io_manager.show_message(f"Unable to load reports: {error}")
        return

    # Test the resident menu until the user exits.
    while True:
        choice = io_manager.show_menu(role="resident")

        if choice == "1":
            try:
                complaint_id = data_manager.get_next_complaint_id()
                io_manager.show_message(
                    f"Next complaint ID: {complaint_id}"
                )
                io_manager.show_message(
                    "Complaint collection and saving are not connected yet."
                )
            except (OSError, ValueError) as error:
                io_manager.show_message(
                    f"Unable to generate complaint ID: {error}"
                )

        elif choice in ("back", "quit"):
            # The welcome screen will be integrated later.
            io_manager.show_goodbye()
            break


if __name__ == "__main__":
    main()