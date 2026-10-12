"""Simple offline checks. Run from the project folder: python test_simple_app.py

Uses sample analysis instead of Gemini and a temporary JSON file for storage.
Menu tests use pretend keyboard input. No live API calls are made.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import data_manager
import io_manager
import logic_manager


def check(description, actual, expected):
    """Stop with an explanation if a result is wrong; otherwise print PASS."""
    assert actual == expected, f"{description}: expected {expected!r}, got {actual!r}"
    print("PASS:", description)


def test_login():
    """Check correct credentials and reject an incorrect password or username."""
    check("Correct admin login", logic_manager.authenticate_admin("admin123", "password123"), True)
    check("Wrong password rejected", logic_manager.authenticate_admin("admin123", "wrong"), False)
    check("Wrong username rejected", logic_manager.authenticate_admin("wrong", "password123"), False)


def test_input():
    """Check that invalid names and phone numbers are retried and spaces trimmed."""
    # patch supplies these answers to input() in order, instead of asking us.
    # Hide the prompts so the test output only shows PASS messages.
    with patch("builtins.input", side_effect=[" ", "Resident123", "  Test Resident  "]), patch("builtins.print"):
        name = io_manager.collect_name()
    check("Invalid names retried; valid name trimmed", name, "Test Resident")

    with patch("builtins.input", side_effect=["", "abc", "++65", "  +6500123456  "]), patch("builtins.print"):
        phone = io_manager.collect_phone_number()
    check("Invalid phones retried; plus and zeros preserved", phone, "+6500123456")


def test_menus():
    """Check resident restrictions, admin options, invalid choices and navigation."""
    # A resident must not be allowed to choose either admin-only option.
    with patch("builtins.input", side_effect=["2", "3", "1"]), patch("builtins.print"):
        choice = io_manager.show_menu("resident")
    check("Resident cannot select admin options", choice, "1")

    # Each row contains: session role, pretend answers, expected menu result.
    cases = [
        ("resident", ["back"], "back"),
        ("resident", ["quit"], "quit"),
        ("admin", ["1"], "1"),
        ("admin", ["2"], "2"),
        ("admin", ["3"], "3"),
        ("admin", ["back"], "back"),
        ("admin", ["quit"], "quit"),
        ("admin", ["9", "", "  BACK  "], "back"),
    ]
    for role, answers, expected in cases:
        with patch("builtins.input", side_effect=answers), patch("builtins.print"):
            choice = io_manager.show_menu(role)
        check(f"{role} menu with input {answers}", choice, expected)


def test_logic():
    """Check a leak, a fire, an unclear report and the AI-unavailable result."""
    analysis = {
        "fault_category": "plumbing",
        "summary": "A pipe is leaking in the corridor.",
        "risk_indicators": ["active_leak"],
        "common_area_hazard": True,
        "is_unclear": False,
    }

    result = logic_manager.process_fault(analysis)
    check("Clear complaint accepted", result["accepted"], True)
    check("Leak severity", result["severity_score"], 3)
    check("Leak priority", result["priority"], "MEDIUM")
    check("Plumbing contractor assigned", result["contractor"], "Plumbing Contractor")
    check("Medium response time", result["response_sla"], "24 hours")

    analysis["summary"] = "There is a fire inside an apartment."
    analysis["fault_category"] = "electrical"
    analysis["risk_indicators"] = ["fire"]
    analysis["common_area_hazard"] = False
    result = logic_manager.process_fault(analysis)
    check("Fire severity", result["severity_score"], 9)
    check("Fire inside an apartment is an emergency", result["priority"], "EMERGENCY")

    analysis["is_unclear"] = True
    check("Unclear complaint rejected", logic_manager.process_fault(analysis)["accepted"], False)

    result = logic_manager.process_fault({"ai_available": False})
    check("AI unavailable needs manual review", result["status"], "Pending Manual Review")


def test_storage():
    """Save, read, edit and delete sample reports without touching real data."""
    original_path = data_manager.REPORTS_FILE
    try:
        # TemporaryDirectory creates a separate folder and removes it afterwards.
        with TemporaryDirectory() as folder:
            data_manager.REPORTS_FILE = Path(folder) / "reports.json"
            check("Empty storage starts at 001", data_manager.get_next_complaint_id(), "complaint_001")

            report = [
                "complaint_001", "Test Resident", "91234567",
                "Leaking pipe", "no_image", "2026-10-13 10:00:00",
                {"accepted": True, "is_unclear": False},
            ]
            data_manager.save_report(report)
            check("One report saved", len(data_manager.load_reports()), 1)
            saved = data_manager.get_report("complaint_001")
            check("Read report by ID", saved[1], "Test Resident")
            check("Default status", saved[6]["status"], "Pending Action")
            check("Next saved ID is 002", data_manager.get_next_complaint_id(), "complaint_002")

            saved[1] = "Updated Resident"
            data_manager.update_report(saved)
            check("Edited name saved", data_manager.get_report("complaint_001")[1], "Updated Resident")

            data_manager.update_complaint_status("complaint_001", "Resolved")
            check("Updated status saved", data_manager.get_report("complaint_001")[6]["status"], "Resolved")

            pending = report[:6]
            pending[0] = "complaint_002"
            pending.append(logic_manager.process_fault({"ai_available": False}))
            data_manager.save_report(pending)
            check("Manual review saved in JSON", data_manager.get_report("complaint_002")[6]["status"], "Pending Manual Review")

            data_manager.delete_report("complaint_001")
            remaining = data_manager.load_reports()
            check("Delete removes only the chosen report", [item[0] for item in remaining], ["complaint_002"])
    finally:
        # Restore the normal path even if a test fails.
        data_manager.REPORTS_FILE = original_path


if __name__ == "__main__":
    test_login()
    test_input()
    test_menus()
    test_logic()
    test_storage()
    print("\nAll simple tests passed!")
