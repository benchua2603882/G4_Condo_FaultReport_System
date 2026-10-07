import logic_manager


def check(label, actual, expected):
    """Print the input/label, the actual result and the expected result, then assert."""
    status = "PASS" if actual == expected else "FAIL"
    print(f"  [{status}] {label}")
    print(f"         got:      {actual!r}")
    print(f"         expected: {expected!r}")
    assert actual == expected, f"{label}: expected {expected!r}, got {actual!r}"


def make_report(**overrides):
    """Build a valid AI report, overriding any fields needed."""
    report = {
        "is_unclear": False,
        "fault_category": "general maintenance",
        "summary": "Test summary",
        "risk_indicators": [],
        "common_area_hazard": False,
    }
    report.update(overrides)
    return report


def test_severity_scoring():
    print("\n--- determine_severity ---")
    test_cases = [
        ({"risk_indicators": ["fire", "active_leak"]}, 9),         # highest wins
        ({"risk_indicators": ["exposed_wiring"]}, 6),
        ({"risk_indicators": []}, 1),                              # no hazards
        ({"risk_indicators": ["trip_hazard", "service_outage"]}, 4),
    ]
    for input_data, expected in test_cases:
        result = logic_manager.determine_severity(input_data)
        check(f"input {input_data}", result, expected)


def test_priority_rules():
    print("\n--- determine_priority ---")
    cases = [
        ({"severity_score": 8, "common_area_hazard": True}, "EMERGENCY"),
        ({"severity_score": 8, "common_area_hazard": False}, "HIGH"),
        ({"severity_score": 6, "common_area_hazard": False}, "HIGH"),
        ({"severity_score": 3, "common_area_hazard": False}, "MEDIUM"),
        ({"severity_score": 1, "common_area_hazard": False}, "LOW"),
    ]
    for input_data, expected in cases:
        check(f"input {input_data}", logic_manager.determine_priority(input_data), expected)


def test_contractor_assignment():
    print("\n--- assign_contractor ---")
    cases = [
        ("electrical", "Electrical Contractor"),
        ("plumbing", "Plumbing Contractor"),
        ("lift", "Lift Maintenance Contractor"),
        ("other", "General Maintenance Contractor"),
    ]
    for category, expected in cases:
        result = logic_manager.assign_contractor({"fault_category": category})
        check(f"fault_category = {category!r}", result, expected)


def test_authenticate_admin():
    print("\n--- authenticate_admin ---")
    cases = [
        ("admin123", "password123", True),
        ("admin123", "wrongpass", False),
        ("wronguser", "password123", False),
        ("wronguser", "wrongpass", False),
        ("", "", False),
        ("ADMIN123", "password123", False),
        ("admin123", "PASSWORD123", False),
    ]
    for user, pw, expected in cases:
        result = logic_manager.authenticate_admin(user, pw)
        check(f"username={user!r}, password={pw!r}", result, expected)


def test_calculate_sla():
    print("\n--- calculate_sla ---")
    cases = [
        ("EMERGENCY", "1 hour"),
        ("HIGH", "4 hours"),
        ("MEDIUM", "24 hours"),
        ("LOW", "72 hours"),
        ("UNKNOWN", "72 hours"),
        ("", "72 hours"),
        ("emergency", "72 hours"),   # case sensitive
    ]
    for priority, expected in cases:
        check(f"priority = {priority!r}", logic_manager.calculate_sla(priority), expected)


def test_create_alert():
    print("\n--- create_alert ---")
    alert = logic_manager.create_alert(
        {"issue_summary": "Sparks coming from lobby wall panel"},
        "EMERGENCY", "Electrical Contractor", "1 hour",
    )
    print("  Alert produced:")
    for line in alert.splitlines():
        print(f"      | {line}")
    expected = (
        "Priority: EMERGENCY\n"
        "Contractor: Electrical Contractor\n"
        "Response SLA: 1 hour\n"
        "Issue: Sparks coming from lobby wall panel"
    )
    check("full alert text", alert, expected)
    check("number of lines", len(alert.splitlines()), 4)

    other = logic_manager.create_alert(
        {"issue_summary": "Dripping tap"}, "MEDIUM", "Plumbing Contractor", "24 hours"
    )
    check("second alert starts with priority", other.startswith("Priority: MEDIUM"), True)
    check("second alert ends with issue", other.endswith("Issue: Dripping tap"), True)


def test_process_fault_unclear():
    print("\n--- process_fault: unclear report ---")
    report = make_report(is_unclear=True)
    print(f"  Input: {report}")
    result = logic_manager.process_fault(report)
    print(f"  Output: {result}")
    check("accepted", result["accepted"], False)
    check("reason", result["reason"],
          "Please resubmit with clearer details about the fault and its location.")
    check("no 'priority' key", "priority" in result, False)
    check("no 'contractor' key", "contractor" in result, False)


def test_process_fault_accepted():
    print("\n--- process_fault: accepted emergency report ---")
    report = make_report(
        fault_category="electrical",
        summary="Sparks from lobby wall panel",
        risk_indicators=["exposed_wiring", "electric_sparks"],
        common_area_hazard=True,
    )
    print(f"  Input: {report}")
    result = logic_manager.process_fault(report)
    print("  Output:")
    for key, value in result.items():
        print(f"      {key}: {value!r}")

    check("accepted", result["accepted"], True)
    check("fault_category", result["fault_category"], "electrical")
    check("severity_score", result["severity_score"], 8)
    check("common_area_hazard", result["common_area_hazard"], True)
    check("issue_summary", result["issue_summary"], "Sparks from lobby wall panel")
    check("risk_indicators", result["risk_indicators"], ["exposed_wiring", "electric_sparks"])
    check("is_unclear", result["is_unclear"], False)
    check("priority", result["priority"], "EMERGENCY")
    check("contractor", result["contractor"], "Electrical Contractor")
    check("response_sla", result["response_sla"], "1 hour")
    check("alert", result["alert"],
          "Priority: EMERGENCY\n"
          "Contractor: Electrical Contractor\n"
          "Response SLA: 1 hour\n"
          "Issue: Sparks from lobby wall panel")


def test_process_fault_priority_levels():
    print("\n--- process_fault: priority levels ---")
    high_in = make_report(risk_indicators=["fire"], common_area_hazard=False)
    print(f"  HIGH input: {high_in}")
    high = logic_manager.process_fault(high_in)
    check("HIGH severity", high["severity_score"], 9)
    check("HIGH priority", high["priority"], "HIGH")
    check("HIGH sla", high["response_sla"], "4 hours")

    med_in = make_report(fault_category="plumbing", risk_indicators=["active_leak"])
    print(f"  MEDIUM input: {med_in}")
    medium = logic_manager.process_fault(med_in)
    check("MEDIUM severity", medium["severity_score"], 3)
    check("MEDIUM priority", medium["priority"], "MEDIUM")
    check("MEDIUM contractor", medium["contractor"], "Plumbing Contractor")
    check("MEDIUM sla", medium["response_sla"], "24 hours")

    low_in = make_report(risk_indicators=[])
    print(f"  LOW input: {low_in}")
    low = logic_manager.process_fault(low_in)
    check("LOW severity", low["severity_score"], 1)
    check("LOW priority", low["priority"], "LOW")
    check("LOW contractor", low["contractor"], "General Maintenance Contractor")
    check("LOW sla", low["response_sla"], "72 hours")


def test_process_fault_copies_risk_indicators():
    print("\n--- process_fault: risk list is a copy ---")
    original = ["flooding"]
    result = logic_manager.process_fault(make_report(risk_indicators=original))
    check("risk_indicators value", result["risk_indicators"], ["flooding"])
    check("is a different list object", result["risk_indicators"] is not original, True)


if __name__ == "__main__":
    while True:
        print("\n=== Logic Manager Tests ===")
        print("1. Test severity")
        print("2. Test priority")
        print("3. Test contractor")
        print("4. Test authentication")
        print("5. Test SLA")
        print("6. Test alert")
        print("7. Test process fault")
        print("8. Run all tests")
        print("0. Exit")

        choice = input("\nChoose a test: ")

        if choice == "1":
            test_severity_scoring()
            input("\nPress Enter to continue...")

        elif choice == "2":
            test_priority_rules()
            input("\nPress Enter to continue...")

        elif choice == "3":
            test_contractor_assignment()
            input("\nPress Enter to continue...")

        elif choice == "4":
            test_authenticate_admin()
            input("\nPress Enter to continue...")

        elif choice == "5":
            test_calculate_sla()
            input("\nPress Enter to continue...")

        elif choice == "6":
            test_create_alert()
            input("\nPress Enter to continue...")

        elif choice == "7":
            test_process_fault_unclear()
            test_process_fault_accepted()
            test_process_fault_priority_levels()
            input("\nPress Enter to continue...")

        elif choice == "8":
            test_severity_scoring()
            test_priority_rules()
            test_contractor_assignment()
            test_authenticate_admin()
            test_calculate_sla()
            test_create_alert()
            test_process_fault_unclear()
            test_process_fault_accepted()
            test_process_fault_priority_levels()
            test_process_fault_copies_risk_indicators()
            print("\nAll tests passed!")
            input("\nPress Enter to continue...")

        elif choice == "0":
            print("Exiting tests.")
            break

        else:
            print("Invalid choice.")