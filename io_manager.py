








def show_menu(role="resident"):
    """Return a menu choice allowed for the authenticated session role.

    Residents can submit only; admins can also view/manage reports. Return
    back to sign out or quit to exit, and repeat all invalid choices.
    """

    while True:
        print(f"\nHDB Fault Reporting System - {role.title()}")
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

    print("Goodbye!")