"""Tests for logic_manager.py. Run with: python test_logic_manager.py"""

import logic_manager


def check(label, actual, expected):
    """Print a [PASS] or [FAIL] tag with the result, then compare them."""
    status = "PASS" if actual == expected else "FAIL"
    print(f"[{status}] {label} -> got {actual!r}, expected {expected!r}")
    assert actual == expected


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
    """Check each priority level, including the common-area rule."""
    cases = [(8, True, "EMERGENCY"), (8, False, "HIGH"), (6, False, "HIGH"),
             (3, False, "MEDIUM"), (1, False, "LOW")]
    for score, hazard, expected in cases:
        data = {"severity_score": score, "common_area_hazard": hazard}
        check(f"score {score}, common area {hazard}", logic_manager.determine_priority(data), expected)


def test_contractor():
    """Each category should go to the right contractor."""
    cases = [("plumbing", "Plumbing Contractor"), ("electrical", "Electrical Contractor"),
             ("lift", "Lift Maintenance Contractor"), ("other", "General Maintenance Contractor")]
    for category, expected in cases:
        check(category, logic_manager.assign_contractor({"fault_category": category}), expected)


def test_sla():
    """Each priority should give the right response time."""
    cases = [("EMERGENCY", "1 hour"), ("HIGH", "4 hours"), ("MEDIUM", "24 hours"), ("LOW", "72 hours")]
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
    check("sla", result["response_sla"], "1 hour")


def test_emergency_vs_high():
    """Severity 8 is EMERGENCY in a common area, but only HIGH elsewhere."""
    for common_area, expected in [(True, "EMERGENCY"), (False, "HIGH")]:
        report = {"is_unclear": False, "fault_category": "electrical", "summary": "Sparks",
                  "risk_indicators": ["electric_sparks"], "common_area_hazard": common_area}
        result = logic_manager.process_fault(report)
        check(f"severity 8, common area {common_area}", result["severity_score"], 8)
        check(f"severity 8, common area {common_area} priority", result["priority"], expected)


if __name__ == "__main__":
    test_authenticate_admin()
    test_severity()
    test_priority()
    test_contractor()
    test_sla()
    test_alert()
    test_process_fault()
    test_emergency_vs_high()
    print("All tests passed!")