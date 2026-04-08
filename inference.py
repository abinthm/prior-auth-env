"""
inference.py - Baseline Prior Auth Agent
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
from typing import List

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI

from prior_auth_env import PriorAuthAction, PriorAuthEnv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

API_BASE_URL = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.environ.get("HF_TOKEN") or os.environ.get("API_KEY")
MODEL_NAME = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")
SERVER_URL = os.environ.get("OPENENV_SERVER_URL", "ws://localhost:7860")

TASKS = ["easy_missing_docs", "step_therapy_required", "medical_necessity_dispute"]
TEMPERATURE = 0.1
MAX_TOKENS = 512
MAX_HISTORY = 8

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an expert RCM (Revenue Cycle Management) specialist handling prior authorization
    requests for a medical practice. Your goal is to obtain insurance approval efficiently.

    AVAILABLE ACTIONS - respond with ONLY valid JSON, nothing else:
    {"action_type": "submit_auth_request", "params": {"procedure_code": "72148", "diagnosis_code": "M54.5"}}
    {"action_type": "get_patient_records", "params": {"record_type": "clinical_notes", "days_back": 90}}
    {"action_type": "get_denial_details", "params": {}}
    {"action_type": "check_payer_criteria", "params": {}}
    {"action_type": "submit_supporting_docs", "params": {"doc_type": "clinical_notes"}}
    {"action_type": "submit_appeal", "params": {"appeal_type": "formal_written", "rationale": "..."}}
    {"action_type": "request_peer_to_peer", "params": {"urgency": "routine"}}
    {"action_type": "prepare_clinical_summary", "params": {"key_findings": ["finding1", "finding2"]}}
    {"action_type": "submit_peer_to_peer_summary", "params": {"content": "..."}}
    {"action_type": "check_auth_status", "params": {}}
    {"action_type": "escalate_to_external_review", "params": {}}
    {"action_type": "resolve", "params": {"outcome": "approved", "notes": "brief summary"}}
    """
).strip()


def format_observation(obs, step: int) -> str:
    lines = [
        f"=== STEP {step} | {obs.steps_remaining} steps remaining ===",
        f"GOAL: {obs.goal}",
        "",
        f"PATIENT: {obs.patient_summary.get('name', '?')} | "
        f"Payer: {obs.patient_summary.get('payer', '?')} | "
        f"Member ID: {obs.patient_summary.get('member_id', '?')}",
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


def parse_action(text: str) -> PriorAuthAction:
    text = text.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    try:
        data = json.loads(text)
        return PriorAuthAction(action_type=data.get("action_type", "check_auth_status"), params=data.get("params", {}))
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


def fallback_policy(task_name: str, obs) -> PriorAuthAction:
    if obs.done:
        return PriorAuthAction(action_type="check_auth_status", params={})

    if obs.step_number == 0:
        proc = {
            "easy_missing_docs": ("72148", "M54.5"),
            "step_therapy_required": ("J0135", "M06.09"),
            "medical_necessity_dispute": ("22612", "M43.16"),
        }[task_name]
        return PriorAuthAction(
            action_type="submit_auth_request",
            params={"procedure_code": proc[0], "diagnosis_code": proc[1]},
        )

    if task_name == "easy_missing_docs":
        if "clinical_notes" not in obs.retrieved_records:
            return PriorAuthAction(action_type="get_patient_records", params={"record_type": "clinical_notes", "days_back": 90})
        if "clinical_notes" not in obs.submitted_documents:
            return PriorAuthAction(action_type="submit_supporting_docs", params={"doc_type": "clinical_notes"})
        return PriorAuthAction(action_type="resolve", params={"outcome": "approved", "notes": "submitted clinical notes"})

    if task_name == "step_therapy_required":
        if "medication_history" not in obs.retrieved_records:
            return PriorAuthAction(action_type="get_patient_records", params={"record_type": "medication_history", "days_back": 365})
        if "medication_history" not in obs.submitted_documents:
            return PriorAuthAction(action_type="submit_supporting_docs", params={"doc_type": "medication_history"})
        return PriorAuthAction(action_type="resolve", params={"outcome": "partial", "notes": "documented methotrexate but not second DMARD"})

    if task_name == "medical_necessity_dispute":
        if obs.appeal_stage == 0:
            return PriorAuthAction(
                action_type="submit_appeal",
                params={"appeal_type": "formal_written", "rationale": "requesting reconsideration"},
            )
        return PriorAuthAction(action_type="resolve", params={"outcome": "denied", "notes": "appeal submitted but process not completed"})

    return PriorAuthAction(action_type="check_auth_status", params={})


def choose_action(task_name: str, obs, history: List[dict], llm: OpenAI | None) -> PriorAuthAction:
    if llm is None:
        return fallback_policy(task_name, obs)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
    try:
        completion = llm.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        response_text = completion.choices[0].message.content or "{}"
        return parse_action(response_text)
    except Exception:
        return fallback_policy(task_name, obs)


async def run_task(task_name: str, env: PriorAuthEnv, llm: OpenAI | None) -> float:
    print(f"\n{'=' * 60}\n  TASK: {task_name}\n{'=' * 60}")

    result = await env.reset(task_name=task_name)
    obs = result.observation
    history: List[dict] = []
    step = 0

    while not obs.done:
        step += 1
        obs_text = format_observation(obs, step)
        print(f"\n--- Step {step} ---")
        history.append({"role": "user", "content": obs_text})
        if len(history) > MAX_HISTORY * 2:
            history = history[-(MAX_HISTORY * 2) :]

        action = choose_action(task_name, obs, history, llm)
        print(f"  -> {action.action_type}")
        if action.params:
            print(f"    params: {json.dumps(action.params)[:120]}")

        history.append({"role": "assistant", "content": json.dumps(action.model_dump())})
        result = await env.step(action)
        obs = result.observation
        reward = float(result.reward or 0.0)
        print(f"  reward={reward:+.3f} | status={obs.payer_status} | done={obs.done}")

        if step > 40:
            break

    final = float(obs.reward or 0.0)
    print(f"\n  Task '{task_name}' complete. Score: {final:.4f}")
    return max(0.0, min(1.0, final))


async def amain():
    print("\nOpenEnv Prior Authorization - Baseline Agent")
    print(f"Model:  {MODEL_NAME}")
    print(f"Server: {SERVER_URL}")

    llm = OpenAI(base_url=API_BASE_URL, api_key=API_KEY) if API_KEY else None
    scores = {}

    async with PriorAuthEnv(base_url=SERVER_URL) as env:
        for task in TASKS:
            t0 = time.time()
            try:
                score = await run_task(task, env, llm)
            except Exception as exc:
                print(f"  Task '{task}' failed: {exc}")
                score = 0.0
            scores[task] = score
            print(f"  [{task}] {score:.4f} ({time.time() - t0:.1f}s)")

    mean = sum(scores.values()) / len(scores)

    print(f"\n{'=' * 60}")
    print("  FINAL RESULTS")
    print(f"{'=' * 60}")
    for task, score in scores.items():
        filled = int(score * 20)
        bar = "█" * filled + "░" * (20 - filled)
        print(f"  {task:<32} {bar} {score:.4f}")
    print(f"  {'MEAN':<32} {'─' * 20} {mean:.4f}")
    print(f"{'=' * 60}\n")


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
