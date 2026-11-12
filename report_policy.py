"""Validation of the existing JSON record format, without file access."""


class ReportPolicy:
    """Recognise accepted and pending records without mutating them."""

    def is_accepted_report(self, report):
        """Check that a seven-item report has accepted, clear processing details."""

        return (
            isinstance(report, list)
            and len(report) == 7
            and isinstance(report[6], dict)
            and report[6].get("accepted") is True
            and report[6].get("is_unclear") is False
        )

    def is_pending_review(self, report):
        """Check that a saved complaint is explicitly awaiting manual classification."""

        return (
            isinstance(report, list) and len(report) == 7
            and isinstance(report[6], dict)
            and report[6].get("accepted") is False
            and report[6].get("manual_input_required") is True
            and report[6].get("status") == "Pending Manual Review"
        )