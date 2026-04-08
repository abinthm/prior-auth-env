"""
inference.py - Baseline Prior Auth Agent
=========================================
Mandatory stdout format (one line each, no newlines within a line):

    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

Environment variables:
    API_BASE_URL   The API endpoint for the LLM (default: HF router)
    MODEL_NAME     The model identifier
    HF_TOKEN       Your Hugging Face / API key
    OPENENV_SERVER_URL  WebSocket URL of the running env (default: ws://localhost:7860)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import textwrap
import time
from pathlib import Path
from typing import List, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from openai import OpenAI

from prior_auth_env import PriorAuthAction, PriorAuthEnv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Configuration ────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")
HF_TOKEN     = os.getenv("HF_TOKEN")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
SERVER_URL   = os.getenv("OPENENV_SERVER_URL", "ws://localhost:7860")
BENCHMARK    = "prior_auth_env"

TASKS        = ["easy_missing_docs", "step_therapy_required", "medical_necessity_dispute"]
TEMPERATURE  = 0.1
MAX_TOKENS   = 512
MAX_HISTORY  = 8    # message pairs kept in LLM context
MAX_STEPS    = 30   # hard cap per episode

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an expert RCM (Revenue Cycle Management) specialist handling prior
    authorization requests for a medical practice. Your goal is to obtain
    insurance approval as efficiently as possible.

    AVAILABLE ACTIONS — respond with ONLY valid JSON matching one of these exactly:
    {"action_type": "submit_auth_request",       "params": {"procedure_code": "72148", "diagnosis_code": "M54.5"}}
    {"action_type": "get_patient_records",        "params": {"record_type": "clinical_notes", "days_back": 90}}
    {"action_type": "get_denial_details",         "params": {}}
    {"action_type": "check_payer_criteria",       "params": {}}
    {"action_type": "submit_supporting_docs",     "params": {"doc_type": "clinical_notes"}}
    {"action_type": "submit_appeal",              "params": {"appeal_type": "formal_written", "rationale": "..."}}
    {"action_type": "request_peer_to_peer",       "params": {"urgency": "routine"}}
    {"action_type": "prepare_clinical_summary",   "params": {"key_findings": ["finding1", "finding2"]}}
    {"action_type": "submit_peer_to_peer_summary","params": {"content": "..."}}
    {"action_type": "check_auth_status",          "params": {}}
    {"action_type": "escalate_to_external_review","params": {}}
    {"action_type": "resolve",                    "params": {"outcome": "approved", "notes": "brief summary"}}

    RULES:
    - Always call submit_auth_request first.
    - After a denial, get_denial_details and check_payer_criteria before acting.
    - Retrieve a record with get_patient_records before submitting it.
    - Call resolve when the authorization is APPROVED or when you have exhausted options.
    - Output ONLY the JSON object — no explanation, no markdown.
    """
).strip()


# ── Logging helpers (mandatory competition format) ────────────────────────────
def log_start(task: str, model: str) -> None:
    print(f"[START] task={task} env={BENCHMARK} model={model}", flush=True)


def log_step(
    step: int,
    action: str,
    reward: float,
    done: bool,
    error: Optional[str],
) -> None:
    error_val = error if error else "null"
    done_val  = "true" if done else "false"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f}"
        f" done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    success_val = "true" if success else "false"
    print(
        f"[END] success={success_val} steps={steps}"
        f" score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


# ── Observation formatter ─────────────────────────────────────────────────────
def format_observation(obs, step: int) -> str:
    lines = [
        f"=== STEP {step} | {obs.steps_remaining} steps remaining ===",
        f"GOAL: {obs.goal}",
        "",
        (
            f"PATIENT: {obs.patient_summary.get('name', '?')} | "
            f"Payer: {obs.patient_summary.get('payer', '?')} | "
            f"Member ID: {obs.patient_summary.get('member_id', '?')}"
        ),
        "",
        f"CURRENT STATUS: {obs.payer_status.upper()}",
        f"PAYER RESPONSE: {obs.payer_response}",
    ]
    if obs.denial_reason:
        lines.append(f"DENIAL REASON: {obs.denial_reason}")
    if obs.denial_reason_code:
        lines.append(f"DENIAL CODE: {obs.denial_reason_code}")
    if obs.submitted_documents:
        lines.append(f"DOCUMENTS SUBMITTED: {', '.join(obs.submitted_documents)}")
    if obs.retrieved_records:
        lines.append(f"RECORDS RETRIEVED: {', '.join(obs.retrieved_records.keys())}")
    if obs.appeal_stage > 0:
        lines.append(f"APPEAL STAGE: {obs.appeal_stage}")
    if obs.reward is not None:
        lines.append(f"LAST REWARD: {float(obs.reward):+.3f}")
    return "\n".join(lines)


# ── Action parsing ────────────────────────────────────────────────────────────
def parse_action(text: str) -> PriorAuthAction:
    text = text.strip()
    # Strip code fences if present
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    try:
        data = json.loads(text)
        return PriorAuthAction(
            action_type=data.get("action_type", "check_auth_status"),
            params=data.get("params", {}),
        )
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                return PriorAuthAction(
                    action_type=data.get("action_type", "check_auth_status"),
                    params=data.get("params", {}),
                )
            except json.JSONDecodeError:
                pass
    return PriorAuthAction(action_type="check_auth_status", params={})


# ── Fallback (deterministic) policy ──────────────────────────────────────────
_PROC_DIAG = {
    "easy_missing_docs":        ("72148",  "M54.5"),
    "step_therapy_required":    ("J0135",  "M06.09"),
    "medical_necessity_dispute":("22612",  "M43.16"),
}


def fallback_policy(task_name: str, obs) -> PriorAuthAction:
    """Rule-based policy that partially solves each task without an LLM."""
    if obs.done:
        return PriorAuthAction(action_type="check_auth_status", params={})

    # --- Step 0: always submit auth first ---
    if obs.step_number == 0:
        proc, diag = _PROC_DIAG[task_name]
        return PriorAuthAction(
            action_type="submit_auth_request",
            params={"procedure_code": proc, "diagnosis_code": diag},
        )

    # ── EASY: missing documentation ───────────────────────────────────────────
    if task_name == "easy_missing_docs":
        if "clinical_notes" not in obs.retrieved_records:
            return PriorAuthAction(
                action_type="get_patient_records",
                params={"record_type": "clinical_notes", "days_back": 90},
            )
        if "clinical_notes" not in obs.submitted_documents:
            return PriorAuthAction(
                action_type="submit_supporting_docs",
                params={"doc_type": "clinical_notes"},
            )
        if obs.payer_status == "approved":
            return PriorAuthAction(
                action_type="resolve",
                params={"outcome": "approved", "notes": "clinical_notes accepted, authorization granted"},
            )
        return PriorAuthAction(action_type="check_auth_status", params={})

    # ── MEDIUM: step therapy ──────────────────────────────────────────────────
    if task_name == "step_therapy_required":
        if "medication_history" not in obs.retrieved_records:
            return PriorAuthAction(
                action_type="get_patient_records",
                params={"record_type": "medication_history", "days_back": 365},
            )
        if "medication_history" not in obs.submitted_documents:
            return PriorAuthAction(
                action_type="submit_supporting_docs",
                params={"doc_type": "medication_history"},
            )
        if "visit_notes" not in obs.retrieved_records:
            return PriorAuthAction(
                action_type="get_patient_records",
                params={"record_type": "visit_notes", "days_back": 180},
            )
        if "visit_notes" not in obs.submitted_documents:
            return PriorAuthAction(
                action_type="submit_supporting_docs",
                params={"doc_type": "visit_notes"},
            )
        if obs.payer_status == "approved":
            return PriorAuthAction(
                action_type="resolve",
                params={"outcome": "approved", "notes": "step therapy documented, authorization granted"},
            )
        return PriorAuthAction(action_type="check_auth_status", params={})

    # ── HARD: medical necessity dispute ───────────────────────────────────────
    if task_name == "medical_necessity_dispute":
        if obs.payer_status in ("denied", "info_requested") and "imaging" not in obs.retrieved_records:
            return PriorAuthAction(
                action_type="get_patient_records",
                params={"record_type": "imaging"},
            )
        if obs.payer_status in ("denied", "info_requested") and "functional_assessment" not in obs.retrieved_records:
            return PriorAuthAction(
                action_type="get_patient_records",
                params={"record_type": "functional_assessment"},
            )
        if obs.payer_status in ("denied", "info_requested") and "clinical_notes" not in obs.retrieved_records:
            return PriorAuthAction(
                action_type="get_patient_records",
                params={"record_type": "clinical_notes"},
            )
        for doc in ["imaging", "functional_assessment", "clinical_notes"]:
            if doc in obs.retrieved_records and doc not in obs.submitted_documents:
                return PriorAuthAction(
                    action_type="submit_supporting_docs",
                    params={"doc_type": doc},
                )
        if obs.appeal_stage == 0 and obs.payer_status in ("denied", "info_requested"):
            return PriorAuthAction(
                action_type="submit_appeal",
                params={
                    "appeal_type": "formal_written",
                    "rationale": (
                        "Patient meets all criteria for L4-L5 fusion: Grade II spondylolisthesis "
                        "confirmed on MRI, ODI 62% severe disability, 18 months failed conservative "
                        "care including PT, ESIs x3, and medications. Surgical intervention is the "
                        "only remaining option."
                    ),
                },
            )
        if obs.appeal_stage == 1:
            return PriorAuthAction(
                action_type="request_peer_to_peer",
                params={"urgency": "routine"},
            )
        if obs.appeal_stage == 2:
            return PriorAuthAction(
                action_type="prepare_clinical_summary",
                params={
                    "key_findings": [
                        "Grade II L4/L5 spondylolisthesis on MRI 2024-01-08",
                        "ODI score 62% — severe disability class",
                        "18 months conservative care: PT x 24 weeks, ESI x3, gabapentin + meloxicam",
                        "All conservative measures failed — no functional improvement",
                        "Orthopedic surgeon attestation: surgical intervention required",
                    ]
                },
            )
        if obs.appeal_stage == 2 and "clinical_summary" in obs.retrieved_records:
            return PriorAuthAction(
                action_type="submit_peer_to_peer_summary",
                params={"content": "Clinical summary submitted per peer-to-peer review request"},
            )
        if obs.appeal_stage >= 3:
            return PriorAuthAction(
                action_type="escalate_to_external_review",
                params={},
            )
        if obs.payer_status == "approved":
            return PriorAuthAction(
                action_type="resolve",
                params={
                    "outcome": "approved",
                    "notes": "Authorization obtained after peer-to-peer review",
                },
            )
        return PriorAuthAction(action_type="check_auth_status", params={})

    return PriorAuthAction(action_type="check_auth_status", params={})


# ── LLM action selection ──────────────────────────────────────────────────────
def choose_action(
    task_name: str,
    obs,
    history: List[dict],
    llm: Optional[OpenAI],
) -> tuple[PriorAuthAction, Optional[str]]:
    """Returns (action, error_string_or_None)."""
    if llm is None:
        return fallback_policy(task_name, obs), None

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
    try:
        completion = llm.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        response_text = completion.choices[0].message.content or "{}"
        return parse_action(response_text), None
    except Exception as exc:
        return fallback_policy(task_name, obs), str(exc)


# ── Episode runner ────────────────────────────────────────────────────────────
async def run_task(task_name: str, env: PriorAuthEnv, llm: Optional[OpenAI]) -> float:
    """Run one full episode; returns final score in [0, 1]."""
    result = await env.reset(task_name=task_name)
    obs    = result.observation

    history: List[dict] = []
    rewards: List[float] = []
    steps_taken = 0
    score        = 0.0
    success      = False

    log_start(task=task_name, model=MODEL_NAME)

    try:
        for step in range(1, MAX_STEPS + 1):
            if obs.done:
                break

            obs_text = format_observation(obs, step)
            history.append({"role": "user", "content": obs_text})
            if len(history) > MAX_HISTORY * 2:
                history = history[-(MAX_HISTORY * 2):]

            action, err = choose_action(task_name, obs, history, llm)
            history.append({"role": "assistant", "content": json.dumps(action.model_dump())})

            result = await env.step(action)
            obs    = result.observation
            reward = float(result.reward or 0.0)
            done   = bool(obs.done)

            rewards.append(reward)
            steps_taken = step

            log_step(
                step=step,
                action=action.action_type,
                reward=reward,
                done=done,
                error=err,
            )

            if done:
                break

        # Final score is the last reward when done==True (grader terminal score)
        score   = float(obs.reward or 0.0) if rewards else 0.0
        score   = max(0.0, min(1.0, score))
        success = score >= 0.5

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


# ── Main ──────────────────────────────────────────────────────────────────────
async def amain() -> None:
    llm    = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN) if HF_TOKEN else None
    scores: dict[str, float] = {}

    async with PriorAuthEnv(base_url=SERVER_URL) as env:
        for task in TASKS:
            t0 = time.monotonic()
            try:
                score = await run_task(task, env, llm)
            except Exception as exc:
                print(f"[DEBUG] Task '{task}' failed: {exc}", flush=True)
                score = 0.0
            scores[task] = score
            elapsed = time.monotonic() - t0
            print(f"[DEBUG] {task} => {score:.4f} ({elapsed:.1f}s)", flush=True)

    mean = sum(scores.values()) / len(scores)
    print(f"\n{'=' * 60}", flush=True)
    print("  FINAL SCORES", flush=True)
    print(f"{'=' * 60}", flush=True)
    for task, s in scores.items():
        bar = "█" * int(s * 20) + "░" * (20 - int(s * 20))
        print(f"  {task:<32} {bar} {s:.4f}", flush=True)
    print(f"  {'MEAN':<32} {'─' * 20} {mean:.4f}", flush=True)
    print(f"{'=' * 60}\n", flush=True)


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
