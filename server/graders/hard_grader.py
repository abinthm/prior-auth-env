from __future__ import annotations

from typing import List

from .base_grader import BaseGrader


class HardGrader(BaseGrader):
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
        raw = 0.0

        if payer_status == "approved":
            raw += 0.30

        required = self.scenario.get("correct_docs_required", [])
        docs_correct = sum(1 for doc in required if doc in submitted_docs)
        raw += 0.25 * (docs_correct / max(len(required), 1))

        if appeal_stage >= 1:
            raw += 0.15
        if appeal_stage >= 3:
            raw += 0.15

        if step_limit > 0:
            speed = max(0.0, (step_limit - step_count) / step_limit)
            raw += 0.10 * speed

        if unnecessary_actions <= 3:
            raw += 0.05

        if not resolved:
            raw -= 0.20

        return self.normalize(raw, max_possible=1.00, min_possible=-0.30)
