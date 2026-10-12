# Provisional project rules: adjust these values when the team agrees its policy.
ADMIN_USERNAME = "admin123"
ADMIN_PASSWORD = "password123"


def authenticate_admin(username, password):
    """Return True only when both values match the hardcoded demo account.

    Accept username and password strings. This simple local-project login
    does not create accounts or store session data on disk.
    """

    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


RISK_SCORES = {
    "fire": 9,
    "smoke": 8,
    "trapped_person": 9,
    "exposed_wiring": 6,
    "electric_sparks": 8,
    "flooding": 6,
    "active_leak": 3,
    "trip_hazard": 3,
    "service_outage": 4,
}


def determine_severity(ai_result):
    """Calculate an integer severity score from validated AI risk indicators.

    Look up each hazard in RISK_SCORES and return the highest score.
    Return 1 for routine maintenance when no hazards are listed.
    """

    severity = 1
    for risk in ai_result["risk_indicators"]:
        severity = max(severity, RISK_SCORES[risk])
    return severity


def determine_priority(ai_result):
    """Return priority from hazards, severity and whether a common area is affected.

    Reported fire is always EMERGENCY, including inside a private apartment.
    Other scores of at least 8 with a common-area hazard give EMERGENCY.
    Otherwise, scores of at least 6 give HIGH, at least 3 give MEDIUM,
    and lower scores give LOW.
    """

    severity = ai_result["severity_score"]
    hazard = ai_result["common_area_hazard"]

    if "fire" in ai_result.get("risk_indicators", []) or (severity >= 8 and hazard):
        return "EMERGENCY"

    elif severity >= 6:
        return "HIGH"

    elif severity >= 3:
        return "MEDIUM"

    else:
        return "LOW"

def assign_contractor(ai_result):
    """Return the contractor name matching the report's fault_category.

    Route plumbing, electrical, and lift faults to their specialist teams.
    Use the General Maintenance Contractor for other categories.
    """

    category = ai_result["fault_category"]

    contractors = {
        "plumbing": "Plumbing Contractor",
        "electrical": "Electrical Contractor",
        "lift": "Lift Maintenance Contractor",
        "general maintenance": "General Maintenance Contractor",
    }

    return contractors.get(category, "General Maintenance Contractor")


def calculate_sla(priority):
    """Convert a priority label into a response-time target string.

    Return 'Immediate action' for EMERGENCY, '4 hours' for HIGH, '24 hours'
    for MEDIUM, and '72 hours' otherwise. These are project action targets,
    not promises about emergency-service arrival times.
    """

    if priority == "EMERGENCY":
        return "Immediate action"

    elif priority == "HIGH":
        return "4 hours"

    elif priority == "MEDIUM":
        return "24 hours"

    else:
        return "72 hours"


def create_alert(ai_result, priority, contractor, sla):
    """Build and return a readable maintenance alert without printing it.

    Combine the report's issue_summary with the supplied priority,
    contractor name, and response-time target (sla) into a multiline string.
    """

    emergency_action = ai_result.get("emergency_action")
    heading = f"EMERGENCY: {emergency_action}\n" if emergency_action else ""
    contractor_label = "Follow-up maintenance contractor" if emergency_action else "Contractor"
    return heading + (
        f"Priority: {priority}\n"
        f"{contractor_label}: {contractor}\n"
        f"Response SLA: {sla}\n"
        f"Issue: {ai_result['issue_summary']}"
    )


def process_fault(ai_result):
    """Apply the business rules to a validated AI report dictionary.

    Return a manual-review marker when AI is unavailable, or accepted=False
    and a clarification reason for unclear reports.
    Otherwise, return accepted=True with the summary, hazards, severity,
    priority, contractor, response SLA, and alert for the complaint record.
    """

    if ai_result.get("ai_available") is False:
        return {
            "accepted": False,
            "manual_input_required": True,
            "status": "Pending Manual Review",
            "reason": "AI analysis is unavailable. An admin must review this complaint.",
        }

    if ai_result["is_unclear"]:
        return {
            "accepted": False,
            "reason": "Please resubmit with clearer details about the fault and its location.",
        }

    enriched = {
        "severity_score": determine_severity(ai_result),
        "common_area_hazard": ai_result["common_area_hazard"],
        "issue_summary": ai_result["summary"],
        "risk_indicators": list(ai_result["risk_indicators"]),
    }
    if "fire" in ai_result["risk_indicators"]:
        enriched["emergency_action"] = (
            "Call SCDF 995 immediately. Do not wait for a maintenance contractor. "
            "This application does not contact emergency services."
        )
    priority = determine_priority(enriched)
    contractor = assign_contractor(ai_result)
    sla = calculate_sla(priority)
    alert = create_alert(enriched, priority, contractor, sla)

    processed = {
        "accepted": True,
        "fault_category": ai_result["fault_category"],
        "severity_score": enriched["severity_score"],
        "common_area_hazard": ai_result["common_area_hazard"],
        "issue_summary": ai_result["summary"],
        "risk_indicators": list(ai_result["risk_indicators"]),
        "is_unclear": False,
        "priority": priority,
        "contractor": contractor,
        "response_sla": sla,
        "alert": alert
    }
    if "emergency_action" in enriched:
        processed["emergency_action"] = enriched["emergency_action"]
        processed["contractor_role"] = "Follow-up maintenance only"
    return processed