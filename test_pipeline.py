"""Offline integration checks. Run with: python test_pipeline.py"""

import json
import sys
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from ai_manager import AIManager
from application import ReportApplication
from authentication import DemoAuthenticator
from data_manager import JsonReportRepository
from logic_manager import LogicManager
from io_manager import IOManager

io_manager = IOManager()
ai_manager = AIManager()
logic_manager = LogicManager()
data_manager = JsonReportRepository()
authenticator = DemoAuthenticator()
main = ReportApplication(io_manager, ai_manager, logic_manager, data_manager, authenticator)


def example_analysis(**changes):
    """Return a fresh sample AI dictionary, overriding fields from changes.

    Keyword arguments let tests create different hazards or invalid values
    without changing the default example used by other tests.
    """
    result = {
        "fault_category": "plumbing",
        "summary": "A pipe is leaking in the shared corridor.",
        "risk_indicators": ["active_leak"],
        "common_area_hazard": True,
        "is_unclear": False,
    }
    result.update(changes)
    return result


def example_complaint(complaint_id="Condo-test"):
    """Return a fresh six-item test complaint with the supplied ID string.

    Use fixed resident details and a timestamp to keep test inputs repeatable.
    """
    return [complaint_id, "Resident", "91234567", "pipe leak lah corridor", "no_image", "2026-09-27T10:00:00+08:00"]


def test_input_validation():
    """Check that contact validation rejects bad input and preserves accepted text."""

    with patch("builtins.input", side_effect=[" ", "Resident123", "Test Resident"]), patch("builtins.print"):
        assert io_manager.collect_name() == "Test Resident"
    with patch("builtins.input", side_effect=["", "+", "++65", "ï¼‘ï¼’ï¼“", "abc", "+6500123456"]), patch("builtins.print"):
        assert io_manager.collect_phone_number() == "+6500123456"


def test_rules():
    """Check contractor routing, severity, priority, SLA, and unclear rejection.

    Take no arguments. Return None if all assertions pass; raise
    AssertionError if a business-rule result differs from the expected value.
    """
    for category, contractor in [
        ("plumbing", "Plumbing Contractor"),
        ("electrical", "Electrical Contractor"),
        ("lift", "Lift Maintenance Contractor"),
        ("general maintenance", "General Maintenance Contractor"),
    ]:
        assert logic_manager.process_fault(example_analysis(fault_category=category))["contractor"] == contractor
    for risks, common, score, priority, sla in [
        ([], False, 1, "LOW", "72 hours"),
        (["active_leak"], True, 3, "MEDIUM", "24 hours"),
        (["exposed_wiring"], True, 6, "HIGH", "4 hours"),
        (["fire", "active_leak"], True, 9, "EMERGENCY", "Immediate action"),
        (["fire"], False, 9, "EMERGENCY", "Immediate action"),
        (["smoke"], True, 8, "EMERGENCY", "Immediate action"),
    ]:
        result = logic_manager.process_fault(example_analysis(risk_indicators=risks, common_area_hazard=common))
        assert (result["severity_score"], result["priority"], result["response_sla"]) == (score, priority, sla)
    assert not logic_manager.process_fault(example_analysis(is_unclear=True))["accepted"]
    fire = example_analysis(summary="There is a fire in the apartment.", fault_category="electrical", risk_indicators=["fire"], common_area_hazard=False)
    result = logic_manager.process_fault(fire)
    assert result["priority"] == "EMERGENCY"
    assert result["contractor"] == "Electrical Contractor"
    assert result["contractor_role"] == "Follow-up maintenance only"
    assert "Call SCDF 995 immediately" in result["alert"]
    assert "Follow-up maintenance contractor: Electrical Contractor" in result["alert"]
    # A denied fire is not escalated based on the word 'fire' in the summary.
    routine = logic_manager.process_fault(example_analysis(summary="No fire; a light is faulty.", risk_indicators=[], common_area_hazard=False))
    assert routine["priority"] == "LOW" and "emergency_action" not in routine
    # Manual classification uses the same emergency rules as a valid AI result.
    with patch("io_manager.IOManager.collect_manual_analysis", return_value=fire), patch("io_manager.IOManager.show_message") as show:
        manual = main.manually_analyze_report(example_complaint())
        assert manual["priority"] == "EMERGENCY"
        show.assert_called_once_with(manual["emergency_action"])
    with patch("ai_manager.AIManager.analyze_complaint", return_value=fire), patch("io_manager.IOManager.collect_complaint", return_value=example_complaint()), patch("data_manager.JsonReportRepository.get_next_complaint_id", return_value="Condo-test"), patch("data_manager.JsonReportRepository.save_report", side_effect=OSError("Disk full")), patch("io_manager.IOManager.show_message") as show:
        assert main.process_new_report() is None
        assert any("Call SCDF 995 immediately" in str(call) for call in show.call_args_list)


def test_schema():
    """Check that response validation accepts valid data and rejects bad data.

    Exercise missing fields, wrong types, and unsupported values. Return None
    on success; raise AssertionError if an invalid response is accepted.
    """
    assert ai_manager.validate_response(example_analysis()) == example_analysis()
    for invalid in [
        {}, [], example_analysis(summary=" "), example_analysis(fault_category="unknown"),
        example_analysis(risk_indicators=["unknown"]), example_analysis(is_unclear="false"),
        example_analysis(severity_score=9),
    ]:
        try:
            ai_manager.validate_response(invalid)
        except ValueError:
            continue
        raise AssertionError("Invalid AI response was accepted")


def test_complaint_ids():
    """Verify readable IDs, restart persistence, and safe failure handling.

    Use temporary storage and real input collection with simulated answers.
    Return None when numbering and saved records match all expectations.
    """

    with TemporaryDirectory() as folder:
        path = Path(folder) / "reports.json"
        with patch.object(data_manager, "_reports_file", path):
            assert data_manager.get_next_complaint_id() == "complaint_001"
            path.write_text("[]", encoding="utf-8")
            assert data_manager.get_next_complaint_id() == "complaint_001"

            for expected in ("complaint_001", "complaint_002"):
                with patch("builtins.input", side_effect=["Test Resident", "91234567", "Pipe leaking", "n"]), patch("builtins.print"), patch("ai_manager.AIManager.analyze_complaint", return_value=example_analysis()):
                    saved = main.process_new_report()
                assert saved[0] == expected
            assert [report[0] for report in data_manager.load_reports()] == ["complaint_001", "complaint_002"]

            # A separate Python process must derive its number from disk too.
            result = subprocess.run(
                [sys.executable, "-B", "-c",
                 "import sys; from data_manager import JsonReportRepository; "
                 "print(JsonReportRepository(sys.argv[1]).get_next_complaint_id())", str(path)],
                cwd=Path(__file__).resolve().parent,
                capture_output=True, text=True, check=True,
            )
            assert result.stdout.strip() == "complaint_003"

            before = path.read_bytes()
            with patch("builtins.input", side_effect=["Test Resident", "91234567", "Unclear fault", "n"]), patch("builtins.print"), patch("ai_manager.AIManager.analyze_complaint", return_value=example_analysis(is_unclear=True)):
                assert main.process_new_report() is None
            assert path.read_bytes() == before
            assert data_manager.get_next_complaint_id() == "complaint_003"

            for ids, expected in [
                (["Condo-legacy"], "complaint_002"),
                (["complaint_009", "complaint_002"], "complaint_010"),
                (["complaint_999"], "complaint_1000"),
                (["Condo-legacy", "complaint_007"], "complaint_008"),
            ]:
                path.write_text(json.dumps([[value] for value in ids]), encoding="utf-8")
                assert data_manager.get_next_complaint_id() == expected

            path.write_text("{broken", encoding="utf-8")
            with patch("io_manager.IOManager.collect_complaint") as collect, patch("io_manager.IOManager.show_message"):
                assert main.process_new_report() is None
                collect.assert_not_called()
            assert path.read_text(encoding="utf-8") == "{broken"


def test_pipeline():
    """Check the submission-to-storage flow using a simulated Gemini API.

    Use temporary files to test text/image requests, saving, viewing,
    filtering, rejection, API failures, and protection of existing data.
    Take no arguments and return None if all assertions pass.
    """
    # Substitute the API boundary only; real AI parsing, business rules and JSON IO run.
    google = ModuleType("google")
    genai = ModuleType("google.genai")
    types = ModuleType("google.genai.types")
    # Mimic the SDK configuration constructor by retaining its named arguments.
    types.GenerateContentConfig = lambda **kwargs: SimpleNamespace(**kwargs)
    genai.Client = MagicMock()
    genai.types = types
    google.genai = genai
    client = genai.Client.return_value.__enter__.return_value
    generate = client.models.generate_content
    modules = {"google": google, "google.genai": genai, "google.genai.types": types}

    with TemporaryDirectory() as folder, patch.dict(sys.modules, modules), patch("io_manager.IOManager.show_message") as show:
        reports_file = Path(folder) / "reports.json"
        with patch.object(data_manager, "_reports_file", reports_file):
            assert data_manager.load_reports() == []
            generate.return_value.text = json.dumps(example_analysis())
            complaint = example_complaint()
            original = complaint.copy()
            with patch("io_manager.IOManager.collect_complaint", return_value=complaint):
                saved = main.process_new_report()
            assert saved[:6] == original and len(saved) == 7
            assert saved[6]["severity_score"] == 3
            assert saved[6]["issue_summary"] == example_analysis()["summary"]
            assert generate.call_args.kwargs["contents"] == ["Resident description: pipe leak lah corridor"]
            assert data_manager.load_reports() == [saved]
            assert data_manager.filter_reports("medium") == [saved]
            assert data_manager.filter_reports("high") == []
            with patch("builtins.input", return_value="7"):
                main.view_reports()
            assert any("Plumbing Contractor" in str(call) for call in show.call_args_list)

            # Real optional image read, with a mocked API call.
            from PIL import Image
            image_path = Path(folder) / "leak.png"
            Image.new("RGB", (2, 2)).save(image_path)
            second = example_complaint("Condo-second")
            second[4] = str(image_path)
            def inspect_image(**kwargs):
                """Check the mock request's text/image contents and return fake JSON.

                Receive the API call's keyword arguments, verify its attached
                image can be read, and return a response with a text attribute.
                """
                assert len(kwargs["contents"]) == 2
                kwargs["contents"][1].load()
                return SimpleNamespace(text=json.dumps(example_analysis()))
            generate.side_effect = inspect_image
            with patch("io_manager.IOManager.collect_complaint", return_value=second):
                assert main.process_new_report() is not None
            assert len(data_manager.load_reports()) == 2
            generate.side_effect = None
            before = reports_file.read_bytes()

            # The data manager must reject unconfirmed records even when called directly.
            for details in [
                {},
                {"accepted": False, "is_unclear": False},
                {"accepted": "true", "is_unclear": False},
                {"accepted": 1, "is_unclear": False},
                {"accepted": True},
                {"accepted": True, "is_unclear": True},
                {"accepted": True, "is_unclear": "false"},
            ]:
                try:
                    data_manager.save_report(example_complaint("Condo-unconfirmed") + [details])
                except ValueError:
                    pass
                else:
                    raise AssertionError("Unconfirmed or unclear report was saved")
                assert reports_file.read_bytes() == before

            # Unclear reports are rejected; invalid AI responses queue admin review.
            for number, response in enumerate([json.dumps(example_analysis(is_unclear=True)), "{invalid", "", '{}']):
                generate.return_value.text = response
                with patch("io_manager.IOManager.collect_complaint", return_value=example_complaint(f"Condo-failed-{number}")), patch("ai_manager.logging.getLogger"):
                    result = main.process_new_report()
                    if number == 0:
                        assert result is None
                    else:
                        assert result[6]["manual_input_required"] is True
                if number == 0:
                    assert reports_file.read_bytes() == before
                assert data_manager.load_reports()[:2] == json.loads(before)
            generate.side_effect = RuntimeError("API unavailable")
            with patch("io_manager.IOManager.collect_complaint", return_value=example_complaint("Condo-offline")), patch("ai_manager.logging.getLogger"):
                assert main.process_new_report()[6]["status"] == "Pending Manual Review"
            assert len(data_manager.load_pending_reviews()) == 4
            assert len(data_manager.load_reports()) == 6
            assert data_manager.load_reports()[:2] == json.loads(before)
            before = reports_file.read_bytes()

            # Duplicate IDs and failed replacement must preserve saved data.
            try:
                data_manager.save_report(saved)
            except ValueError:
                pass
            else:
                raise AssertionError("Duplicate ID accepted")
            third = example_complaint("Condo-third") + [saved[6]]
            with patch("data_manager.os.replace", side_effect=OSError("Disk error")):
                try:
                    data_manager.save_report(third)
                except OSError:
                    pass
                else:
                    raise AssertionError("Write failure hidden")
            assert reports_file.read_bytes() == before
            assert not list(Path(folder).glob("*.tmp"))
            reports_file.write_text("{broken", encoding="utf-8")
            main.view_reports()
            try:
                data_manager.save_report(third)
            except ValueError:
                pass
            else:
                raise AssertionError("Corrupt file overwritten")
            assert reports_file.read_text(encoding="utf-8") == "{broken"


def test_status_updates():
    """Check status persistence, menu navigation, and unchanged data on failures.

    Exercise real menu input with temporary records, including legacy reports.
    Return None if every check passes; assertions identify any regression.
    """

    with TemporaryDirectory() as folder:
        path = Path(folder) / "reports.json"
        with patch.object(data_manager, "_reports_file", path), patch("builtins.print"):
            details = logic_manager.process_fault(example_analysis())
            first = example_complaint("complaint_001") + [dict(details)]
            second = example_complaint("complaint_002") + [dict(details)]
            data_manager.save_report(first)
            data_manager.save_report(second)
            stored = json.loads(path.read_text(encoding="utf-8"))
            assert stored[0][6]["status"] == "Pending Action"

            for choice, expected in [("1", "Contractor contacted"), ("3", "Resolved"), ("2", "Pending Action")]:
                with patch("builtins.input", side_effect=["1", "bad_id", "complaint_001", "invalid", choice, "7"]):
                    main.view_reports()
                updated = json.loads(path.read_text(encoding="utf-8"))
                assert updated[0][6]["status"] == expected
                assert updated[0][:6] == stored[0][:6]
                assert updated[1] == stored[1]

            before = path.read_bytes()
            for answers in [["7"], ["1", "back"], ["1", "complaint_001", "4"]]:
                with patch("builtins.input", side_effect=answers):
                    main.view_reports()
                assert path.read_bytes() == before

            for complaint_id, status in [("missing", "Resolved"), ("complaint_001", "invalid")]:
                try:
                    data_manager.update_complaint_status(complaint_id, status)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Invalid update accepted")
                assert path.read_bytes() == before

            with patch("data_manager.os.replace", side_effect=OSError("Disk error")), patch("builtins.input", side_effect=["1", "complaint_001", "3"]):
                main.view_reports()
            assert path.read_bytes() == before

            # Legacy records receive a default on read without modifying the file.
            path.write_text(json.dumps([first]), encoding="utf-8")
            before = path.read_bytes()
            assert data_manager.load_reports()[0][6]["status"] == "Pending Action"
            assert path.read_bytes() == before
            data_manager.update_complaint_status("complaint_001", "Resolved")
            assert json.loads(path.read_text())[0][6]["status"] == "Resolved"

            path.write_text("[]", encoding="utf-8")
            with patch("builtins.input", side_effect=["1", "7"]):
                main.view_reports()
            assert path.read_text() == "[]"


def test_crud():
    """Check view/edit/delete menus against temporary JSON without live API calls.

    Verify contact and fault edits, reanalysis, cancellation, storage failures,
    deletion confirmation, and preservation of other records and metadata.
    """

    with TemporaryDirectory() as folder:
        path = Path(folder) / "reports.json"
        with patch.object(data_manager, "_reports_file", path), patch("builtins.print"):
            details = logic_manager.process_fault(example_analysis())
            details["status"] = "Resolved"
            for complaint_id in ("complaint_001", "complaint_002"):
                data_manager.save_report(example_complaint(complaint_id) + [dict(details)])
            original = data_manager.get_report("complaint_001")
            other = data_manager.get_report("complaint_002")

            # View one record, including retrying an unknown ID.
            with patch("builtins.input", side_effect=["2", "missing", "complaint_001", "7"]), patch("io_manager.IOManager.show_reports") as show:
                main.view_reports()
                assert len(show.call_args_list) == 2
                assert show.call_args_list[0].args[0] == [original, other]
                assert show.call_args_list[1].args[0] == [original]

            # Contact changes do not need another AI call and preserve status.
            with patch("builtins.input", side_effect=["3", "complaint_001", "1", "123", "Updated Resident", "2", "abc", "+6591234567", "5", "7"]), patch("ai_manager.AIManager.analyze_complaint") as analyze:
                main.view_reports()
                analyze.assert_not_called()
            updated = data_manager.get_report("complaint_001")
            assert updated[1:3] == ["Updated Resident", "+6591234567"]
            assert {k: v for k, v in updated[6].items() if k != "history"} == {k: v for k, v in original[6].items() if k != "history"}
            assert updated[6]["history"][:-1] == original[6]["history"]
            assert updated[6]["history"][-1]["action"] == "Complaint edited"
            assert updated[0] == original[0] and updated[5] == original[5]
            assert data_manager.get_report("complaint_002") == other

            before = path.read_bytes()
            for answers in [
                ["3", "back"],
                ["3", "complaint_001", "1", "Discarded Name", "6"],
                ["4", "back"],
                ["4", "complaint_001", "invalid", "n", "7"],
            ]:
                with patch("builtins.input", side_effect=answers):
                    main.view_reports()
                assert path.read_bytes() == before

            # Fault edits are reanalyzed and reset the action status.
            revised_analysis = example_analysis(summary="Lift is out of service.", fault_category="lift", risk_indicators=["service_outage"])
            with patch("builtins.input", side_effect=["3", "complaint_001", "3", "Lift is broken", "5", "7"]), patch("ai_manager.AIManager.analyze_complaint", return_value=revised_analysis) as analyze:
                main.view_reports()
                assert analyze.call_args.args[0][3] == "Lift is broken"
                assert len(analyze.call_args.args[0]) == 6
            updated = data_manager.get_report("complaint_001")
            assert updated[6]["status"] == "Pending Action"
            assert updated[6]["contractor"] == "Lift Maintenance Contractor"
            assert updated[5] == original[5]

            before = path.read_bytes()
            for response in [example_analysis(is_unclear=True), RuntimeError("API unavailable")]:
                with patch("builtins.input", side_effect=["3", "complaint_001", "3", "bad update", "5", "7"]), patch("ai_manager.AIManager.analyze_complaint", **({"side_effect": response} if isinstance(response, Exception) else {"return_value": response})):
                    main.view_reports()
                assert path.read_bytes() == before

            # File errors must preserve the original records for both mutations.
            for answers in [["3", "complaint_001", "1", "Another Name", "5"], ["4", "complaint_001", "y"]]:
                with patch("builtins.input", side_effect=answers), patch("data_manager.os.replace", side_effect=OSError("Disk error")):
                    main.view_reports()
                assert path.read_bytes() == before

            # Invalid direct calls cannot replace or delete unrelated data.
            for operation, argument in [(data_manager.delete_report, "missing"), (data_manager.get_report, "missing"), (data_manager.update_report, original[:6] + [{"accepted": False}])]:
                try:
                    operation(argument)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Invalid CRUD operation accepted")
                assert path.read_bytes() == before

            with patch("builtins.input", side_effect=["4", "missing", "complaint_001", "y", "7"]):
                main.view_reports()
            assert data_manager.load_reports() == [other]
            assert json.loads(path.read_text())[0][0] == "complaint_002"
            data_manager.delete_report("complaint_002")
            assert data_manager.load_reports() == []
            assert data_manager.get_next_complaint_id() == "complaint_001"
            with patch("builtins.input", side_effect=["3", "4", "2", "7"]):
                main.view_reports()


def test_role_access():
    """Verify resident restrictions, admin authentication, and logout behavior.

    Exercise real terminal menus with simulated input. Stub report actions
    and logging so these checks do not modify saved complaints or logs.
    """

    assert authenticator.authenticate_admin("admin123", "password123")
    assert not authenticator.authenticate_admin("wrong", "password123")
    assert not authenticator.authenticate_admin("admin123", "wrong")

    with patch("application.logging.basicConfig"), patch("data_manager.JsonReportRepository.load_reports", return_value=[]):
        with patch("builtins.input", side_effect=["invalid", "1", "2", "1", "quit"]), patch("builtins.print") as output, patch("application.ReportApplication.process_new_report") as submit, patch("application.ReportApplication.view_reports") as view:
            main.run()
            submit.assert_called_once()
            view.assert_not_called()
            assert not any("2. View reports" in str(call) for call in output.call_args_list)

        # Wrong credentials stay at welcome; a correct retry opens admin actions.
        with patch("builtins.input", side_effect=["2", "admin123", "2", "admin123", "2", "1", "back", "1", "2", "quit"]), patch("io_manager.getpass", side_effect=["wrong", "password123"]), patch("builtins.print") as output, patch("application.ReportApplication.process_new_report") as submit, patch("application.ReportApplication.view_reports") as view:
            main.run()
            submit.assert_called_once()
            view.assert_called_once()
            assert any("Invalid username or password" in str(call) for call in output.call_args_list)
            assert any("Admin login successful" in str(call) for call in output.call_args_list)

        with patch("builtins.input", side_effect=["2", "back", "quit"]), patch("io_manager.getpass") as password, patch("builtins.print"), patch("application.ReportApplication.view_reports") as view:
            main.run()
            password.assert_not_called()
            view.assert_not_called()

        # Even if a menu returned an unauthorized choice, main blocks it.
        with patch("io_manager.IOManager.show_welcome", return_value="1"), patch("io_manager.IOManager.show_menu", side_effect=["2", "quit"]), patch("builtins.print"), patch("application.ReportApplication.view_reports") as view:
            main.run()
            view.assert_not_called()


def test_manual_review():
    """Check persisted AI failures, admin approval/cancellation and safe write errors."""

    with TemporaryDirectory() as folder, patch("builtins.print"), patch("ai_manager.logging.getLogger"):
        path = Path(folder) / "reports.json"
        with patch.object(data_manager, "_reports_file", path):
            # The real wrapper converts API errors to a marker; logic must not crash.
            with patch("ai_manager.AIManager.request_analysis", side_effect=RuntimeError("private error body")), patch("io_manager.IOManager.collect_complaint", return_value=example_complaint("complaint_001")), patch("application.logging.basicConfig"), patch("builtins.input", side_effect=["1", "1", "quit"]), patch("logic_manager.LogicManager.determine_severity") as score, patch("logic_manager.LogicManager.assign_contractor") as contractor:
                main.run()
                score.assert_not_called()
                contractor.assert_not_called()
            queued = data_manager.get_report("complaint_001")
            assert queued[6]["accepted"] is False
            assert queued[6]["status"] == "Pending Manual Review"
            assert "private error body" not in path.read_text()
            assert data_manager.load_reports() == [queued]
            assert not path.with_name("pending_reviews.json").exists()
            assert data_manager.load_pending_reviews() == [queued]
            assert data_manager.get_next_complaint_id() == "complaint_002"
            result = subprocess.run(
                [sys.executable, "-B", "-c", "import sys; from data_manager import JsonReportRepository; print(JsonReportRepository(sys.argv[1]).get_next_complaint_id())", str(path)],
                capture_output=True, text=True, check=True,
            )
            assert result.stdout.strip() == "complaint_002"
            before = path.read_bytes()
            # Pending records can be viewed, but a status change cannot bypass approval.
            assert data_manager.get_report("complaint_001") == queued
            try:
                data_manager.update_complaint_status("complaint_001", "Resolved")
            except ValueError:
                pass
            else:
                raise AssertionError("Pending review bypassed admin classification")
            assert path.read_bytes() == before
            # Unknown IDs retry; cancelling final approval must leave the queue intact.
            with patch("builtins.input", side_effect=["missing", "complaint_001", "Pipe leaking", "1", "7", "1", "2"]):
                main.review_pending_reports()
            assert path.read_bytes() == before

            # Failing the accepted-file write must not remove the pending complaint.
            with patch("builtins.input", side_effect=["complaint_001", "Pipe leaking", "1", "7", "1", "1"]), patch("data_manager.os.replace", side_effect=OSError("Disk full")):
                main.review_pending_reports()
            assert path.read_bytes() == before
            assert not list(Path(folder).glob("*.tmp"))

            with patch("builtins.input", side_effect=["complaint_001", "Pipe leaking", "1", "7", "1", "1"]), patch("ai_manager.AIManager.request_analysis") as api:
                main.review_pending_reports()
                api.assert_not_called()
            approved = data_manager.get_report("complaint_001")
            assert approved[:6] == queued[:6]
            assert approved[6]["review_source"] == "manual"
            assert approved[6]["status"] == "Pending Action"
            assert approved[6]["severity_score"] == 3
            assert approved[6]["contractor"] == "Plumbing Contractor"
            assert data_manager.load_pending_reviews() == []
            assert len(data_manager.load_reports()) == 1

            # Queue write failures preserve existing accepted data and don't claim success.
            accepted_before = path.read_bytes()
            with patch("ai_manager.AIManager.request_analysis", side_effect=RuntimeError("offline")), patch("io_manager.IOManager.collect_complaint", return_value=example_complaint("complaint_002")), patch("data_manager.os.replace", side_effect=OSError("Disk full")):
                assert main.process_new_report() is None
            assert path.read_bytes() == accepted_before
            assert data_manager.load_pending_reviews() == []

            # Accepted and pending reports coexist; approval replaces only the selected record.
            second = example_complaint("complaint_002") + [dict(queued[6])]
            second = data_manager.save_report(second)
            assert data_manager.load_reports() == [approved, second]
            assert data_manager.get_next_complaint_id() == "complaint_003"
            try:
                data_manager.save_report(second)
            except ValueError:
                pass
            else:
                raise AssertionError("Duplicate pending ID was accepted")
            # Contact edits preserve the review requirement and leave accepted data intact.
            second[1] = "Updated Resident"
            data_manager.update_report(second)
            edited = data_manager.get_report("complaint_002")[6]
            assert {k: v for k, v in edited.items() if k != "history"} == {k: v for k, v in queued[6].items() if k != "history"}
            assert edited["history"][-1]["changes"]["name"]["new"] == "Updated Resident"
            details = dict(approved[6])
            data_manager.approve_pending_review(second[:6] + [details])
            assert data_manager.get_report("complaint_001") == approved
            assert len(data_manager.load_reports()) == 2
            assert data_manager.get_report("complaint_002")[6]["accepted"] is True
            assert data_manager.load_pending_reviews() == []
            data_manager.delete_report("complaint_002")
            assert data_manager.load_pending_reviews() == []
            third = example_complaint("complaint_003") + [dict(queued[6])]
            data_manager.save_report(third)
            data_manager.delete_report("complaint_003")
            assert data_manager.load_reports() == [approved]

            # An admin can manually approve a fault edit without changing its ID/time.
            draft = approved[:6] + [dict(approved[6])]
            draft[3] = "Lift outage"
            with patch("application.ReportApplication.select_report", return_value=approved), patch("io_manager.IOManager.collect_report_edits", return_value=draft), patch("ai_manager.AIManager.request_analysis", side_effect=RuntimeError("offline")), patch("builtins.input", side_effect=["Lift is out of service", "2", "9", "2", "1"]):
                assert main.edit_report([approved]) is True
            updated = data_manager.get_report("complaint_001")
            assert updated[3] == "Lift outage" and updated[5] == approved[5]
            assert updated[6]["contractor"] == "Lift Maintenance Contractor"
            before_edit = path.read_bytes()
            with patch("application.ReportApplication.select_report", return_value=updated), patch("io_manager.IOManager.collect_report_edits", return_value=approved), patch("ai_manager.AIManager.request_analysis", side_effect=RuntimeError("offline")), patch("builtins.input", return_value="back"):
                assert main.edit_report([updated]) is True
            assert path.read_bytes() == before_edit

            path.write_text("{broken", encoding="utf-8")
            with patch("io_manager.IOManager.collect_complaint") as collect:
                assert main.process_new_report() is None
                collect.assert_not_called()
            assert path.read_text() == "{broken"

    # Main enforces the admin boundary even if a menu returns an unauthorized choice.
    with patch("application.logging.basicConfig"), patch("data_manager.JsonReportRepository.load_reports", return_value=[]), patch("builtins.print"), patch("io_manager.IOManager.show_welcome", return_value="1"), patch("io_manager.IOManager.show_menu", side_effect=["3", "quit"]), patch("application.ReportApplication.review_pending_reports") as review:
        main.run()
        review.assert_not_called()
    with patch("application.logging.basicConfig"), patch("data_manager.JsonReportRepository.load_reports", return_value=[]), patch("builtins.print"), patch("builtins.input", side_effect=["2", "admin123", "3", "quit"]), patch("io_manager.getpass", return_value="password123"), patch("application.ReportApplication.review_pending_reports") as review:
        main.run()
        review.assert_called_once()


if __name__ == "__main__":
    test_input_validation()
    test_rules()
    test_schema()
    test_complaint_ids()
    test_pipeline()
    test_status_updates()
    test_crud()
    test_role_access()
    test_manual_review()
    # Keep terminal output in the I/O manager, including the test script.
    io_manager.show_message("All offline pipeline checks passed.")