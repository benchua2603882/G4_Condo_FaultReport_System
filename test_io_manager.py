"""Tests for the OOP IOManager. Run with: python test_io_manager.py"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from io_manager import (
    AdminMenu, ConsoleChannel, IOChannel, ImagePathCollector, MenuRegistry,
    NameValidator, PhoneValidator, RequiredTextValidator, ResidentMenu,
    ValidatedPrompter, ReportFormatter, IOManager
)

def check(label, actual, expected):
    assert actual == expected, f"{label}: expected {expected!r}, got {actual!r}"
    print("PASS:", label)


def test_channel_interface():
    try:
        IOChannel()
        raise AssertionError("IOChannel should be abstract")
    except TypeError:
        print("PASS: IOChannel is now abstract hence cannot be created directly")

    channel = ConsoleChannel()
    with patch("builtins.input", return_value="hello") as fake_input:
        check("ConsoleChannel.read returns typed text", channel.read("Q: "), "hello")
        fake_input.assert_called_once_with("Q: ")
    with patch("builtins.print") as fake_print:
        channel.write("hi")
        fake_print.assert_called_once_with("hi")

def test_validators_polymorphism():
    """Every validator is used the same way: clean() or ValueError."""
    cases = [
        (NameValidator(), "  Test Resident  ", "Test Resident", "Resident123"),
        (PhoneValidator(), "  +6500123456  ", "+6500123456", "++65"),
        (RequiredTextValidator(), "  leak  ", "leak", "   "),
    ]
    for validator, good_raw, good_clean, bad_raw in cases:
        name = type(validator).__name__
        check(f"{name} accepts and trims", validator.clean(good_raw), good_clean)
        try:
            validator.clean(bad_raw)
            raise AssertionError(f"{name} accepted bad input")
        except ValueError as error:
            check(f"{name} rejects bad input", str(error), validator.error_message)

class FakeChannel(IOChannel):
    """Plays back scripted answers and records everything shown to the user."""

    def __init__(self, answers=()):
        self._answers = list(answers)
        self.output = []

    def read(self, prompt=""):
        self.output.append(prompt)
        return self._answers.pop(0)

    def read_secret(self, prompt=""):
        self.output.append(prompt)
        return self._answers.pop(0)

    def write(self, message=""):
        self.output.append(str(message))


def test_prompter_retries():
    channel = FakeChannel([" ", "Resident123", "  Test Resident  "])
    prompter = ValidatedPrompter(channel)
    check("name retried then trimmed", prompter.ask("Name? ", NameValidator()), "Test Resident")
    check("two error messages shown",
          channel.output.count(NameValidator().error_message), 2)

    prompter = ValidatedPrompter(FakeChannel(["", "abc", "++65", "１２３", "  +6500123456  "]))
    check("phone retried, plus and zeros kept",
          prompter.ask("Phone? ", PhoneValidator()), "+6500123456")


def test_image_path_collector():
    with TemporaryDirectory() as folder:
        (Path(folder) / "leak.png").write_bytes(b"x")
        (Path(folder) / "note.txt").write_text("x")

        answers = ["maybe", "y", "", "missing.png", "note.txt", "leak.png"]
        collector = ImagePathCollector(FakeChannel(answers), project_folder=Path(folder))
        expected = str((Path(folder) / "leak.png").resolve())
        check("retries bad answers and returns absolute path", collector.collect(), expected)

        collector = ImagePathCollector(FakeChannel(["N"]), project_folder=Path(folder))
        check("N returns no_image", collector.collect(), "no_image")

def test_menu_classes():
    registry = MenuRegistry()
    check("resident menu type", type(registry.for_role("resident")), ResidentMenu)
    check("admin menu type", type(registry.for_role("admin")), AdminMenu)
    check("unknown role falls back to resident", type(registry.for_role("guest")), ResidentMenu)
    check("resident cannot choose 2", "2" in registry.for_role("resident").allowed_choices, False)
    check("admin can choose 3", "3" in registry.for_role("admin").allowed_choices, True)
    check("admin keeps resident option", "1. Submit a complaint" in AdminMenu().option_lines, True)

def test_report_formatter():
    report = ["complaint_001", "Test Resident", "91234567", "Leaking pipe",
              "no_image", "2026-10-13T10:00:00+08:00",
              {"accepted": True, "risk_indicators": ["active_leak"], "extra": None}]
    lines = ReportFormatter().format(report)
    check("table starts with a border", lines[0].startswith("+-"), True)
    check("bool shown as Yes", any("Accepted" in l and "Yes" in l for l in lines), True)
    check("list shown as text", any("active_leak" in l for l in lines), True)
    check("None shown as N/A", any("N/A" in l for l in lines), True)
    check("formatter does not change the report", report[6]["accepted"], True)

    long_report = report[:3] + ["word " * 40] + report[4:]
    check("long text is wrapped, not cut",
          sum("word" in l for l in ReportFormatter().format(long_report)) > 1, True)

def test_collect_name_and_phone():
    io = IOManager(FakeChannel([" ", "Resident123", "  Test Resident  "]))
    check("name retried then trimmed", io.collect_name(), "Test Resident")


def test_collect_complaint():
    io = IOManager(FakeChannel(["Test Resident", "91234567", "Pipe leaking", "n"]))
    complaint = io.collect_complaint("complaint_001")
    check("complaint has six fields", len(complaint), 6)
    check("complaint id kept", complaint[0], "complaint_001")
    check("description stored", complaint[3], "Pipe leaking")
    check("no image marker", complaint[4], "no_image")


def test_show_menu_by_role():
    io = IOManager(FakeChannel(["2", "3", "1"]))
    check("resident cannot pick admin options", io.show_menu("resident"), "1")
    io = IOManager(FakeChannel(["9", "", "  BACK  "]))
    check("admin menu retries then accepts back", io.show_menu("admin"), "back")


def test_admin_credentials():
    io = IOManager(FakeChannel(["admin123", "password123"]))
    check("credentials returned", io.collect_admin_credentials(), ("admin123", "password123"))
    io = IOManager(FakeChannel(["BACK"]))
    check("back cancels login", io.collect_admin_credentials(), None)


def test_show_reports_empty():
    channel = FakeChannel()
    IOManager(channel).show_reports([])
    check("empty list message", channel.output, ["\nNo saved reports found."])

def test_report_actions():
    report = ["complaint_001", "Test Resident", "91234567", "Leaking pipe",
              "no_image", "2026-10-13T10:00:00+08:00", {"accepted": True}]

    io = IOManager(FakeChannel(["maybe", "Y"]))
    check("deletion confirmed with Y", io.confirm_report_deletion(report), True)

    io = IOManager(FakeChannel(["n"]))
    check("deletion cancelled with N", io.confirm_report_deletion(report), False)

    io = IOManager(FakeChannel(["7", "2"]))
    check("status picked after retry", io.choose_complaint_status(), "Pending Action")

    io = IOManager(FakeChannel(["3", "Dripping tap in corridor", "5"]))
    edited = io.collect_report_edits(report)
    check("edit changes the copy", edited[3], "Dripping tap in corridor")
    check("original report untouched", report[3], "Leaking pipe")

    io = IOManager(FakeChannel(["6"]))
    check("go back returns None", io.collect_report_edits(report), None)


def test_manual_analysis():
    complaint = ["complaint_002", "Test Resident", "91234567", "Pipe leaking",
                 "no_image", "2026-10-13T10:00:00+08:00",
                 {"accepted": False, "manual_input_required": True}]
    categories = ["plumbing", "lift"]
    risks = ["fire", "active_leak"]

    # summary, category 1, hazards "2", common area 1 (Yes), confirm 1
    io = IOManager(FakeChannel(["Pipe is leaking", "1", "2", "1", "1"]))
    result = io.collect_manual_analysis(complaint, categories, risks)
    check("manual analysis dict", result, {
        "fault_category": "plumbing",
        "summary": "Pipe is leaking",
        "risk_indicators": ["active_leak"],
        "common_area_hazard": True,
        "is_unclear": False,
    })

    io = IOManager(FakeChannel(["back"]))
    check("back at summary cancels", io.collect_manual_analysis(complaint, categories, risks), None)

    io = IOManager(FakeChannel(["Pipe is leaking", "1", "9", "back"]))
    check("invalid hazard then back cancels",
          io.collect_manual_analysis(complaint, categories, risks), None)

def test_admin_pending_notification():
    channel = FakeChannel(["1"])
    IOManager(channel).show_menu("admin", pending_count=3)
    check("admin sees pending notice",
          any("NOTICE: 3 complaint(s)" in line for line in channel.output), True)

    channel = FakeChannel(["1"])
    IOManager(channel).show_menu("admin", pending_count=0)
    check("no notice when count is zero",
          any("NOTICE" in line for line in channel.output), False)

    channel = FakeChannel(["1"])
    IOManager(channel).show_menu("resident", pending_count=3)
    check("resident never sees the notice",
          any("NOTICE" in line for line in channel.output), False)
    
if __name__ == "__main__":
    test_channel_interface()
    test_validators_polymorphism()
    test_prompter_retries()
    test_image_path_collector()
    test_menu_classes()
    test_report_formatter()
    test_collect_name_and_phone()
    test_collect_complaint()
    test_show_menu_by_role()
    test_admin_credentials()
    test_show_reports_empty()
    test_report_actions()
    test_manual_analysis()
    test_admin_pending_notification()
    print("\nAll IOManager tests passed!")