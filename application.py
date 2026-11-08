"""Complaint submission workflows using injected manager objects."""
from contracts import Analyzer, Authenticator, FaultProcessor, ReportRepository, UserInterface


class ReportApplication:
    """Coordinate complaint submission through the I/O, AI, logic and data managers."""

    def __init__(self, io: UserInterface, ai: Analyzer, logic: FaultProcessor,
                 data: ReportRepository, authenticator: Authenticator):
        """Associate injected managers with this app without constructing them."""
        self._io = io
        self._ai = ai
        self._logic = logic
        self._data = data
        self._authenticator = authenticator

    def analyze_report(self, complaint):
        """Run AI and rules; return accepted details or a manual-review marker."""

        ai_result = self._ai.analyze_complaint(complaint)
        processed = self._logic.process_fault(ai_result)
        if processed["accepted"]:
            processed["status"] = "Pending Action"
        # Emergency instructions must be visible even if a later save fails.
        if processed.get("emergency_action"):
            self._io.show_message(processed["emergency_action"])
        return processed

    def process_new_report(self):
        """Run one complaint through the I/O, AI, logic, and data managers.

        Collect input and return the saved seven-item record. AI failures go to
        reports.json as Pending Manual Review; accepted reports use Pending Action.
        Return None for unclear reports, unexpected processing errors or failed writes.
        """

        try:
            complaint_id = self._data.get_next_complaint_id()
        except (OSError, ValueError) as error:
            self._io.show_message(f"Unable to generate complaint ID: {error}")
            return None

        complaint = self._io.collect_complaint(complaint_id)

        self._io.show_message("\nComplaint details collected:")
        self._io.show_message(complaint)

        self._io.show_message("\nSending complaint to Gemini for analysis...")
        try:
            processed = self.analyze_report(complaint)
        except Exception as error:
            # Report the failure and let the user return to the menu.
            self._io.show_message(f"AI analysis failed: {error}")
            self._io.show_message("Complaint not saved. Please try again.")
            return None

        if processed.get("manual_input_required"):
            report = complaint + [processed]
            try:
                self._data.save_report(report)
            except (OSError, ValueError) as error:
                self._io.show_message(f"Unable to save complaint for review: {error}")
                return None
            self._io.show_message(
                f"Complaint {complaint[0]} saved with status Pending Manual Review because AI analysis is unavailable."
            )
            return report

        if not processed["accepted"]:
            self._io.show_message(processed["reason"])
            self._io.show_message("Complaint not saved.")
            return None

        # Preserve the original six fields and append the AI/logic results.
        complaint.append(processed)
        try:
            self._data.save_report(complaint)
        except (OSError, ValueError) as error:
            self._io.show_message(f"Unable to save complaint: {error}")
            return None

        self._io.show_message(f"\nComplaint {complaint[0]} saved successfully.")
        self._io.show_message(processed["alert"])

        return complaint
