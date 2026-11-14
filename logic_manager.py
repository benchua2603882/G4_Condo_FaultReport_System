"""Fault rules and priorities, independent of terminal, storage and Gemini."""


class EmergencyPriorityRule:
    """Specialise priority selection for fire or severe shared-area hazards."""

    def evaluate(self, report):
        """Return EMERGENCY for the original multi-condition emergency rule."""
        if "fire" in report.get("risk_indicators", []) or (
            report["severity_score"] >= 8 and report["common_area_hazard"]
        ):
            return "EMERGENCY"
        return None


class ScorePriorityRule:
    """Select a priority when severity reaches a configured minimum."""

    def __init__(self, minimum, priority):
        """Store one threshold and its result without changing application rules."""
        self._minimum = minimum
        self._priority = priority

    def evaluate(self, report):
        """Return the configured label or None when the rule does not apply."""
        return self._priority if report["severity_score"] >= self._minimum else None


class LogicManager:
    """Aggregate independent priority rules and apply the existing fault policy."""

    def __init__(self, priority_rules=None):
        """Use supplied rule objects or the unchanged Part 1 priority sequence."""
        self._priority_rules = tuple(priority_rules) if priority_rules is not None else (
            EmergencyPriorityRule(), ScorePriorityRule(6, "HIGH"),
            ScorePriorityRule(3, "MEDIUM"),
        )
        self._risk_scores = {
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

    def determine_severity(self, ai_result):
        """Calculate an integer severity score from validated AI risk indicators.

        Look up each hazard in the stored risk scores and return the highest score.
        Return 1 for routine maintenance when no hazards are listed.
        """

        severity = 1
        for risk in ai_result["risk_indicators"]:
            severity = max(severity, self._risk_scores[risk])
        return severity

    def determine_priority(self, ai_result):
        """Use the first matching rule; rules share the same non-mutating contract."""
        for rule in self._priority_rules:
            result = rule.evaluate(ai_result)
            if result is not None:
                return result
        return "LOW"

    def assign_contractor(self, ai_result):
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

    def calculate_sla(self, priority):
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

    def create_alert(self, ai_result, priority, contractor, sla):
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

    def process_fault(self, ai_result):
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
            "severity_score": self.determine_severity(ai_result),
            "common_area_hazard": ai_result["common_area_hazard"],
            "issue_summary": ai_result["summary"],
            "risk_indicators": list(ai_result["risk_indicators"]),
        }
        if "fire" in ai_result["risk_indicators"]:
            enriched["emergency_action"] = (
                "Call SCDF 995 immediately. Do not wait for a maintenance contractor. "
                "This application does not contact emergency services."
            )
        priority = self.determine_priority(enriched)
        contractor = self.assign_contractor(ai_result)
        sla = self.calculate_sla(priority)
        alert = self.create_alert(enriched, priority, contractor, sla)

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