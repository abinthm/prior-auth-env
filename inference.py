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
import sys
import textwrap
import time
from pathlib import Path
from typing import List, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from openai import OpenAI

from client import PriorAuthEnv
from models import PriorAuthAction

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Configuration ────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")
HF_TOKEN     = os.getenv("HF_TOKEN")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
SERVER_URL   = os.getenv("OPENENV_SERVER_URL", "ws://localhost:7860")
BENCHMARK    = "prior_auth_env"

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

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

    RULES:
    - Always call submit_auth_request first.
    - After a denial, get_denial_details and check_payer_criteria before acting.
    - Retrieve a record with get_patient_records before submitting it.
    - Call resolve when the authorization is APPROVED or when you have exhausted options.
    """
).strip()

PRIOR_AUTH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "submit_auth_request",
            "description": "Submit a new prior authorization request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "procedure_code": {"type": "string"},
                    "diagnosis_code": {"type": "string"}
                },
                "required": ["procedure_code", "diagnosis_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_records",
            "description": "Retrieve medical records for the patient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "record_type": {"type": "string"},
                    "days_back": {"type": "integer"}
                },
                "required": ["record_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_supporting_docs",
            "description": "Submit a retrieved document to the payer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_type": {"type": "string"}
                },
                "required": ["doc_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_denial_details",
            "description": "View details of an authorization denial.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_payer_criteria",
            "description": "Check exactly what the payer policy requires for approval.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_appeal",
            "description": "Submit a formal written appeal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appeal_type": {"type": "string"},
                    "rationale": {"type": "string"}
                },
                "required": ["appeal_type", "rationale"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_peer_to_peer",
            "description": "Request a peer-to-peer physician review call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "urgency": {"type": "string"}
                },
                "required": ["urgency"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_clinical_summary",
            "description": "Extract key findings to prepare a clinical summary for a P2P call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key_findings": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["key_findings"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_peer_to_peer_summary",
            "description": "Submit the prepared clinical summary during the P2P phase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"}
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_external_review",
            "description": "Escalate the dispute to an Independent Review Organization (IRO).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_auth_status",
            "description": "Check the status without performing any action.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resolve",
            "description": "Mark the authorization as resolved or terminal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "outcome": {"type": "string"},
                    "notes": {"type": "string"}
                },
                "required": ["outcome"]
            }
        }
    }
]


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


# ── LLM action selection ──────────────────────────────────────────────────────
def choose_action(
    task_name: str,
    obs,
    history: List[dict],
    llm: OpenAI,
) -> tuple[PriorAuthAction, Optional[str]]:
    """Returns (action, error_string_or_None)."""
    
    if obs.done:
        return PriorAuthAction(action_type="check_auth_status", params={}), None

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
    
    try:
        completion = llm.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            tools=PRIOR_AUTH_TOOLS,
            tool_choice="required"
        )
        
        tool_calls = completion.choices[0].message.tool_calls
        if not tool_calls:
            return PriorAuthAction(action_type="check_auth_status", params={}), "No tool calls generated."
            
        action_name = tool_calls[0].function.name
        action_args = {}
        try:
            action_args = json.loads(tool_calls[0].function.arguments)
        except Exception:
            pass # Use empty dict if arguments are malformed
            
        return PriorAuthAction(action_type=action_name, params=action_args), None
        
    except Exception as exc:
        return PriorAuthAction(action_type="check_auth_status", params={}), str(exc)


# ── Episode runner ────────────────────────────────────────────────────────────
async def run_task(task_name: str, env: PriorAuthEnv, llm: OpenAI) -> float:
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
            history.append({
                "role": "assistant",
                "content": f"Executed action: {action.action_type} with args: {json.dumps(action.params)}"
            })

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
    llm    = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
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

