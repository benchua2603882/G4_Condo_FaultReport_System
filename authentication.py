# Provisional demo account: replace with real credential handling later.
DEMO_ADMIN_USERNAME = "admin123"
DEMO_ADMIN_PASSWORD = "password123"


class DemoAuthenticator:
    """Checks admin logins against a demo account."""

    def __init__(self, username=DEMO_ADMIN_USERNAME, password=DEMO_ADMIN_PASSWORD):
        """Store the one accepted username and password.

        Defaults to the demo account. Pass other values to use a different one.
        """

        self.username = username
        self.password = password

    def authenticate_admin(self, username, password):
        """Return True when both values match the stored demo account.

        Accept username and password strings.
        """

        return username == self.username and password == self.password