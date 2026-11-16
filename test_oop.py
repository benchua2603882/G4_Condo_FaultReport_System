"""Offline checks for class contracts and dependency injection.

Run with python -m unittest -v test_oop. No API requests or real reports used.
"""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ai_manager import AIManager, AnalysisSchema
from application import ReportApplication
from authentication import DemoAuthenticator
from contracts import AnalysisProvider, PriorityRule, ReportReader, ReportWriter
from data_manager import JsonReportRepository
from io_manager import IOManager
from logic_manager import EmergencyPriorityRule, LogicManager, ScorePriorityRule


class SampleProvider(AnalysisProvider):
    """Test-only provider; production always uses GeminiProvider."""

    def __init__(self, response):
        """Keep a sample response and a record of requests for assertions."""
        self._response = deepcopy(response)
        self.calls = []

    def request_analysis(self, complaint):
        """Return independent parsed data under the same provider contract."""
        self.calls.append(deepcopy(complaint))
        return deepcopy(self._response)


class UnavailableProvider(AnalysisProvider):
    """Test-only provider demonstrating the allowed exception outcome."""

    def request_analysis(self, complaint):
        """Simulate an API timeout without a network connection."""
        raise TimeoutError("private server detail")


class OOPTests(unittest.TestCase):
    """Verify substitutability, encapsulation and independent object lifetimes."""

    def setUp(self):
        """Prepare isolated storage and the original sample leak classification."""
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "reports.json"
        self.analysis = {
            "fault_category": "plumbing", "summary": "Pipe leaking in corridor.",
            "risk_indicators": ["active_leak"], "common_area_hazard": True,
            "is_unclear": False,
        }

    def make_app(self, provider):
        """Inject the provider and a terminal with deterministic resident answers."""
        answers = iter(["Test Resident", "91234567", "Pipe leaking", "n"])
        self.messages = []
        self.repository = JsonReportRepository(self.path)
        return ReportApplication(
            IOManager(reader=lambda prompt: next(answers), writer=self.messages.append),
            AIManager(provider), LogicManager(), self.repository, DemoAuthenticator(),
        )

    def test_abstract_contracts_require_implementations(self):
        """An unfinished provider, repository or priority rule cannot be used."""
        for contract in (AnalysisProvider, PriorityRule, ReportReader, ReportWriter):
            with self.subTest(contract=contract.__name__), self.assertRaises(TypeError):
                contract()

    def test_injected_provider_runs_real_pipeline(self):
        """The same controller runs with an alternate provider without branches."""
        provider = SampleProvider(self.analysis)
        report = self.make_app(provider).process_new_report()
        self.assertEqual(provider.calls[0], report[:6])
        self.assertEqual(report[6]["severity_score"], 3)
        self.assertEqual(report[6]["status"], "Pending Action")
        self.assertEqual(JsonReportRepository(self.path).load_reports(), [report])

    def test_provider_timeout_preserves_manual_review(self):
        """Substitution with a failing provider keeps the existing fallback."""
        with patch("ai_manager.logging.getLogger"):
            report = self.make_app(UnavailableProvider()).process_new_report()
        self.assertEqual(report[6]["status"], "Pending Manual Review")
        self.assertNotIn("private server detail", self.path.read_text())
        with self.assertRaises(ValueError):
            self.repository.update_complaint_status(report[0], "Resolved")

    def test_schema_validation_cannot_be_bypassed_by_provider(self):
        """A provider must still pass validation before domain rules use data."""
        with patch("ai_manager.logging.getLogger"):
            report = self.make_app(SampleProvider({"summary": "incomplete"})).process_new_report()
        self.assertEqual(report[6]["status"], "Pending Manual Review")
        self.assertNotIn("severity_score", report[6])

    def test_unclear_provider_output_is_not_saved(self):
        """A valid rejection remains different from an unavailable provider."""
        self.analysis["is_unclear"] = True
        result = self.make_app(SampleProvider(self.analysis)).process_new_report()
        self.assertIsNone(result)
        self.assertFalse(self.path.exists())

    def test_repositories_have_independent_storage(self):
        """Two instances never share mutable global REPORTS_FILE state."""
        first = JsonReportRepository(self.path)
        other = JsonReportRepository(self.path.with_name("other.json"))
        details = LogicManager().process_fault(self.analysis)
        report = ["complaint_001", "Test", "91234567", "Leak", "no_image", "time", details]
        first.save_report(report)
        self.assertEqual(first.get_next_complaint_id(), "complaint_002")
        self.assertEqual(other.load_reports(), [])
        self.assertEqual(other.get_next_complaint_id(), "complaint_001")
        with self.assertRaises(AttributeError):
            first.reports_file = other.reports_file

    def test_owned_schema_is_not_mutated_by_callers(self):
        """Copies and immutable choices protect each schema's configuration."""
        first, second = AnalysisSchema(), AnalysisSchema()
        external = first.response_schema
        external["required"].clear()
        external["properties"]["fault_category"]["enum"].clear()
        self.assertEqual(first.validate_response(self.analysis), self.analysis)
        self.assertEqual(second.validate_response(self.analysis), self.analysis)
        self.assertIsInstance(first.categories, tuple)

    def test_priority_rules_share_one_non_mutating_contract(self):
        """Both concrete rule types accept the same enriched dictionary."""
        report = {"severity_score": 9, "common_area_hazard": False, "risk_indicators": ["fire"]}
        before = deepcopy(report)
        for rule, expected in [(EmergencyPriorityRule(), "EMERGENCY"), (ScorePriorityRule(6, "HIGH"), "HIGH")]:
            with self.subTest(rule=type(rule).__name__):
                self.assertEqual(rule.evaluate(report), expected)
                self.assertEqual(report, before)
                self.assertIsNone(rule.evaluate({"severity_score": 1, "common_area_hazard": False, "risk_indicators": []}))

    def test_rule_aggregation_keeps_independent_objects(self):
        """One independently created rule can serve multiple managers."""
        rule = ScorePriorityRule(3, "MEDIUM")
        rules = [rule]
        first, second = LogicManager(rules), LogicManager(rules)
        rules.clear()
        report = {"severity_score": 3, "common_area_hazard": False, "risk_indicators": []}
        self.assertEqual(first.determine_priority(report), "MEDIUM")
        self.assertEqual(second.determine_priority(report), "MEDIUM")
        self.assertEqual(rule.evaluate(report), "MEDIUM")

    def test_corrupt_storage_stays_unchanged(self):
        """The repository contract exposes corruption without silently resetting."""
        self.path.write_text("{broken", encoding="utf-8")
        repository = JsonReportRepository(self.path)
        with self.assertRaises(json.JSONDecodeError):
            repository.get_next_complaint_id()
        self.assertEqual(self.path.read_text(), "{broken")


if __name__ == "__main__":
    unittest.main()
