from __future__ import annotations

from typing import List

from .base_grader import BaseGrader


class EasyGrader(BaseGrader):
    """
    Scores the easy_missing_docs task (CPT 72148 Lumbar MRI).

    Optimal path (3 steps):
      1. submit_auth_request → info_requested (CO-197, needs clinical_notes)
      2. get_patient_records(clinical_notes) + submit_supporting_docs → approved
      3. resolve

    Score breakdown (max = 1.00):
      approval        0.45   payer approved
      docs            0.25   fraction of correct docs submitted
      speed           0.15   step efficiency
      efficiency      0.10   low unnecessary-action count
      resolved        0.05   explicit resolve() call
    Total possible:   1.00

    A perfect run (3 steps, approval, all docs, resolve, 0 unnecessary):
      0.45 + 0.25 + 0.15*(8-3)/8 + 0.10 + 0.05 = 0.45+0.25+0.09+0.10+0.05 = 0.94
    Normalized: ~1.00 (clamped).
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

        # ── Approval (0.45) ──────────────────────────────────────────────────
        if payer_status == "approved":
            raw += 0.45

        # ── Documentation (0.25) ─────────────────────────────────────────────
        required = self.scenario.get("correct_docs_required", [])
        docs_correct = sum(1 for doc in required if doc in submitted_docs)
        if required:
            raw += 0.25 * (docs_correct / len(required))

        # ── Speed (0.15) ─────────────────────────────────────────────────────
        if step_limit > 0:
            speed = max(0.0, (step_limit - step_count) / step_limit)
            raw += 0.15 * speed

        # ── Efficiency (0.10) ────────────────────────────────────────────────
        if unnecessary_actions == 0:
            raw += 0.10
        elif unnecessary_actions <= 1:
            raw += 0.07
        elif unnecessary_actions <= 3:
            raw += 0.03

        # ── Resolve bonus (0.05) ─────────────────────────────────────────────
        if resolved:
            raw += 0.05

        return max(0.0, min(1.0, raw))
