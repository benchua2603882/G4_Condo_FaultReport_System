"""Offline AI tests. Run with: python test_ai_manager.py"""

import json
import os
import unittest
from unittest.mock import patch

from ai_manager import AIManager

class AIManagerTests(unittest.TestCase):
    """Check AI response handling without calling Gemini."""

    def setUp(self):
            """Prepare sample data and replace the Gemini client."""
            self.complaint = [
                "complaint_001", "Test Resident", "91234567",
                "pipe leak at corridor", "no_image", "2026-11-11T10:00:00"
            ]
    
            self.valid = {
                "fault_category": "plumbing",
                "summary": "A pipe is leaking in the corridor.",
                "risk_indicators": ["active_leak"],
                "common_area_hazard": True,
                "is_unclear": False,
            }
    
            # Replace the external client so no real API request is sent.
            client_patch = patch("google.genai.Client")
            client_class = client_patch.start()
            self.addCleanup(client_patch.stop)
    
            client = client_class.return_value.__enter__.return_value
            self.generate = client.models.generate_content
    
            # Temporary test value, automatically restored after each test.
            env_patch = patch.dict(
                os.environ, {"GEMINI_API_KEY": "test-only"}
            )
            env_patch.start()
            self.addCleanup(env_patch.stop)
    
            self.manager = AIManager()

    def test_valid_response(self):
            """Accept a complete response and send only fault details."""
            self.generate.return_value.text = json.dumps(self.valid)
    
            result = self.manager.analyze_complaint(self.complaint)
    
            self.assertEqual(result, self.valid)
            self.generate.assert_called_once()
            self.assertEqual(
                self.generate.call_args.kwargs["contents"],
                ["Resident description: pipe leak at corridor"]
            )

    def test_api_errors(self):
            """Convert timeout and API errors into failure markers."""
            errors = [
                TimeoutError("Timed out"),
                RuntimeError("API failed"),
            ]
    
            for error in errors:
                with self.subTest(error=type(error).__name__):
                    self.generate.side_effect = error
    
                    with self.assertLogs("ai_manager", level="ERROR"):
                        result = self.manager.analyze_complaint(
                            self.complaint
                        )
    
                    self.assertEqual(result, {
                        "ai_available": False,
                        "error_type": type(error).__name__,
                    })

    def test_invalid_responses(self):
        """Reject empty, malformed and schema-invalid responses."""
        missing = self.valid.copy()
        del missing["summary"]

        cases = [
            ("empty", "", "ValueError"),
            ("malformed JSON", "{broken", "JSONDecodeError"),
            ("missing field", json.dumps(missing), "ValueError"),
            (
                "blank summary",
                json.dumps(dict(self.valid, summary=" ")),
                "ValueError",
            ),
            (
                "wrong type",
                json.dumps(dict(self.valid, risk_indicators="fire")),
                "ValueError",
            ),
            (
                "wrong boolean",
                json.dumps(dict(self.valid, is_unclear="false")),
                "ValueError",
            ),
            (
                "unknown category",
                json.dumps(dict(self.valid, fault_category="unknown")),
                "ValueError",
            ),
            (
                "unknown risk",
                json.dumps(dict(self.valid, risk_indicators=["unknown"])),
                "ValueError",
            ),
            (
                "extra field",
                json.dumps(dict(self.valid, severity_score=9)),
                "ValueError",
            ),
        ]

        for label, response, error_type in cases:
            with self.subTest(case=label):
                self.generate.return_value.text = response

                with self.assertLogs("ai_manager", level="ERROR"):
                    result = self.manager.analyze_complaint(
                        self.complaint
                    )

                self.assertEqual(result, {
                    "ai_available": False,
                    "error_type": error_type,
                })


if __name__ == "__main__":
    unittest.main(verbosity=2)

