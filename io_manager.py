
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
