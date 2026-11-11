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

            

