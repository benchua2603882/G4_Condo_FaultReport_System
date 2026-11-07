"""Small contracts used by application orchestration and replaceable components.

Repositories return the existing seven-item JSON-compatible records and raise
ValueError for invalid operations, OSError for storage failures. Providers
return parsed dictionaries or raise; AIManager handles failure markers.
"""
from abc import ABC, abstractmethod
from typing import Protocol


class AnalysisProvider(ABC):
    """Boundary for one external analysis request; no domain decisions."""

    @abstractmethod
    def request_analysis(self, complaint: list) -> dict:
        """Return parsed provider output or raise on unavailable/invalid output."""
        raise NotImplementedError

