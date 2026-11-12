"""Create and start the Condo application."""

from ai_manager import AIManager
from application import ReportApplication
from authentication import DemoAuthenticator
from data_manager import DEFAULT_REPORTS_FILE, JsonReportRepository
from io_manager import IOManager
from logic_manager import LogicManager


class ApplicationFactory:
    """Create the managers and connect them to the application."""

    @staticmethod
    def create(reports_file=DEFAULT_REPORTS_FILE):
        """Return an application with all its required managers."""
        return ReportApplication(
            io=IOManager(),
            ai=AIManager(),
            logic=LogicManager(),
            data=JsonReportRepository(reports_file),
            authenticator=DemoAuthenticator(),
        )


if __name__ == "__main__":
    ApplicationFactory.create().run()