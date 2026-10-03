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
    """Return the highest risk score, or 1 for no hazards."""
    return max(
        (RISK_SCORES[risk] for risk in ai_result["risk_indicators"]),
        default=1,
    )


def determine_priority(ai_result):
    """Return priority based on severity and common-area hazard."""
    severity = ai_result["severity_score"]

    if severity >= 8 and ai_result["common_area_hazard"]:
        return "EMERGENCY"
    if severity >= 6:
        return "HIGH"
    if severity >= 3:
        return "MEDIUM"
    return "LOW"


def assign_contractor(ai_result):
    """Route the fault to the appropriate contractor."""
    contractors = {
        "plumbing": "Plumbing Contractor",
        "electrical": "Electrical Contractor",
        "lift": "Lift Maintenance Contractor",
        "general maintenance": "General Maintenance Contractor",
    }
    return contractors.get(
        ai_result["fault_category"],
        "General Maintenance Contractor",
    )


def calculate_sla(priority):
    """Return the response target for the priority."""
    sla = {
        "EMERGENCY": "1 hour",
        "HIGH": "4 hours",
        "MEDIUM": "24 hours",
        "LOW": "72 hours",
    }
    return sla.get(priority, "72 hours")