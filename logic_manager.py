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

    severity = 1
    for risk in ai_result["risk_indicators"]:
        severity = max(severity, RISK_SCORES[risk])
    return severity

test = {
    "risk_indicators": ["fire", "smoke"]
}

print(determine_severity(test))
print(determine_severity({"risk_indicators": ["active_leak"]}))
print(determine_severity({"risk_indicators": ["smoke", "flooding"]}))
print(determine_severity({"risk_indicators": []}))