"""Complaint submission workflows using manager objects."""
import logging
from pathlib import Path
from contracts import Analyzer, Authenticator, FaultProcessor, ReportRepository, UserInterface


class ReportApplication:
    """Coordinate complaint submission through the I/O, AI, logic and data managers."""

    def __init__(self, io: UserInterface, ai: Analyzer, logic: FaultProcessor,
                 data: ReportRepository, authenticator: Authenticator):
        """Associate  managers with this app without constructing them."""
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

    def process_new_report(self, role="resident"):
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
                report = self._data.save_report(report, actor=role.title())
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
            complaint = self._data.save_report(complaint, actor=role.title())
        except (OSError, ValueError) as error:
            self._io.show_message(f"Unable to save complaint: {error}")
            return None

        self._io.show_message(f"\nComplaint {complaint[0]} saved successfully.")
        self._io.show_message(processed["alert"])

        return complaint


    def pending_review_count(self):
        """New feature: reload the admin notification count; None means unavailable."""
        try:
            return len(self._data.load_pending_reviews())
        except (OSError, ValueError) as error:
            self._io.show_message(f"Unable to check pending reviews: {error}")
            return None

    def select_report(self, reports):
        """Prompt for an existing report ID and load its current saved record.

        Retry IDs missing from the supplied list. Return None on Go back or
        storage errors. Reload the selected record before editing or deleting it.
        """

        while True:
            complaint_id = self._io.collect_report_id()
            if complaint_id is None:
                return None
            try:
                self._data.find_report_index(reports, complaint_id)
            except ValueError:
                self._io.show_message("Complaint ID not found. Please try again.")
                continue
            try:
                return self._data.get_report(complaint_id)
            except (OSError, ValueError) as error:
                self._io.show_message(f"Unable to load complaint: {error}")
                return None

    def view_reports(self):
        """Display saved reports and offer CRUD, history and search actions.

        Reload after each update. After viewing one ID, show only the action menu
        instead of immediately printing all reports again. Return None on Go back
        or file errors. Input and output stay in the I/O manager.
        """

        show_all_reports = True
        while True:
            try:
                reports = self._data.load_reports()
            except (OSError, ValueError) as error:
                self._io.show_message(f"Unable to load reports: {error}")
                return

            if show_all_reports:
                self._io.show_reports(reports)
            choice = self._io.show_report_menu()
            if choice == "7":
                return
            if not reports:
                self._io.show_message("No saved complaints are available. Submit a complaint from the main menu.")
                continue
            if choice == "1":
                completed = self.update_report_status(reports)
            elif choice == "2":
                completed = self.view_one_report(reports)
            elif choice == "3":
                completed = self.edit_report(reports)
            elif choice == "4":
                completed = self.remove_report(reports)
            elif choice == "5":
                completed = self.view_report_history(reports)
            elif choice == "6":
                completed = self.search_reports()
            else:
                continue
            if not completed:
                return
            show_all_reports = choice not in ("2", "5", "6")


    def view_one_report(self, reports):
        """Display one report selected by ID; return False if selection is cancelled."""

        report = self.select_report(reports)
        if report is None:
            return False
        self._io.show_reports([report])
        return True


    def edit_report(self, reports):
        """Edit a selected complaint and save only after any fault changes are accepted.

        Contact-only edits preserve analysis/status. Description or image edits
        rerun AI and business rules and reset status to Pending Action. If AI is
        unavailable, offer manual admin approval. Failed or cancelled edits keep
        the original report intact. Return False on Go back.
        """

        original = self.select_report(reports)
        if original is None:
            return False
        draft = self._io.collect_report_edits(original)
        if draft is None:
            return False
        if draft == original:
            self._io.show_message("No changes to save.")
            return True
        if draft[3:5] != original[3:5]:
            self._io.show_message("Analyzing the updated complaint with Gemini...")
            try:
                processed = self.analyze_report(draft[:6])
            except Exception as error:
                self._io.show_message(f"Analysis failed; original complaint kept: {error}")
                return True
            if processed.get("manual_input_required"):
                self._io.show_message("AI analysis is unavailable. Review this edit manually or go back to keep the original.")
                try:
                    processed = self.manually_analyze_report(draft)
                except ValueError as error:
                    self._io.show_message(f"Invalid review; original complaint kept: {error}")
                    return True
                if processed is None:
                    self._io.show_message("Changes not saved. Original complaint kept.")
                    return True
            if not processed["accepted"]:
                self._io.show_message(processed["reason"])
                self._io.show_message("Changes not saved. Original complaint kept.")
                return True
            draft[6] = processed
        try:
            self._data.update_report(draft)
        except (OSError, ValueError) as error:
            self._io.show_message(f"Unable to save changes: {error}")
            return False
        self._io.show_message(f"Complaint {draft[0]} updated successfully.")
        return True

    def update_report_status(self, reports):
        """Select a saved complaint by ID and persist the selected status.

        Take the currently loaded report list and retry unknown IDs. Return True
        after saving, or False for Go back or a storage error.
        """

        report = self.select_report(reports)
        if report is None:
            return False
        complaint_id = report[0]

        status = self._io.choose_complaint_status()
        if status is None:
            return False
        try:
            self._data.update_complaint_status(complaint_id, status)
        except (OSError, ValueError) as error:
            self._io.show_message(f"Unable to update complaint status: {error}")
            return False
        self._io.show_message(f"Complaint {complaint_id} status updated to {status}.")
        return True

    def remove_report(self, reports):
        """Delete a selected report only after confirmation; return False on Go back."""

        report = self.select_report(reports)
        if report is None:
            return False
        if not self._io.confirm_report_deletion(report):
            self._io.show_message("Deletion cancelled.")
            return True
        try:
            self._data.delete_report(report[0])
        except (OSError, ValueError) as error:
            self._io.show_message(f"Unable to delete complaint: {error}")
            return False
        self._io.show_message(f"Complaint {report[0]} deleted.")
        return True

    def manually_analyze_report(self, complaint):
        """Collect approved admin details and apply the usual severity/routing rules.

        Return processed details marked as a manual review, or None on cancellation.
        This workflow is called only from authenticated admin actions.
        """

        analysis = self._io.collect_manual_analysis(
            complaint, self._ai.categories, self._ai.risks
        )
        if analysis is None:
            return None
        processed = self._logic.process_fault(self._ai.validate_response(analysis))
        processed["status"] = "Pending Action"
        processed["review_source"] = "manual"
        if processed.get("emergency_action"):
            self._io.show_message(processed["emergency_action"])
        return processed

    def review_pending_reports(self):
        """Let an authenticated admin select and approve queued complaints by ID."""

        while True:
            try:
                pending = self._data.load_pending_reviews()
            except (OSError, ValueError) as error:
                self._io.show_message(f"Unable to load manual reviews: {error}")
                return
            if not pending:
                self._io.show_message("No complaints are awaiting manual review.")
                return
            self._io.show_message("Complaints awaiting manual review:")
            self._io.show_reports(pending)
            complaint_id = self._io.collect_report_id()
            if complaint_id is None:
                return
            try:
                complaint = pending[self._data.find_report_index(pending, complaint_id)]
            except ValueError:
                self._io.show_message("Complaint ID not found. Please try again.")
                continue
            try:
                processed = self.manually_analyze_report(complaint)
                if processed is None:
                    self._io.show_message("Review cancelled. Complaint remains awaiting review.")
                    return
                self._data.approve_pending_review(complaint[:6] + [processed])
            except (OSError, ValueError) as error:
                self._io.show_message(f"Unable to approve complaint: {error}")
                return
            self._io.show_message(f"Complaint {complaint_id} approved and saved with Pending Action status.")
            self._io.show_message(processed["alert"])


    def run(self):
        """Start the application and handle menu choices until the user quits.

        Configure logging and load records, then ask for Resident or Admin.
        Authenticate admins before permitting report management. Back clears
        the role; quit exits. Take no arguments and return None when finished.
        """

        logging.basicConfig(
            filename=Path(__file__).resolve().parent / "application.log",
            level=logging.ERROR,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        try:
            self._data.load_reports()
        except (OSError, ValueError) as error:
            self._io.show_message(f"Unable to load saved reports: {error}")

        role = None
        while True:
            if role is None:
                welcome_choice = self._io.show_welcome()
                if welcome_choice == "quit":
                    self._io.show_goodbye()
                    break
                if welcome_choice == "1":
                    role = "resident"
                else:
                    credentials = self._io.collect_admin_credentials()
                    if credentials is None:
                        continue
                    if not self._authenticator.authenticate_admin(*credentials):
                        self._io.show_message("Invalid username or password. Please try again.")
                        continue
                    role = "admin"
                    self._io.show_message("Admin login successful.")

            # New feature: refresh the notification after login and every admin action.
            if role == "admin":
                choice = self._io.show_menu(role, pending_count=self.pending_review_count())
            else:
                choice = self._io.show_menu(role)

            if choice == "quit":
                self._io.show_goodbye()
                break

            elif choice == "back":
                role = None

            elif choice == "1":
                self.process_new_report(role)

            elif choice == "2" and role == "admin":
                self.view_reports()

            elif choice == "3" and role == "admin":
                self.review_pending_reports()
