from datetime import datetime
from pathlib import Path
import json
from getpass import getpass
from copy import deepcopy
from textwrap import wrap
from abc import ABC, abstractmethod

# --------------------------------------------------------------------------
# Interface: how the program talks to the outside world
# --------------------------------------------------------------------------
class IOChannel(ABC):
    """Contract for any input/output device (console, GUI, test double)."""

    @abstractmethod
    def read(self, prompt=""):
        """Return one line of text typed by the user."""

    @abstractmethod
    def read_secret(self, prompt=""):
        """Return text typed by the user without echoing it."""

    @abstractmethod
    def write(self, message=""):
        """Show a message to the user."""


class ConsoleChannel(IOChannel):
    """Terminal implementation. Looks up input/print at call time so that
    unittest.mock.patch("builtins.input") still works."""

    def read(self, prompt=""):
        return input(prompt)

    def read_secret(self, prompt=""):
        return getpass(prompt)

    def write(self, message=""):
        print(message)

# --------------------------------------------------------------------------
# Abstract validator + concrete validators (inheritance + polymorphism)
# --------------------------------------------------------------------------
class InputValidator(ABC):
    """Base class: turn raw text into clean text, or raise ValueError."""

    def __init__(self, error_message):
        self._error_message = error_message

    @property
    def error_message(self):
        return self._error_message

    def clean(self, raw):
        """Template method: trim, then let the subclass accept or reject."""
        value = raw.strip()
        if not self._is_valid(value):
            raise ValueError(self._error_message)
        return self._transform(value)

    @abstractmethod
    def _is_valid(self, value):
        """Return True if the trimmed value is acceptable."""

    def _transform(self, value):
        """Hook: subclasses may change the accepted value. Default keeps it."""
        return value


class NameValidator(InputValidator):
    def __init__(self):
        super().__init__("Invalid name. Enter letters and spaces only.")

    def _is_valid(self, value):
        return value.replace(" ", "").isalpha()


class PhoneValidator(InputValidator):
    def __init__(self):
        super().__init__(
            "Invalid phone number. Enter digits only, "
            "with an optional '+' at the beginning."
        )

    def _is_valid(self, value):
        # Remove a leading '+' only for checking; the stored text keeps it.
        digits = value.removeprefix("+")
        return digits.isascii() and digits.isdecimal()


class RequiredTextValidator(InputValidator):
    def __init__(self):
        super().__init__("This field cannot be empty. Please try again.")

    def _is_valid(self, value):
        return bool(value)

# --------------------------------------------------------------------------
# Prompting helpers
# --------------------------------------------------------------------------
class ValidatedPrompter:
    """Asks a question until a validator accepts the answer."""

    def __init__(self, channel):
        self._channel = channel

    def ask(self, prompt, validator):
        while True:
            try:
                return validator.clean(self._channel.read(prompt))
            except ValueError as error:
                self._channel.write(str(error))

    def ask_choice(self, prompt, allowed, error_message, lowercase=False):
        """Ask until the answer is one of `allowed`; return it."""
        while True:
            choice = self._channel.read(prompt).strip()
            if lowercase:
                choice = choice.lower()
            if choice in allowed:
                return choice
            self._channel.write(error_message)


class ImagePathCollector:
    """Asks about an optional image and validates the file path."""

    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    NO_IMAGE = "no_image"

    def __init__(self, channel, project_folder=None):
        self._channel = channel
        self._project_folder = project_folder or Path(__file__).resolve().parent

    def collect(self):
        while True:
            answer = self._channel.read(
                "Do you have an image to attach? (Y/N): "
            ).strip().lower()
            if answer == "n":
                return self.NO_IMAGE
            if answer == "y":
                break
            self._channel.write("Invalid input. Please enter Y or N.")

        while True:
            image_path = self._channel.read(
                "Enter the image path (e.g. test_images/leak.jpg): "
            ).strip().strip("\"'")
            if not image_path:
                self._channel.write("The image path cannot be empty.")
                continue
            path = Path(image_path).expanduser()
            if not path.is_absolute():
                path = self._project_folder / path
            if not path.is_file():
                self._channel.write("File not found. Please check the path.")
                continue
            if path.suffix.lower() not in self.ALLOWED_EXTENSIONS:
                self._channel.write("Please select a JPG, JPEG, PNG, or WEBP image.")
                continue
            return str(path.resolve())

# --------------------------------------------------------------------------
# Abstract menu + role-specific menus (polymorphism, no if/else on role)
# --------------------------------------------------------------------------
class Menu(ABC):
    """A role's menu: what it shows and which answers it accepts."""

    @property
    @abstractmethod
    def option_lines(self):
        """Numbered lines shown to the user."""

    @property
    @abstractmethod
    def allowed_choices(self):
        """Answers this role may type."""

    def notification_lines(self, pending_count=None):
        """Extra lines shown above the options. Default: none."""
        return []


class ResidentMenu(Menu):
    @property
    def option_lines(self):
        return ["1. Submit a complaint"]

    @property
    def allowed_choices(self):
        return ("1", "back", "quit")


class AdminMenu(ResidentMenu):
    """An admin can do everything a resident can, plus two more options."""

    @property
    def option_lines(self):
        return super().option_lines + [
            "2. View reports",
            "3. Review complaints awaiting approval",
        ]

    @property
    def allowed_choices(self):
        return ("1", "2", "3", "back", "quit")
    
    def notification_lines(self, pending_count=None):
        if pending_count:  # None and 0 show nothing
            return [f"NOTICE: {pending_count} complaint(s) pending manual review."]
        return []

class MenuRegistry:
    """Finds the right Menu for a role. New role = new entry (open/closed)."""

    def __init__(self):
        self._menus = {"resident": ResidentMenu(), "admin": AdminMenu()}

    def for_role(self, role):
        # Unknown roles get the safest (smallest) menu.
        return self._menus.get(role, self._menus["resident"])

# --------------------------------------------------------------------------
# Report display
# --------------------------------------------------------------------------
class ReportFormatter:
    """Turns saved report lists into bordered Field / Value table lines.
    It only builds text; it never prints and never changes a report."""

    LABELS = ["Complaint ID", "Name", "Phone number",
              "Description", "Image path", "Submitted at"]
    VALUE_WIDTH = 52

    def format(self, report):
        rows = list(zip(self.LABELS, report[:6]))
        if len(report) > 6 and isinstance(report[6], dict):
            for key, value in report[6].items():
                rows.append((key.replace("_", " ").capitalize(), value))

        field_width = max([len("Field")] + [len(label) for label, _ in rows])
        border = ("+-" + "-" * field_width + "-+-"
                  + "-" * self.VALUE_WIDTH + "-+")
        lines = [border,
                 f"| {'Field':<{field_width}} | {'Value':<{self.VALUE_WIDTH}} |",
                 border]
        for label, value in rows:
            for index, line in enumerate(self._wrap(self._to_text(value))):
                field = label if index == 0 else ""
                lines.append(
                    f"| {field:<{field_width}} | {line:<{self.VALUE_WIDTH}} |"
                )
        lines.append(border)
        return lines

    @staticmethod
    def _to_text(value):
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value) or "None"
        if value is None:
            return "N/A"
        return str(value)

    def _wrap(self, text):
        lines = []
        for paragraph in text.splitlines() or [""]:
            lines.extend(wrap(paragraph, width=self.VALUE_WIDTH) or [""])
        return lines

# --------------------------------------------------------------------------
# The IO Manager (facade used by main.py)
# --------------------------------------------------------------------------
class IOManager:
    """All terminal input/output for the condo fault reporting system."""

    HAZARD_NONE_TEXT = "0. No reported hazards\nback. Go back without approving"

    def __init__(self, channel=None):
        # Aggregation: the channel is supplied from outside and can be reused.
        self._channel = channel if channel is not None else ConsoleChannel()
        # Composition: these helpers are created and owned by this manager.
        self._prompter = ValidatedPrompter(self._channel)
        self._formatter = ReportFormatter()
        self._menus = MenuRegistry()
        self._images = ImagePathCollector(self._channel)
        self._name_validator = NameValidator()
        self._phone_validator = PhoneValidator()
        self._required_validator = RequiredTextValidator()

    # ----- simple output ---------------------------------------------------
    def show_message(self, message):
        self._channel.write(message)

    def show_goodbye(self):
        self._channel.write("\nGoodbye!")

    # ----- menus -----------------------------------------------------------
    def show_welcome(self):
        while True:
            self._channel.write("\nWelcome to the Condo Fault Reporting System")
            self._channel.write("1. Resident")
            self._channel.write("2. Admin")
            self._channel.write("Type 'quit' to exit.")
            choice = self._channel.read("Are you a resident or admin? ").strip().lower()
            if choice in ("1", "2", "quit"):
                return choice
            self._channel.write("Invalid input. Enter 1, 2, or quit.")

    def show_menu(self, role="resident", pending_count=None):
        menu = self._menus.for_role(role)
        while True:
            self._channel.write("\n========================================")
            self._channel.write(f"Condo Fault Reporting System - {role.title()}")
            self._channel.write("========================================")
            for line in menu.notification_lines(pending_count):
                self._channel.write(line)
            for line in menu.option_lines:
                self._channel.write(line)
            self._channel.write(
                "Type 'back' to return to the welcome screen, or 'quit' to exit."
            )
            choice = self._channel.read("Choose an option: ").strip().lower()
            if choice in menu.allowed_choices:
                return choice
            self._channel.write("Invalid input. Choose an option shown in your menu.")

    def show_report_menu(self):
        while True:
            self.show_message(
                "\n1. Update complaint status\n2. View complaint by ID"
                "\n3. Edit complaint\n4. Delete complaint\n5. Go back to main menu"
            )
            choice = self._channel.read("Choose an option: ").strip()
            if choice in ("1", "2", "3", "4", "5"):
                return choice
            self.show_message("Invalid input. Enter 1, 2, 3, 4, or 5.")

    # ----- field collection ------------------------------------------------
    def collect_name(self):
        return self._prompter.ask("What is your name? ", self._name_validator)

    def collect_phone_number(self):
        return self._prompter.ask("What is your phone number? ", self._phone_validator)

    def get_required_input(self, prompt):
        return self._prompter.ask(prompt, self._required_validator)

    def collect_image_path(self):
        return self._images.collect()

    def collect_complaint(self, complaint_id):
        """Return [complaint_id, name, phone, description, image_path, date_time]."""
        self.show_message("\n--- Submit a Complaint ---")
        name = self.collect_name()
        phone_number = self.collect_phone_number()
        description = self.get_required_input("What is your complaint? ")
        image_path = self.collect_image_path()
        date_time = datetime.now().astimezone().isoformat(timespec="seconds")
        return [complaint_id, name, phone_number, description, image_path, date_time]

    def collect_admin_credentials(self):
        """Return (username, password), or None if the admin types 'back'."""
        username = self._channel.read("Admin username (or 'back' to cancel): ").strip()
        if username.lower() == "back":
            return None
        password = self._channel.read_secret("Admin password: ")
        return username, password

    # ----- report display --------------------------------------------------
    def show_reports(self, reports):
        if not reports:
            self.show_message("\nNo saved reports found.")
            return
        self.show_message("\n--- Saved Reports ---")
        for number, report in enumerate(reports, start=1):
            self.show_message(f"\nReport {number}:")
            for line in self._formatter.format(report):
                self.show_message(line)

    # ----- admin report actions -------------------------------------------
    def collect_report_id(self):
        choice = self.get_required_input(
            "Enter complaint_id (e.g. complaint_001), or 'back' to go back to main menu: "
        )
        return None if choice.lower() in ("back", "go back") else choice

    def choose_complaint_status(self):
        statuses = {"1": "Contractor contacted", "2": "Pending Action", "3": "Resolved"}
        while True:
            self.show_message(
                "\n1. Contractor contacted\n2. Pending Action\n3. Resolved\n4. Go back"
            )
            choice = self._channel.read("Choose a status: ").strip()
            if choice == "4":
                return None
            if choice in statuses:
                return statuses[choice]
            self.show_message("Invalid input. Enter 1, 2, 3, or 4.")

    def collect_report_edits(self, report):
        """Return an edited copy on Save, or None on Go back."""
        draft = deepcopy(report)
        while True:
            self.show_reports([draft])
            self.show_message(
                "\n1. Edit name\n2. Edit phone number\n3. Edit description"
                "\n4. Replace or remove image\n5. Save changes\n6. Go back without saving"
            )
            choice = self._channel.read("Choose an option: ").strip()
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
        self.show_reports([report])
        while True:
            answer = self._channel.read(
                f"Delete complaint {report[0]} permanently? (Y/N): "
            ).strip().lower()
            if answer == "y":
                return True
            if answer in ("n", "back", "go back"):
                return False
            self.show_message("Invalid input. Enter Y or N.")

    # ----- manual review (used when AI is unavailable) ---------------------
    def choose_manual_option(self, prompt, options):
        """Return the chosen value, or None for the final Go back option."""
        valid_numbers = [str(n) for n in range(1, len(options) + 1)]
        while True:
            self.show_message(prompt)
            for number, value in enumerate(options, 1):
                self.show_message(f"{number}. {value}")
            self.show_message(f"{len(options) + 1}. Go back without approving")
            choice = self._channel.read("Choose an option: ").strip().lower()
            if choice in ("back", str(len(options) + 1)):
                return None
            if choice in valid_numbers:
                return options[int(choice) - 1]
            self.show_message("Invalid choice. Choose an option shown above.")

    def _collect_hazards(self, risks):
        """Return a list of chosen hazards, or None to cancel."""
        valid_numbers = [str(n) for n in range(1, len(risks) + 1)]
        while True:
            self.show_message("Select only hazards supported by the complaint:")
            for number, risk in enumerate(risks, 1):
                self.show_message(f"{number}. {risk.replace('_', ' ')}")
            self.show_message(self.HAZARD_NONE_TEXT)
            choice = self._channel.read("Hazard numbers separated by commas: ").strip().lower()
            if choice == "back":
                return None
            if choice == "0":
                return []
            picks = [item.strip() for item in choice.split(",")]
            if all(item in valid_numbers for item in picks):
                return list(dict.fromkeys(risks[int(item) - 1] for item in picks))
            self.show_message("Enter valid hazard numbers, 0 for none, or back.")

    def collect_manual_analysis(self, complaint, categories, risks):
        """Return the admin's approved analysis dict, or None if cancelled."""
        self.show_reports([complaint])
        self.show_message(
            "Review the original description and any attached image before approving."
        )
        self.show_message(
            "If details are insufficient, go back and leave the complaint awaiting review."
        )
        summary = self.get_required_input("Readable issue summary (or 'back' to cancel): ")
        if summary.lower() == "back":
            return None
        category = self.choose_manual_option("Fault category:", categories)
        if category is None:
            return None
        selected_risks = self._collect_hazards(risks)
        if selected_risks is None:
            return None
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

# --------------------------------------------------------------------------
# Backward-compatible entry points.
# main.py and the existing tests still call io_manager.<function>(...).
# Each one only forwards to the single IOManager object above.
# --------------------------------------------------------------------------
_manager = IOManager()

def show_menu(role="resident", pending_count=None): return _manager.show_menu(role, pending_count)
def show_message(message): return _manager.show_message(message)
def show_goodbye(): return _manager.show_goodbye()
def collect_name(): return _manager.collect_name()
def collect_phone_number(): return _manager.collect_phone_number()
def get_required_input(prompt): return _manager.get_required_input(prompt)
def collect_image_path(): return _manager.collect_image_path()
def collect_complaint(complaint_id): return _manager.collect_complaint(complaint_id)
def show_reports(reports): return _manager.show_reports(reports)
def show_welcome(): return _manager.show_welcome()
def collect_admin_credentials(): return _manager.collect_admin_credentials()
def show_report_menu(): return _manager.show_report_menu()
def collect_report_id(): return _manager.collect_report_id()
def choose_complaint_status(): return _manager.choose_complaint_status()
def collect_report_edits(report): return _manager.collect_report_edits(report)
def confirm_report_deletion(report): return _manager.confirm_report_deletion(report)
def choose_manual_option(prompt, options): return _manager.choose_manual_option(prompt, options)
def collect_manual_analysis(complaint, categories, risks):
    return _manager.collect_manual_analysis(complaint, categories, risks)