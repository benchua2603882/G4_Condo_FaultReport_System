"""Tests for logic_manager.py. Run with: python test_logic_manager.py"""

import logic_manager


def check(label, actual, expected):
    """Print a [PASS] or [FAIL] tag with the result, then compare them."""
    status = "PASS" if actual == expected else "FAIL"
    print(f"[{status}] {label} -> got {actual!r}, expected {expected!r}")
    assert actual == expected

def test_invalid_ai_result():
    """Simulate invalid AI output reaching the Logic Manager."""
    false_ai_result = {
        "is_unclear": False,
        "fault_category": "electrical",
        "summary": "Sparks in lobby",
        "risk_indicators": ["invalid_risk"],
        "common_area_hazard": True
    }

    try:
        logic_manager.process_fault(false_ai_result)
        print("[FAIL] Invalid AI result was not rejected")
    except KeyError:
        print("[PASS] Invalid AI result caused a KeyError as expected")

def test_authenticate_admin():
    """Only the exact username and password should log in."""
    check("correct login", logic_manager.authenticate_admin("admin123", "password123"), True)
    check("wrong password", logic_manager.authenticate_admin("admin123", "wrong"), False)
    check("wrong username", logic_manager.authenticate_admin("wrong", "password123"), False)
    check("empty input", logic_manager.authenticate_admin("", ""), False)


def test_severity():
    """The highest risk score should win, and no risks should give 1."""
    check("fire + leak", logic_manager.determine_severity({"risk_indicators": ["fire", "active_leak"]}), 9)
    check("exposed wiring", logic_manager.determine_severity({"risk_indicators": ["exposed_wiring"]}), 6)
    check("no risks", logic_manager.determine_severity({"risk_indicators": []}), 1)


def test_priority():
    """Check priority levels, common-area rules, and fire emergencies."""
    cases = [
        (8, True, "EMERGENCY"),
        (8, False, "HIGH"),
        (6, False, "HIGH"),
        (3, False, "MEDIUM"),
        (1, False, "LOW")
    ]

    for score, hazard, expected in cases:
        data = {
            "severity_score": score,
            "common_area_hazard": hazard,
            "risk_indicators": []
        }
        check(
            f"score {score}, common area {hazard}",
            logic_manager.determine_priority(data),
            expected
        )

    fire_data = {
        "severity_score": 9,
        "common_area_hazard": False,
        "risk_indicators": ["fire"]
    }
    check(
        "fire is emergency indoors",
        logic_manager.determine_priority(fire_data),
        "EMERGENCY"
    )


def test_contractor():
    """Each category should go to the right contractor."""
    cases = [("plumbing", "Plumbing Contractor"), ("electrical", "Electrical Contractor"),
             ("lift", "Lift Maintenance Contractor"), ("other", "General Maintenance Contractor")]
    for category, expected in cases:
        check(category, logic_manager.assign_contractor({"fault_category": category}), expected)


def test_sla():
    """Each priority should give the right response time."""
    cases = [
    ("EMERGENCY", "Immediate action"),
    ("HIGH", "4 hours"),
    ("MEDIUM", "24 hours"),
    ("LOW", "72 hours")
]
    for priority, expected in cases:
        check(priority, logic_manager.calculate_sla(priority), expected)


def test_alert():
    """The alert should have the exact four-line format."""
    alert = logic_manager.create_alert({"issue_summary": "Dripping tap"}, "MEDIUM", "Plumbing Contractor", "24 hours")
    print(alert)
    check("alert text", alert, "Priority: MEDIUM\nContractor: Plumbing Contractor\nResponse SLA: 24 hours\nIssue: Dripping tap")


def test_process_fault():
    """Check an unclear report and an emergency report from start to finish."""
    unclear = {"is_unclear": True, "fault_category": "lift", "summary": "?",
               "risk_indicators": [], "common_area_hazard": False}
    rejected = logic_manager.process_fault(unclear)
    check("unclear accepted", rejected["accepted"], False)
    check("unclear message", rejected["reason"],
          "Please resubmit with clearer details about the fault and its location.")

    report = {"is_unclear": False, "fault_category": "electrical", "summary": "Sparks in lobby",
              "risk_indicators": ["exposed_wiring", "electric_sparks"], "common_area_hazard": True}
    result = logic_manager.process_fault(report)
    print(result)
    check("accepted", result["accepted"], True)
    check("severity", result["severity_score"], 8)
    check("priority", result["priority"], "EMERGENCY")
    check("contractor", result["contractor"], "Electrical Contractor")
    check("sla", result["response_sla"], "Immediate action")


def test_emergency_vs_high():
    """Severity 8 is EMERGENCY in a common area, but only HIGH elsewhere."""
    for common_area, expected in [(True, "EMERGENCY"), (False, "HIGH")]:
        report = {"is_unclear": False, "fault_category": "electrical", "summary": "Sparks",
                  "risk_indicators": ["electric_sparks"], "common_area_hazard": common_area}
        result = logic_manager.process_fault(report)
        check(f"severity 8, common area {common_area}", result["severity_score"], 8)
        check(f"severity 8, common area {common_area} priority", result["priority"], expected)

def test_unclear_complaint():
    """Simulate the AI identifying a complaint as unclear."""
    unclear_report = {
        "is_unclear": True,
        "fault_category": "general maintenance",
        "summary": "Something is wrong",
        "risk_indicators": [],
        "common_area_hazard": False
    }

    result = logic_manager.process_fault(unclear_report)

    print("\n--- Unclear Complaint Test ---")
    print("AI result:", unclear_report)
    print("Logic Manager result:", result)

    check("complaint rejected", result["accepted"], False)
    check(
        "asks for clearer details",
        result["reason"],
        "Please resubmit with clearer details about the fault and its location."
    )

def test_fire_emergency():
    """Fire must trigger emergency instructions regardless of location."""
    report = {
        "is_unclear": False,
        "fault_category": "general maintenance",
        "summary": "Fire reported in an apartment",
        "risk_indicators": ["fire"],
        "common_area_hazard": False
    }

    result = logic_manager.process_fault(report)

    check("fire priority", result["priority"], "EMERGENCY")
    check("fire SLA", result["response_sla"], "Immediate action")
    check("SCDF instruction", "Call SCDF 995 immediately" in result["alert"], True)
    check("contractor role", result["contractor_role"], "Follow-up maintenance only")

def test_ai_unavailable():
    """Unavailable AI should send the report for manual review."""
    report = {"ai_available": False}

    result = logic_manager.process_fault(report)

    check("not accepted", result["accepted"], False)
    check("manual review", result["manual_input_required"], True)
    check("review status", result["status"], "Pending Manual Review")
    

if __name__ == "__main__":
    test_authenticate_admin()
    test_severity()
    test_priority()
    test_contractor()
    test_sla()
    test_alert()
    test_process_fault()
    test_emergency_vs_high()
    test_invalid_ai_result()
    test_unclear_complaint()
    test_fire_emergency()
    test_ai_unavailable()
    print("All tests passed!")