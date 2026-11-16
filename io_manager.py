from datetime import date, datetime
from pathlib import Path
import json
from copy import deepcopy
from getpass import getpass
from textwrap import wrap


class IOManager:
    """Terminal interaction with replaceable input, output and password readers."""

    def __init__(self, reader=None, writer=None, password_reader=None):
        """Use terminal functions by default or supplied callables for testing."""
        self._reader = reader
        self._writer = writer
        self._password_reader = password_reader

    def _read(self, prompt):
        """Read one answer from the configured input boundary."""
        return input(prompt) if self._reader is None else self._reader(prompt)

    def _write(self, *values):
        """Send text to the configured output boundary."""
        if self._writer is None:
            print(*values)
        else:
            self._writer(*values)

    def _read_password(self, prompt):
        """Read a hidden password unless a test supplies another reader."""
        return getpass(prompt) if self._password_reader is None else self._password_reader(prompt)

    def show_welcome(self):
        """Ask whether the user is a resident or admin; return '1', '2', or 'quit'.

        Repeat invalid choices. Selecting Admin still requires a successful login.
        """

        while True:
            self._write("\nWelcome to the Condo Fault Reporting System")
            self._write("1. Resident")
            self._write("2. Admin")
            self._write("Type 'quit' to exit.")
            choice = self._read("Are you a resident or admin? ").strip().lower()
            if choice in ("1", "2", "quit"):
                return choice
            self._write("Invalid input. Enter 1, 2, or quit.")

    def collect_admin_credentials(self):
        """Return the entered username and password, or None to cancel login.

        Hide password entry in an interactive terminal. Type back at the username
        prompt to return to the welcome screen. The authenticator checks credentials.
        """

        username = self._read("Admin username (or 'back' to cancel): ").strip()
        if username.lower() == "back":
            return None
        password = self._read_password("Admin password: ")
        return username, password

    def show_menu(self, role="resident", pending_count=None):
        """Return a menu choice allowed for the authenticated session role.

        Residents can submit only; admins can also view/manage reports. Return
        back to sign out or quit to exit, and repeat all invalid choices.
        """

        while True:
            self._write(f"\nCondo Fault Reporting System - {role.title()}")
            # New feature: show the refreshed pending-review count only to admins.
            if role == "admin":
                if pending_count is None:
                    self._write("[NOTICE] Pending-review count is unavailable.")
                elif pending_count:
                    self._write(f"[ATTENTION] {pending_count} complaint(s) awaiting manual approval.")
                else:
                    self._write("No complaints are awaiting manual approval.")
            self._write("1. Submit a complaint")
            if role == "admin":
                self._write("2. View reports")
                count_label = "unavailable" if pending_count is None else str(pending_count)
                self._write(f"3. Review complaints awaiting approval ({count_label})")
            self._write("Type 'back' to return to the welcome screen, or 'quit' to exit.")

            choice = self._read("Choose an option: ").strip().lower()

            allowed_choices = ("1", "2", "3", "back", "quit") if role == "admin" else ("1", "back", "quit")
            if choice in allowed_choices:
                return choice

            self._write("Invalid input. Choose an option shown in your menu.")

    def collect_name(self):
        """Ask for the resident's name and return it as a trimmed string.

        Repeat the question if the name is empty or contains anything other
        than letters and spaces. No arguments are needed.
        """

        while True:
            name = self._read("What is your name? ").strip()

            if name.replace(" ", "").isalpha():
                return name

            self._write("Invalid name. Enter letters and spaces only.")

    def collect_phone_number(self):
        """Ask for a phone number and return the validated text.

        Accept digits with an optional single '+' at the beginning. Repeat
        invalid entries and keep any leading '+' or zeros in the returned string.
        """

        while True:
            phone_number = self._read("What is your phone number? ").strip()

            # Remove a leading '+' only for checking.
            # Keep the original input for storage.
            digits = phone_number.removeprefix("+")
            if digits.isascii() and digits.isdecimal():
                return phone_number

            self._write(
                "Invalid phone number. Enter digits only, "
                "with an optional '+' at the beginning."
            )

    def get_required_input(self, prompt):
        """Display the supplied prompt and return a nonempty, trimmed answer.

        The prompt argument is the question shown to the user. Blank answers
        cause the same question to be asked again.
        """

        while True:
            answer = self._read(prompt).strip()

            if answer:
                return answer

            self._write("This field cannot be empty. Please try again.")

    def collect_image_path(self):
        """Ask whether to attach an image and validate the user's file path.

        Return 'no_image' if declined. Otherwise, repeat invalid paths until an
        existing JPG, JPEG, PNG, or WEBP file is selected, then return its absolute
        path as a string. Relative paths start from this project's folder.
        """

        project_folder = Path(__file__).resolve().parent
        allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}

        # Ask whether the user wants to attach an image.
        while True:
            answer = self._read(
                "Do you have an image to attach? (Y/N): "
            ).strip().lower()

            if answer == "n":
                return "no_image"

            if answer == "y":
                break

            self._write("Invalid input. Please enter Y or N.")

        # If the user selected Y, ask for the image path.
        while True:
            image_path = self._read(
                "Enter the image path "
                "(e.g. test_images/leak.jpg): "
            ).strip().strip("\"'")

            if not image_path:
                self._write("The image path cannot be empty.")
                continue

            path = Path(image_path).expanduser()

            # Resolve relative paths from the folder containing this file.
            if not path.is_absolute():
                path = project_folder / path

            if not path.is_file():
                self._write("File not found. Please check the path.")
                continue

            if path.suffix.lower() not in allowed_extensions:
                self._write("Please select a JPG, JPEG, PNG, or WEBP image.")
                continue

            return str(path.resolve())

    def collect_complaint(self, complaint_id):
        """Ask for complaint details and return the initial six-item list.

        Collect a name, phone number, description, and optional image path.
        Use the supplied complaint ID and generate a local timestamp, then return
        [complaint_id, name, phone_number, description, image_path, date_time].
        """

        self._write("\n--- Submit a Complaint ---")

        # Ask and validate each question before continuing.
        name = self.collect_name()
        phone_number = self.collect_phone_number()
        description = self.get_required_input("What is your complaint? ")
        image_path = self.collect_image_path()

        # Record the submission time using the computer's local timezone.
        date_time = datetime.now().astimezone().isoformat(timespec="seconds")

        # Complaint ID is first; submission date and time are last.
        return [complaint_id, name, phone_number, description, image_path, date_time]

    def show_message(self, message):
        """Print the supplied message or complaint list to the terminal.

        Other managers use this function for user-facing output. Returns None.
        """

        self._write(message)

    def choose_manual_option(self, prompt, options):
        """Return one selected value, or None for the final Go back option."""

        while True:
            self.show_message(prompt)
            for number, value in enumerate(options, 1):
                self.show_message(f"{number}. {value}")
            self.show_message(f"{len(options) + 1}. Go back without approving")
            choice = self._read("Choose an option: ").strip().lower()
            if choice in ("back", str(len(options) + 1)):
                return None
            if choice in [str(number) for number in range(1, len(options) + 1)]:
                return options[int(choice) - 1]
            self.show_message("Invalid choice. Choose an option shown above.")

    def collect_manual_analysis(self, complaint, categories, risks):
        """Collect an admin's classification and explicit approval, or return None.

        Show the original complaint, including its image path. Ask for a readable
        summary, category, observed hazards and common-area risk. Never supply
        default hazard guesses when AI is unavailable. Back cancels the review.
        """

        self.show_reports([complaint])
        self.show_message("Review the original description and any attached image before approving.")
        self.show_message("If details are insufficient, go back and leave the complaint awaiting review.")
        summary = self.get_required_input("Readable issue summary (or 'back' to cancel): ")
        if summary.lower() == "back":
            return None
        category = self.choose_manual_option("Fault category:", categories)
        if category is None:
            return None
        while True:
            self.show_message("Select only hazards supported by the complaint:")
            for number, risk in enumerate(risks, 1):
                self.show_message(f"{number}. {risk.replace('_', ' ')}")
            self.show_message("0. No reported hazards\nback. Go back without approving")
            choice = self._read("Hazard numbers separated by commas: ").strip().lower()
            if choice == "back":
                return None
            if choice == "0":
                selected_risks = []
                break
            choices = [item.strip() for item in choice.split(",")]
            if all(item in [str(number) for number in range(1, len(risks) + 1)] for item in choices):
                selected_risks = list(dict.fromkeys(risks[int(item) - 1] for item in choices))
                break
            self.show_message("Enter valid hazard numbers, 0 for none, or back.")
        shared = self.choose_manual_option("Is there a hazard in a common area?", ["Yes", "No"])
        if shared is None:
            return None
        analysis = {
            "fault_category": category,
            "summary": summary,
            "risk_indicators": selected_risks,
            "common_area_hazard": shared == "Yes",
            "is_unclear": False,
        }
        self.show_message(json.dumps(analysis, indent=2))
        if self.choose_manual_option("Confirm your review:", ["Approve complaint"]) is None:
            return None
        return analysis

    def show_goodbye(self):
        """Print the goodbye message when the user exits.

        Takes no arguments and returns None.
        """

        self._write("Goodbye!")

    def show_reports(self, reports):
        """Display one complaint per table row without changing saved records.

        Wrap long values inside cells. A single report also shows all its
        original fields and analysis details, including the full image path.
        Show an empty-list message when there are no reports. Returns None.
        """

        if not reports:
            self.show_message("\nNo saved reports found.")
            return

        self.show_message("\n--- Saved Reports ---")
        headers = ["ID", "Name", "Phone number", "Description", "Score",
                   "Priority", "Contractor", "Status", "Submitted"]
        widths = [13, 16, 14, 28, 5, 9, 22, 21, 25]
        rows = []
        for report in reports:
            details = report[6] if len(report) > 6 and isinstance(report[6], dict) else {}
            status = details.get("status")
            if not status:
                status = "Pending Action" if details.get("accepted") is True else "Not assessed"
            rows.append([
                report[0], report[1], report[2], report[3],
                details.get("severity_score"), details.get("priority"),
                details.get("contractor"), status, report[5],
            ])
        self._show_table(headers, rows, widths)

        if len(reports) == 1:
            report = reports[0]
            fields = ["ID", "Name", "Phone number", "Description", "Image path", "Submitted"]
            details_rows = list(zip(fields, report[:6]))
            if len(report) > 6 and isinstance(report[6], dict):
                details_rows.extend(
                    (key.replace("_", " ").capitalize(), value)
                    for key, value in report[6].items() if key != "history"
                )
            self.show_message("\nFull complaint details:")
            self._show_table(["Field", "Value"], details_rows, [24, 80])
            self.show_message("Use View complaint history in the reports menu to see activity entries.")
        else:
            self.show_message("View a complaint by ID to see its full image path and analysis details.")

    def _show_table(self, headers, rows, widths):
        """Print bordered rows, wrapping text without truncating stored values."""
        border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
        self.show_message(border)
        for row in [headers, *rows]:
            cells = []
            for value, width in zip(row, widths):
                if value is None or value == "":
                    text = "-"
                elif isinstance(value, bool):
                    text = "Yes" if value else "No"
                elif isinstance(value, (list, dict)):
                    text = json.dumps(value, ensure_ascii=False)
                else:
                    text = str(value)
                # Keep explicit line breaks (for example, alerts) within the cell.
                lines = []
                for line in text.splitlines():
                    lines.extend(wrap(line, width=width) or [""])
                cells.append(lines or [""])
            for line_number in range(max(len(cell) for cell in cells)):
                parts = [
                    (cell[line_number] if line_number < len(cell) else "").ljust(width)
                    for cell, width in zip(cells, widths)
                ]
                self.show_message("| " + " | ".join(parts) + " |")
            self.show_message(border)

    def show_report_menu(self):
        """Return a report action including history/search, with Go back last (1-7).

        Repeat invalid choices. Takes no arguments and does not change reports.
        """

        while True:
            self.show_message(
                "\n1. Update complaint status\n2. View complaint by ID"
                "\n3. Edit complaint\n4. Delete complaint"
                "\n5. View complaint history\n6. Search and filter reports"
                "\n7. Go back to main menu"
            )
            choice = self._read("Choose an option: ").strip()
            if choice in ("1", "2", "3", "4", "5", "6", "7"):
                return choice
            self.show_message("Invalid input. Enter a number from 1 to 7.")

    # New feature: activity uses the same bordered, wrapped table as complaint views.
    def show_report_history(self, report):
        """Show saved activity in order without inventing events for older records."""
        self.show_message(f"\n--- Activity history: {report[0]} ---")
        history = report[6].get("history", [])
        if not history:
            self.show_message("No activity history recorded. Older actions were not tracked.")
            return
        if not isinstance(history, list) or any(not isinstance(entry, dict) for entry in history):
            self.show_message("Unable to display this complaint's invalid history.")
            return
        rows = []
        for number, entry in enumerate(history, 1):
            changes = entry.get("changes", {})
            change_lines = []
            if isinstance(changes, dict):
                for field, values in changes.items():
                    if isinstance(values, dict):
                        old = json.dumps(values.get("old"), ensure_ascii=False)
                        new = json.dumps(values.get("new"), ensure_ascii=False)
                        change_lines.append(f"{field.replace('_', ' ').capitalize()}: {old} -> {new}")
            rows.append([number, entry.get("timestamp"), entry.get("action"),
                         entry.get("actor"), "\n".join(change_lines)])
        self._show_table(["No.", "Time", "Action", "Actor", "Changes"], rows,
                         [4, 25, 20, 10, 70])

    # New feature: combine optional filters; blank inputs mean no restriction.
    def collect_report_filters(self, categories):
        """Return search criteria, or None when back is entered at any prompt."""
        while True:
            self.show_message("\n--- Search and filter reports ---")
            self.show_message("Leave fields blank for all values; type 'back' at any prompt to cancel.")
            query = self._read("Keyword (ID, name, phone, description or summary): ").strip()
            if query.casefold() == "back":
                return None
            criteria = {"query": query}
            choices = [
                ("status", "Status", ["Pending Manual Review", "Pending Action", "Contractor contacted", "Resolved"]),
                ("category", "Category", list(categories)),
                ("priority", "Priority", ["LOW", "MEDIUM", "HIGH", "EMERGENCY"]),
            ]
            for key, label, options in choices:
                value = self._collect_filter_choice(label, options)
                if value is None:
                    return None
                criteria[key] = value
            for key, label in [("date_from", "Submitted from"), ("date_to", "Submitted to")]:
                value = self._collect_filter_date(label)
                if value is None:
                    return None
                criteria[key] = value
            if criteria["date_from"] and criteria["date_to"] and criteria["date_from"] > criteria["date_to"]:
                self.show_message("Start date must not be after end date. Please enter the filters again.")
                continue
            return criteria

    def _collect_filter_choice(self, label, options):
        """Collect a numbered/exact filter value, blank for all, or None for back."""
        self.show_message(label + ": " + "; ".join(f"{n}. {item}" for n, item in enumerate(options, 1)))
        while True:
            answer = self._read(f"{label} (blank = all): ").strip()
            if answer.casefold() == "back":
                return None
            if not answer:
                return ""
            for number, option in enumerate(options, 1):
                if answer == str(number) or answer.casefold() == option.casefold():
                    return option
            self.show_message("Choose a listed number/value, leave blank, or type back.")

    def _collect_filter_date(self, label):
        """Validate one calendar date while allowing blank or cancellation."""
        while True:
            answer = self._read(f"{label} (YYYY-MM-DD, blank = any): ").strip()
            if answer.casefold() == "back":
                return None
            if not answer:
                return ""
            try:
                if date.fromisoformat(answer).isoformat() == answer:
                    return answer
            except ValueError:
                pass
            self.show_message("Enter a valid date in YYYY-MM-DD format, leave blank, or type back.")

    def collect_report_id(self):
        """Return the entered complaint ID, or None to go back to the main menu.

        Accept 'back' or 'go back' to cancel. Repeat blank entries.
        """

        choice = self.get_required_input(
            "Enter complaint_id (e.g. complaint_001), or 'back' to go back to main menu: "
        )
        return None if choice.lower() in ("back", "go back") else choice

    def choose_complaint_status(self):
        """Return the chosen status string, or None for Go back to the main menu.

        Prompt with the three supported statuses and repeat invalid choices.
        """

        statuses = {"1": "Contractor contacted", "2": "Pending Action", "3": "Resolved"}
        while True:
            self.show_message("\n1. Contractor contacted\n2. Pending Action\n3. Resolved\n4. Go back")
            choice = self._read("Choose a status: ").strip()
            if choice == "4":
                return None
            if choice in statuses:
                return statuses[choice]
            self.show_message("Invalid input. Enter 1, 2, 3, or 4.")

    def collect_report_edits(self, report):
        """Return an edited copy on Save, or None on Go back without saving.

        Allow name, phone, description, and image edits using existing validators.
        Preserve ID, date, and processing details for the workflow to handle.
        Selecting image and answering N removes the existing attachment.
        """

        draft = deepcopy(report)
        while True:
            self.show_reports([draft])
            self.show_message(
                "\n1. Edit name\n2. Edit phone number\n3. Edit description"
                "\n4. Replace or remove image\n5. Save changes\n6. Go back without saving"
            )
            choice = self._read("Choose an option: ").strip()
            if choice == "1":
                draft[1] = self.collect_name()
            elif choice == "2":
                draft[2] = self.collect_phone_number()
            elif choice == "3":
                draft[3] = self.get_required_input("Enter the updated complaint: ")
            elif choice == "4":
                draft[4] = self.collect_image_path()
            elif choice == "5":
                return draft
            elif choice == "6":
                return None
            else:
                self.show_message("Invalid input. Enter a number from 1 to 6.")

    def confirm_report_deletion(self, report):
        """Show the selected report and return True only for an explicit Y.

        N or back cancels deletion. Repeat other responses without changing data.
        """

        self.show_reports([report])
        while True:
            answer = self._read(f"Delete complaint {report[0]} permanently? (Y/N): ").strip().lower()
            if answer == "y":
                return True
            if answer in ("n", "back", "go back"):
                return False
            self.show_message("Invalid input. Enter Y or N.")
