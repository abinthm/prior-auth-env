from __future__ import annotations

from typing import List

from .base_grader import BaseGrader


class MediumGrader(BaseGrader):
    """
    Scores the step_therapy_required task (Humira adalimumab J0135).

    Optimal path (5–6 steps):
      1. submit_auth_request → denied (CO-167, needs medication_history)
      2. get + submit medication_history → denied again (needs visit_notes)
      3. get + submit visit_notes → approved
      4. resolve

    Score breakdown (max = 1.00):
      approval        0.40   payer approved
      docs            0.30   weighted by required doc count (2 docs)
      denial_nav      0.10   agent correctly navigated 2+ denial stages
      speed           0.10   step efficiency bonus
      efficiency      0.07   unnecessary-action penalty
      resolved        0.03   explicit resolve() call
    Total possible:   1.00

    Partial credit design:
      - Submitting 1/2 required docs gives 0.15 (50% of doc score)
      - Navigating the first denial gives 0.10 even without approval
      - This gives agents meaningful gradient throughout a medium episode
    """

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

        # ── Approval (0.40) ──────────────────────────────────────────────────
        if payer_status == "approved":
            raw += 0.40

        # ── Documentation (0.30) — partial credit per doc ──────────────────
        required = self.scenario.get("correct_docs_required", [])
        docs_correct = sum(1 for doc in required if doc in submitted_docs)
        if required:
            raw += 0.30 * (docs_correct / len(required))

        # ── Denial navigation (0.10) — reward understanding the workflow ────
        # The medium task requires navigating 2 denial stages successfully.
        # Partial: 0.05 for first denial navigated, 0.10 for both.
        if denial_count >= 2:
            raw += 0.10
        elif denial_count >= 1:
            raw += 0.05

        # ── Speed (0.10) ─────────────────────────────────────────────────────
        if step_limit > 0:
            speed = max(0.0, (step_limit - step_count) / step_limit)
            raw += 0.10 * speed

        # ── Efficiency (0.07) ────────────────────────────────────────────────
        if unnecessary_actions == 0:
            raw += 0.07
        elif unnecessary_actions <= 2:
            raw += 0.04
        elif unnecessary_actions <= 4:
            raw += 0.01

        # ── Resolve bonus (0.03) ─────────────────────────────────────────────
        if resolved:
            raw += 0.03

        return max(0.0, min(1.0, raw))
