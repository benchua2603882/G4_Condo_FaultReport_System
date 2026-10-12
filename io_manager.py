from datetime import datetime
from pathlib import Path
import json
from getpass import getpass
from copy import deepcopy

def show_menu(role="resident"):
    """Return a menu choice allowed for the current role.

    Residents can submit complaints. Admins can also manage reports
    and review pending complaints. Back signs out; quit exits.
    Repeat invalid choices.
    """

    while True:
        print("\n========================================")
        print(f"Condo Fault Reporting System - {role.title()}")
        print("========================================")
        print("1. Submit a complaint")

        if role == "admin":
            print("2. View reports")
            print("3. Review complaints awaiting approval")

        print("Type 'back' to return to the welcome screen, or 'quit' to exit.")

        choice = input("Choose an option: ").strip().lower()

        allowed_choices = (
            ("1", "2", "3", "back", "quit")
            if role == "admin"
            else ("1", "back", "quit")
        )

        if choice in allowed_choices:
            return choice

        print("Invalid input. Choose an option shown in your menu.")

def show_message(message):
    """Print the supplied message or complaint list to the terminal.

    Other managers use this function for user-facing output. Returns None.
    """

    print(message)

def show_goodbye():
    """Print the goodbye message when the user exits.

    Takes no arguments and returns None.
    """

    print("\nGoodbye!")

def collect_name():
    """Ask for the resident's name and return it as a trimmed string.

    Repeat the question if the name is empty or contains anything other
    than letters and spaces. No arguments are needed.
    """

    while True:
        name = input("What is your name? ").strip()

        if name.replace(" ", "").isalpha():
            return name

        print("Invalid name. Enter letters and spaces only.")

def collect_phone_number():
    """Ask for a phone number and return the validated text.

    Accept digits with an optional single '+' at the beginning. Repeat
    invalid entries and keep any leading '+' or zeros in the returned string.
    """

    while True:
        phone_number = input("What is your phone number? ").strip()

        # Remove a leading '+' only for checking.
        # Keep the original input for storage.
        digits = phone_number.removeprefix("+")
        if digits.isascii() and digits.isdecimal():
            return phone_number

        print(
            "Invalid phone number. Enter digits only, "
            "with an optional '+' at the beginning."
        )

def get_required_input(prompt):
    """Display the supplied prompt and return a nonempty, trimmed answer.

    The prompt argument is the question shown to the user. Blank answers
    cause the same question to be asked again.
    """

    while True:
        answer = input(prompt).strip()

        if answer:
            return answer

        print("This field cannot be empty. Please try again.")


def collect_image_path():
    """Ask whether to attach an image and validate the user's file path.

    Return 'no_image' if declined. Otherwise, repeat invalid paths until an
    existing JPG, JPEG, PNG, or WEBP file is selected, then return its absolute
    path as a string. Relative paths start from this project's folder.
    """

    project_folder = Path(__file__).resolve().parent
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}

    # Ask whether the user wants to attach an image.
    while True:
        answer = input(
            "Do you have an image to attach? (Y/N): "
        ).strip().lower()

        if answer == "n":
            return "no_image"

        if answer == "y":
            break

        print("Invalid input. Please enter Y or N.")

    # If the user selected Y, ask for the image path.
    while True:
        image_path = input(
            "Enter the image path "
            "(e.g. test_images/leak.jpg): "
        ).strip().strip("\"'")

        if not image_path:
            print("The image path cannot be empty.")
            continue

        path = Path(image_path).expanduser()

        # Resolve relative paths from the folder containing this file.
        if not path.is_absolute():
            path = project_folder / path

        if not path.is_file():
            print("File not found. Please check the path.")
            continue

        if path.suffix.lower() not in allowed_extensions:
            print("Please select a JPG, JPEG, PNG, or WEBP image.")
            continue

        return str(path.resolve())


def collect_complaint(complaint_id):
    """Ask for complaint details and return the initial six-item list.

    Collect a name, phone number, description, and optional image path.
    Use the supplied complaint ID and generate a local timestamp, then return
    [complaint_id, name, phone_number, description, image_path, date_time].
    """

    print("\n--- Submit a Complaint ---")

    # Ask and validate each question before continuing.
    name = collect_name()
    phone_number = collect_phone_number()
    description = get_required_input("What is your complaint? ")
    image_path = collect_image_path()

    # Record the submission time using the computer's local timezone.
    date_time = datetime.now().astimezone().isoformat(timespec="seconds")

    # Complaint ID is first; submission date and time are last.
    return [complaint_id, name, phone_number, description, image_path, date_time]

def show_reports(reports):
    """Display the supplied list of saved reports with numbered entries.

    Format each report as indented JSON. Show an empty-list message when
    there are no reports. Returns None and does not change the records.
    """

    if not reports:
        show_message("\nNo saved reports found.")
        return

    show_message("\n--- Saved Reports ---")
    for number, report in enumerate(reports, start=1):
        show_message(f"\nReport {number}:")
        show_message(json.dumps(report, indent=2, ensure_ascii=False))

def show_welcome():
    """Ask whether the user is a resident or admin; return '1', '2', or 'quit'.

    Repeat invalid choices. Selecting Admin still requires a successful login.
    """

    while True:
        print("\nWelcome to the Condo Fault Reporting System")
        print("1. Resident")
        print("2. Admin")
        print("Type 'quit' to exit.")
        choice = input("Are you a resident or admin? ").strip().lower()
        if choice in ("1", "2", "quit"):
            return choice
        print("Invalid input. Enter 1, 2, or quit.")

def collect_admin_credentials():
    """Return the entered username and password, or None to cancel login.

    Hide password entry in an interactive terminal. Type back at the username
    prompt to return to the welcome screen. Authentication happens in logic.
    """

    username = input("Admin username (or 'back' to cancel): ").strip()
    if username.lower() == "back":
        return None
    password = getpass("Admin password: ")
    return username, password

def show_report_menu():
    """Return a report action: status, view one, edit, delete, or back (1-5).

    Repeat invalid choices. Takes no arguments and does not change reports.
    """

    while True:
        show_message(
            "\n1. Update complaint status\n2. View complaint by ID"
            "\n3. Edit complaint\n4. Delete complaint\n5. Go back to main menu"
        )
        choice = input("Choose an option: ").strip()
        if choice in ("1", "2", "3", "4", "5"):
            return choice
        show_message("Invalid input. Enter 1, 2, 3, 4, or 5.")

def collect_report_id():
    """Return the entered complaint ID, or None to go back to the main menu.

    Accept 'back' or 'go back' to cancel. Repeat blank entries.
    """

    choice = get_required_input(
        "Enter complaint_id (e.g. complaint_001), or 'back' to go back to main menu: "
    )
    return None if choice.lower() in ("back", "go back") else choice

def choose_complaint_status():
    """Return the chosen status string, or None for Go back to the main menu.

    Prompt with the three supported statuses and repeat invalid choices.
    """

    statuses = {"1": "Contractor contacted", "2": "Pending Action", "3": "Resolved"}
    while True:
        show_message("\n1. Contractor contacted\n2. Pending Action\n3. Resolved\n4. Go back")
        choice = input("Choose a status: ").strip()
        if choice == "4":
            return None
        if choice in statuses:
            return statuses[choice]
        show_message("Invalid input. Enter 1, 2, 3, or 4.")

def choose_complaint_status():
    """Return the chosen status string, or None for Go back to the main menu.

    Prompt with the three supported statuses and repeat invalid choices.
    """

    statuses = {"1": "Contractor contacted", "2": "Pending Action", "3": "Resolved"}
    while True:
        show_message("\n1. Contractor contacted\n2. Pending Action\n3. Resolved\n4. Go back")
        choice = input("Choose a status: ").strip()
        if choice == "4":
            return None
        if choice in statuses:
            return statuses[choice]
        show_message("Invalid input. Enter 1, 2, 3, or 4.")

        
def collect_report_edits(report):
    """Return an edited copy on Save, or None on Go back without saving.
    Allow name, phone, description, and image edits using existing validators.
    Preserve ID, date, and processing details for the workflow to handle.
    Selecting image and answering N removes the existing attachment.
    """

    draft = deepcopy(report)
    while True:
        show_reports([draft])
        show_message(
            "\n1. Edit name\n2. Edit phone number\n3. Edit description"
            "\n4. Replace or remove image\n5. Save changes\n6. Go back without saving"
        )
        choice = input("Choose an option: ").strip()
        if choice == "1":
            draft[1] = collect_name()
        elif choice == "2":
            draft[2] = collect_phone_number()
        elif choice == "3":
            draft[3] = get_required_input("Enter the updated complaint: ")
        elif choice == "4":
            draft[4] = collect_image_path()
        elif choice == "5":
            return draft
        elif choice == "6":
            return None
        else:
            show_message("Invalid input. Enter a number from 1 to 6.")

def confirm_report_deletion(report):
    """Show the selected report and return True only for an explicit Y.

    N or back cancels deletion. Repeat other responses without changing data.
    """

    show_reports([report])
    while True:
        answer = input(f"Delete complaint {report[0]} permanently? (Y/N): ").strip().lower()
        if answer == "y":
            return True
        if answer in ("n", "back", "go back"):
            return False
        show_message("Invalid input. Enter Y or N.")

def choose_manual_option(prompt, options):
    """Return one selected value, or None for the final Go back option."""

    while True:
        show_message(prompt)
        for number, value in enumerate(options, 1):
            show_message(f"{number}. {value}")
        show_message(f"{len(options) + 1}. Go back without approving")
        choice = input("Choose an option: ").strip().lower()
        if choice in ("back", str(len(options) + 1)):
            return None
        if choice in [str(number) for number in range(1, len(options) + 1)]:
            return options[int(choice) - 1]
        show_message("Invalid choice. Choose an option shown above.")


def collect_manual_analysis(complaint, categories, risks):
    """Collect an admin's classification and explicit approval, or return None.

    Show the original complaint, including its image path. Ask for a readable
    summary, category, observed hazards and common-area risk. Never supply
    default hazard guesses when AI is unavailable. Back cancels the review.
    """

    show_reports([complaint])
    show_message("Review the original description and any attached image before approving.")
    show_message("If details are insufficient, go back and leave the complaint awaiting review.")
    summary = get_required_input("Readable issue summary (or 'back' to cancel): ")
    if summary.lower() == "back":
        return None
    category = choose_manual_option("Fault category:", categories)
    if category is None:
        return None
    while True:
        show_message("Select only hazards supported by the complaint:")
        for number, risk in enumerate(risks, 1):
            show_message(f"{number}. {risk.replace('_', ' ')}")
        show_message("0. No reported hazards\nback. Go back without approving")
        choice = input("Hazard numbers separated by commas: ").strip().lower()
        if choice == "back":
            return None
        if choice == "0":
            selected_risks = []
            break
        choices = [item.strip() for item in choice.split(",")]
        if all(item in [str(number) for number in range(1, len(risks) + 1)] for item in choices):
            selected_risks = list(dict.fromkeys(risks[int(item) - 1] for item in choices))
            break
        show_message("Enter valid hazard numbers, 0 for none, or back.")
    shared = choose_manual_option("Is there a hazard in a common area?", ["Yes", "No"])
    if shared is None:
        return None
    analysis = {
        "fault_category": category,
        "summary": summary,
        "risk_indicators": selected_risks,
        "common_area_hazard": shared == "Yes",
        "is_unclear": False,
    }
    show_message(json.dumps(analysis, indent=2))
    if choose_manual_option("Confirm your review:", ["Approve complaint"]) is None:
        return None
    return analysis