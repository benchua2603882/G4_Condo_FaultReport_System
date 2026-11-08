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

    
