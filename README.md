---
title: Prior Auth Env — Healthcare Prior Authorization Agent Environment
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 7860
tags:
  - openenv
  - healthcare
  - prior-authorization
  - rcm
  - real-world
  - rl-environment
---

# Prior Authorization Environment

**A real-world OpenEnv environment for training AI agents on US health insurance prior authorization workflows.**

[![OpenEnv](https://img.shields.io/badge/OpenEnv-Compatible-blue)](https://github.com/meta-pytorch/OpenEnv)
[![Domain](https://img.shields.io/badge/Domain-Healthcare%20RCM-green)](https://en.wikipedia.org/wiki/Revenue_cycle_management)
[![Tasks](https://img.shields.io/badge/Tasks-3%20(Easy%20%E2%86%92%20Hard)-orange)](https://huggingface.co/spaces/abin334/prior-auth-env)
[![Difficulty](https://img.shields.io/badge/Difficulty-Easy%20%7C%20Medium%20%7C%20Hard-red)](https://huggingface.co/spaces/abin334/prior-auth-env)

---

## Why Prior Authorization?

Prior authorization (PA) is the process insurance companies use to approve or deny medically necessary treatments before they are performed. In the US:

- **$35 billion** is spent annually on PA administrative overhead
- **90% of physicians** report PA causes treatment delays
- Physicians spend an average of **14 hours per week** on PA paperwork
- Incomplete or wrong actions at any step can **delay patient care by days/weeks**

This environment trains AI agents to navigate this complex, multi-step, denial-heavy workflow — exactly the kind of high-stakes sequential decision-making that is hard for current LLMs and ideal for RL fine-tuning.

---

## Environment Overview

The agent acts as an RCM (Revenue Cycle Management) specialist. Starting from a patient case, it must:

1. Submit an authorization request to the insurer
2. Respond to denials by gathering and submitting the correct clinical documentation
3. File formal appeals when needed
4. Navigate peer-to-peer reviews with medical directors
5. Escalate to external review organizations as a last resort

Each action produces a realistic payer response drawn from actual insurance denial workflows. The environment models real-world complexity: wrong actions incur step costs, redundant submissions are penalized, and the correct documentation must be retrieved before it can be submitted.

---

## Action Space

The agent communicates by sending a JSON object with two fields:

```json
{"action_type": "<action>", "params": {<key-value pairs>}}
```

| Action | Description | Key Params |
|--------|-------------|------------|
| `submit_auth_request` | Submit the initial PA request to the payer | `procedure_code`, `diagnosis_code` |
| `get_patient_records` | Retrieve a record type from the patient chart | `record_type`, `days_back` |
| `get_denial_details` | Fetch full denial reason and payer criteria | _(none)_ |
| `check_payer_criteria` | Look up coverage policy for the procedure | _(none)_ |
| `submit_supporting_docs` | Submit a retrieved record to address a denial | `doc_type` |
| `submit_appeal` | File a formal written appeal | `appeal_type`, `rationale` |
| `request_peer_to_peer` | Request medical director review after appeal | `urgency` |
| `prepare_clinical_summary` | Compile clinical findings for P2P call | `key_findings` (list) |
| `submit_peer_to_peer_summary` | Submit the clinical summary to the payer | `content` |
| `check_auth_status` | Query current authorization status | _(none)_ |
| `escalate_to_external_review` | Escalate to Independent Review Organization | _(none)_ |
| `resolve` | Mark episode complete with outcome | `outcome`, `notes` |

---

## Observation Space

Each `step()` and `reset()` returns a `PriorAuthObservation` with:

| Field | Type | Description |
|-------|------|-------------|
| `patient_summary` | `dict` | Patient demographics, payer, member ID |
| `payer_response` | `str` | Full payer message (approval, denial reason, next steps) |
| `payer_status` | `str` | `pending` / `info_requested` / `denied` / `approved` |
| `denial_reason` | `str \| None` | Human-readable denial reason |
| `denial_reason_code` | `str \| None` | Standard denial code (e.g. `CO-50`, `CO-197`) |
| `available_actions` | `list[str]` | All valid action names |
| `retrieved_records` | `dict` | Records fetched so far (record_type → content) |
| `submitted_documents` | `list[str]` | Doc types submitted to payer |
| `appeal_stage` | `int` | 0=none, 1=appeal submitted, 2=P2P requested, 3=P2P complete, 4=IRO escalated |
| `step_number` | `int` | Current step in episode |
| `steps_remaining` | `int` | Steps before episode terminates |
| `goal` | `str` | Plain-English description of what needs to be achieved |
| `task_name` | `str` | Active task identifier |
| `reward` | `float` | Step-level reward (terminal episodes: final grader score) |
| `done` | `bool` | Whether the episode has ended |

---

## Tasks

### Task 1: `easy_missing_docs` — Missing Documentation Submission
**Difficulty:** Easy | **Step Limit:** 8 | **Optimal Steps:** 3

**Scenario:** Patient James Whitfield needs a Lumbar Spine MRI (CPT 72148). BlueCrest HMO initially denies due to missing clinical documentation (CO-197). The agent must retrieve the correct office visit notes and resubmit.

**What the agent must do:**
1. Submit authorization with correct procedure/diagnosis codes
2. Recognize the info-request denial and identify the missing document
3. Retrieve `clinical_notes` from the patient chart
4. Submit the documentation to the payer → Authorization approved

**Grading:**
| Component | Weight | Criteria |
|-----------|--------|----------|
| Approval | 45% | `payer_status == "approved"` |
| Documentation | 25% | Fraction of required docs submitted |
| Speed | 15% | Steps saved vs. step limit |
| Efficiency | 10% | Penalizes unnecessary/redundant actions |
| Resolve | 5% | Called `resolve()` to close episode |

**Expected scores:** Random agent ~0.10 | Frontier LLM ~0.85–1.00

---

### Task 2: `step_therapy_required` — Two-Stage Step Therapy Documentation
**Difficulty:** Medium | **Step Limit:** 14 | **Optimal Steps:** 6

**Scenario:** Patient Maria Santos has rheumatoid arthritis and needs Humira (adalimumab, J0135). Apex Health HMO's step therapy policy requires proof that she tried and failed **two** conventional DMARDs (methotrexate + one other) before approving a biologic. The payer issues two sequential denials, each requiring a different document.

**What the agent must do:**
1. Submit authorization → Denied (CO-167): needs `medication_history`
2. Retrieve and submit `medication_history` → Denied again: needs `visit_notes`
3. Retrieve and submit `visit_notes` → Authorization approved
4. Resolve episode

**Grading:**
| Component | Weight | Criteria |
|-----------|--------|----------|
| Approval | 40% | `payer_status == "approved"` |
| Documentation | 30% | Fraction of both required docs submitted |
| Denial Navigation | 10% | Navigated 1+ denial stages correctly |
| Speed | 10% | Step efficiency |
| Efficiency | 7% | Low unnecessary actions |
| Resolve | 3% | Called `resolve()` |

**Expected scores:** Random agent ~0.05 | Frontier LLM ~0.65–0.85

---

### Task 3: `medical_necessity_dispute` — Full Appeal + P2P + IRO Escalation
**Difficulty:** Hard | **Step Limit:** 26 | **Optimal Steps:** 13

**Scenario:** Patient Robert Okonkwo needs lumbar spinal fusion L4-L5 (CPT 22612) for Grade II spondylolisthesis. United National Health PPO denies as "not medically necessary" (CO-50). The agent must navigate a 4-stage escalation ladder:

**What the agent must do:**
1. Submit auth → Denied (CO-50): needs imaging + functional assessment + clinical notes
2. Retrieve all 3 documents + Submit formal appeal → Appeal upheld — denied again (P2P required)
3. Request peer-to-peer → Prepare clinical summary → Submit P2P → Medical director upholds denial (IRO option offered)
4. Escalate to IRO → Authorization approved

**Grading:**
| Component | Weight | Criteria |
|-----------|--------|----------|
| Approval | 25% | Final `payer_status == "approved"` |
| Documentation | 20% | All 3 required docs (imaging, functional assessment, clinical notes) |
| Appeal | 10% | Reached `appeal_stage >= 1` |
| P2P Complete | 12% | Reached `appeal_stage >= 3` |
| IRO Escalation | 13% | Reached `appeal_stage >= 4` |
| Speed | 10% | Step efficiency |
| Efficiency | 5% | Unnecessary action count |
| Resolve | 5% | Called `resolve()` |

**Expected scores:** Random agent ~0.02 | Frontier LLM ~0.40–0.65

**Why this challenges frontier models:** The agent must maintain multi-stage context across 13+ steps, correctly interpret payer responses at each stage, prepare a clinically coherent summary (with real medical findings), and know when to escalate. Models that "give up" after the first appeal denial will score below 0.30.

---

## Reward Function

The reward function provides **dense, partial-progress signal** throughout each episode:

- **Step penalty** (`-0.01` per step): discourages excessive steps
- **Invalid action penalty** (`-0.05`): penalizes unknown action types
- **Redundant action penalty** (`-0.02` to `-0.05`): penalizes re-retrieving/re-submitting
- **Progress rewards** (`+0.02` to `+0.10`): awarded for correct doc submission, appeal filing, P2P completion
- **Terminal score** (`0.0–1.0`): grader-computed final score on `done=True`

The final score is returned as the last reward when `done=True`. Intermediate steps provide gradient signal for RL training.

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/reset` | POST | Start new episode. Body: `{"task_name": "easy_missing_docs"}` |
| `/step` | POST | Execute action. Body: `{"action_type": "...", "params": {...}}` |
| `/state` | GET | Get current state (episode_id, step count, scores) |
| `/health` | GET | Health check: `{"status": "ok"}` |
| `/ws` | WebSocket | Persistent session endpoint (used by Python client) |
| `/docs` | GET | Interactive OpenAPI/Swagger documentation |

---

## Quick Start

### Connect to the running Space

```python
import asyncio
from prior_auth_env import PriorAuthEnv, PriorAuthAction

async def main():
    async with PriorAuthEnv(base_url="https://abin334-prior-auth-env.hf.space") as env:
        # Start easy task
        result = await env.reset(task_name="easy_missing_docs")
        obs = result.observation
        print(f"Goal: {obs.goal}")
        print(f"Status: {obs.payer_status}")

        # Submit authorization request
        result = await env.step(PriorAuthAction(
            action_type="submit_auth_request",
            params={"procedure_code": "72148", "diagnosis_code": "M54.5"}
        ))
        print(f"Payer response: {result.observation.payer_response}")
        print(f"Reward: {result.reward}")

asyncio.run(main())
```

### Install the client package

```bash
pip install git+https://huggingface.co/spaces/abin334/prior-auth-env
```

### Run locally with Docker

```bash
# Pull from HF Spaces registry
docker pull registry.hf.space/abin334-prior-auth-env:latest

# Run on port 7860
docker run -d -p 7860:7860 registry.hf.space/abin334-prior-auth-env:latest

# Or build from source
git clone https://huggingface.co/spaces/abin334/prior-auth-env
cd prior-auth-env
docker build -t prior-auth-env:latest .
docker run -d -p 7860:7860 prior-auth-env:latest
```

### Run the baseline inference script

```bash
# Without LLM (deterministic fallback policy)
OPENENV_SERVER_URL=ws://localhost:7860 python inference.py

# With LLM via HF Inference API
HF_TOKEN=hf_xxx \
OPENENV_SERVER_URL=ws://localhost:7860 \
MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct \
python inference.py
```

---

## Baseline Scores

Scores produced by the deterministic fallback policy (no LLM required, fully reproducible):

| Task | Fallback Policy | Llama-3.3-70B | Qwen2.5-72B |
|------|----------------|---------------|-------------|
| easy_missing_docs | ~0.72 | ~0.88 | ~0.90 |
| step_therapy_required | ~0.58 | ~0.72 | ~0.75 |
| medical_necessity_dispute | ~0.32 | ~0.48 | ~0.52 |
| **Mean** | **~0.54** | **~0.69** | **~0.72** |

*Scores are averaged over 5 runs. LLM scores use `temperature=0.1`.*

---

## Project Structure

```
prior_auth_env/
├── Dockerfile                    # Container definition
├── README.md                     # This file (HF Spaces config + docs)
├── openenv.yaml                  # OpenEnv manifest
├── pyproject.toml                # Package metadata
├── inference.py                  # Baseline agent script (mandatory)
├── __init__.py                   # Package exports
├── client.py                     # PriorAuthEnv WebSocket client
├── models.py                     # Pydantic Action/Observation/State models
└── server/
    ├── __init__.py
    ├── app.py                    # FastAPI application (all endpoints)
    ├── prior_auth_environment.py # Core environment logic
    ├── prior_auth_env_environment.py  # Legacy compatibility shim
    ├── graders/
    │   ├── base_grader.py        # Abstract grader base class
    │   ├── easy_grader.py        # Grader for easy_missing_docs
    │   ├── medium_grader.py      # Grader for step_therapy_required
    │   └── hard_grader.py        # Grader for medical_necessity_dispute
    └── scenarios/
        ├── easy_missing_docs.py         # Lumbar MRI scenario data
        ├── step_therapy_required.py     # Humira step therapy scenario
        └── medical_necessity_dispute.py # Spinal fusion appeal+P2P+IRO scenario
```

---

## Environment Spec Compliance

This environment implements the full [OpenEnv specification](https://github.com/meta-pytorch/OpenEnv):

- ✅ Typed `Action`, `Observation`, `State` Pydantic models
- ✅ `reset()` returns clean initial `PriorAuthObservation`
- ✅ `step(action)` returns observation, reward, done, info
- ✅ `state()` returns `PriorAuthState` with episode metadata
- ✅ `openenv.yaml` manifest present
- ✅ Docker deployment on port 7860
- ✅ `/health`, `/reset`, `/step`, `/state`, `/ws`, `/docs` endpoints
- ✅ 3 tasks with programmatic graders returning scores in `[0.0, 1.0]`
- ✅ `inference.py` with correct `[START]`/`[STEP]`/`[END]` stdout format

---

## License

BSD 3-Clause License. See LICENSE for details.
