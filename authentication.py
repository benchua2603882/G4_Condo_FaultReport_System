"""The existing demonstration account, separated from fault scoring."""


class DemoAuthenticator:
    """Encapsulate the demo credentials and compare both supplied values."""

    def __init__(self, username="admin123", password="password123"):
        """Retain the Part 1 demo login; this is not production authentication."""
        self._username = username
        self._password = password

    def authenticate_admin(self, username, password):
        """Return True only when both credentials match this account."""
        return username == self._username and password == self._password