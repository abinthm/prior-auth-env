from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class BaseGrader(ABC):
    """Shared normalization helpers for task graders."""

    def __init__(self, scenario: dict):
        self.scenario = scenario

    def normalize(self, raw: float, max_possible: float = 1.0, min_possible: float = -0.3) -> float:
        normalized = (raw - min_possible) / (max_possible - min_possible)
        # Strictly (0, 1) limits per Hackathon validator rules
        return max(0.01, min(0.99, normalized))

    @abstractmethod
    def compute_final_score(
        self,
        submitted_docs: List[str],
        payer_status: str,
        denial_count: int,
        appeal_stage: int,
        step_count: int,
        step_limit: int,
        unnecessary_actions: int,
        resolved: bool,
    ) -> float:
        raise NotImplementedError
