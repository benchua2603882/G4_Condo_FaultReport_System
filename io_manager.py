from datetime import datetime
from pathlib import Path
import json
from getpass import getpass

def show_menu(role="resident"):
    """Return a menu choice allowed for the authenticated session role.

    Residents can submit only; admins can also view/manage reports. Return
    back to sign out or quit to exit, and repeat all invalid choices.
    """

    while True:
        print("\n========================================")
        print(f"Condo Fault Reporting System - {role.title()}")
        print("========================================")
        print("1. Submit a complaint")
        if role == "admin":
            print("2. View reports")
        print("Type 'back' to return to the welcome screen, or 'quit' to exit.")

        choice = input("Choose an option: ").strip().lower()

        allowed_choices = ("1", "2", "back", "quit") if role == "admin" else ("1", "back", "quit")
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