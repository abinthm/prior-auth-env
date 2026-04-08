from __future__ import annotations

from typing import List

from .base_grader import BaseGrader


class HardGrader(BaseGrader):
    """
    Scores the medical-necessity-dispute task (CPT 22612 spinal fusion).

    The optimal path requires 4 distinct stages:
      1. Submit auth → Denied (CO-50)
      2. Gather 3 docs + submit appeal → Upheld
      3. Request P2P → prepare summary → submit P2P → Upheld again
      4. Escalate to IRO → Approved

    Score breakdown (max = 1.00 before normalization):
      approval        0.25   payer_status == "approved"
      docs            0.20   fraction of required docs submitted
      appeal          0.10   completed formal appeal (appeal_stage >= 1)
      p2p_complete    0.12   completed peer-to-peer (appeal_stage >= 3)
      escalation      0.13   reached external IRO (appeal_stage >= 4)
      speed           0.10   step efficiency bonus
      efficiency      0.05   low unnecessary-action penalty
      resolved        0.05   explicit resolve() call
    Total possible:   1.00

    Partial credit is awarded at every stage so agents get meaningful
    gradient signal throughout the episode.
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

        # ── Approval (0.25) ──────────────────────────────────────────────────
        if payer_status == "approved":
            raw += 0.25

        # ── Documentation quality (0.20) ────────────────────────────────────
        required = self.scenario.get("correct_docs_required", [])
        docs_correct = sum(1 for doc in required if doc in submitted_docs)
        if required:
            raw += 0.20 * (docs_correct / len(required))

        # ── Appeal milestones (partial progress rewards) ─────────────────────
        if appeal_stage >= 1:   # formal appeal submitted
            raw += 0.10
        if appeal_stage >= 3:   # peer-to-peer summary submitted
            raw += 0.12
        if appeal_stage >= 4:   # escalated to external IRO
            raw += 0.13

        # ── Speed bonus (0.10) ───────────────────────────────────────────────
        if step_limit > 0:
            speed = max(0.0, (step_limit - step_count) / step_limit)
            raw += 0.10 * speed

        # ── Efficiency bonus (0.05) ──────────────────────────────────────────
        if unnecessary_actions <= 3:
            raw += 0.05
        elif unnecessary_actions <= 6:
            raw += 0.02

        # ── Resolve bonus (0.05) ─────────────────────────────────────────────
        if resolved:
            raw += 0.05

        # Normalize into [0, 1]; max possible = 1.00, floor = 0.0
        return max(0.0, min(1.0, raw))
