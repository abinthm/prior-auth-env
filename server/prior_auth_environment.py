from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from openenv.core.env_server.interfaces import Environment

from models import PriorAuthAction, PriorAuthObservation, PriorAuthState
from server.graders.easy_grader import EasyGrader
from server.graders.hard_grader import HardGrader
from server.graders.medium_grader import MediumGrader
from server.scenarios.easy_missing_docs import EASY_SCENARIO
from server.scenarios.medical_necessity_dispute import HARD_SCENARIO
from server.scenarios.step_therapy_required import MEDIUM_SCENARIO


SCENARIOS: Dict[str, dict] = {
    "easy_missing_docs": EASY_SCENARIO,
    "step_therapy_required": MEDIUM_SCENARIO,
    "medical_necessity_dispute": HARD_SCENARIO,
}

GRADERS: Dict[str, type] = {
    "easy_missing_docs": EasyGrader,
    "step_therapy_required": MediumGrader,
    "medical_necessity_dispute": HardGrader,
}

ALL_ACTIONS = [
    "submit_auth_request",
    "get_patient_records",
    "get_denial_details",
    "check_payer_criteria",
    "submit_supporting_docs",
    "submit_appeal",
    "request_peer_to_peer",
    "prepare_clinical_summary",
    "submit_peer_to_peer_summary",
    "check_auth_status",
    "escalate_to_external_review",
    "resolve",
]


class PriorAuthEnvironment(Environment):
    is_concurrency_safe = False

    def __init__(self):
        self._reset_state()

    def _reset_state(self) -> None:
        self._episode_id = str(uuid.uuid4())
        self._scenario: Optional[dict] = None
        self._task_name = ""
        self._payer_status = "pending"
        self._submitted_docs: list[str] = []
        self._retrieved_records: dict[str, Any] = {}
        self._denial_count = 0
        self._appeal_stage = 0
        self._step_count = 0
        self._total_reward = 0.0
        self._done = False
        self._episode_done = False
        self._denial_sequence_index = 0
        self._grader = None
        self._unnecessary_actions = 0
        self._correct_path_steps: list[str] = []

    def reset(self, task_name: str = "easy_missing_docs", **kwargs) -> PriorAuthObservation:
        self._reset_state()
        if task_name not in SCENARIOS:
            available = ", ".join(sorted(SCENARIOS))
            raise ValueError(f"Unknown task_name '{task_name}'. Available tasks: {available}")

        self._task_name = task_name
        self._scenario = deepcopy(SCENARIOS[task_name])
        self._grader = GRADERS[task_name](self._scenario)

        return PriorAuthObservation(
            patient_summary=self._scenario["patient"],
            payer_response=(
                f"Prior authorization required for {self._scenario['procedure']['name']}. "
                f"Patient is covered under {self._scenario['patient']['payer']}. "
                "Please submit authorization request to begin."
            ),
            payer_status="pending",
            denial_reason=None,
            denial_reason_code=None,
            available_actions=ALL_ACTIONS,
            retrieved_records={},
            submitted_documents=[],
            appeal_stage=0,
            step_number=0,
            steps_remaining=self._scenario["step_limit"],
            goal=self._scenario["goal"],
            task_name=task_name,
            reward=0.0,
            done=False,
        )

    def step(self, action: PriorAuthAction) -> PriorAuthObservation:
        if self._done:
            return self._build_obs(
                payer_response="Episode already complete. Call reset() to start a new episode.",
                reward=0.0,
                done=True,
            )

        if self._scenario is None or self._grader is None:
            raise RuntimeError("Environment must be reset before calling step().")

        self._step_count += 1
        step_reward = -0.01

        handler = self._get_handler(action.action_type)
        if handler is None:
            self._unnecessary_actions += 1
            payer_response = f"Unknown action: {action.action_type}. Valid actions: {ALL_ACTIONS}"
            step_reward -= 0.05
        else:
            payer_response, extra_reward, marked_done = handler(action.params)
            step_reward += extra_reward
            if marked_done:
                self._episode_done = True

        self._total_reward += step_reward

        if self._step_count >= self._scenario["step_limit"] and not self._episode_done:
            self._done = True
            final_score = self._grader.compute_final_score(
                submitted_docs=self._submitted_docs,
                payer_status=self._payer_status,
                denial_count=self._denial_count,
                appeal_stage=self._appeal_stage,
                step_count=self._step_count,
                step_limit=self._scenario["step_limit"],
                unnecessary_actions=self._unnecessary_actions,
                resolved=False,
            )
            return self._build_obs(
                payer_response="Step limit reached. Episode terminated.",
                reward=final_score,
                done=True,
            )

        if self._episode_done:
            self._done = True
            final_score = self._grader.compute_final_score(
                submitted_docs=self._submitted_docs,
                payer_status=self._payer_status,
                denial_count=self._denial_count,
                appeal_stage=self._appeal_stage,
                step_count=self._step_count,
                step_limit=self._scenario["step_limit"],
                unnecessary_actions=self._unnecessary_actions,
                resolved=True,
            )
            return self._build_obs(
                payer_response=payer_response,
                reward=final_score,
                done=True,
            )

        return self._build_obs(
            payer_response=payer_response,
            reward=step_reward,
            done=False,
        )

    def _build_obs(self, payer_response: str, reward: float, done: bool) -> PriorAuthObservation:
        scenario = self._scenario or {}
        return PriorAuthObservation(
            patient_summary=scenario.get("patient", {}),
            payer_response=payer_response,
            payer_status=self._payer_status,
            denial_reason=scenario.get("current_denial_reason"),
            denial_reason_code=scenario.get("current_denial_code"),
            available_actions=ALL_ACTIONS,
            retrieved_records=deepcopy(self._retrieved_records),
            submitted_documents=self._submitted_docs.copy(),
            appeal_stage=self._appeal_stage,
            step_number=self._step_count,
            steps_remaining=max(0, scenario.get("step_limit", 0) - self._step_count),
            goal=scenario.get("goal", ""),
            task_name=self._task_name,
            reward=reward,
            done=done,
        )

    @property
    def state(self) -> PriorAuthState:
        return PriorAuthState(
            episode_id=self._episode_id,
            step_count=self._step_count,
            task_name=self._task_name,
            payer_status=self._payer_status,
            submitted_docs=self._submitted_docs.copy(),
            retrieved_records=list(self._retrieved_records.keys()),
            denial_count=self._denial_count,
            appeal_stage=self._appeal_stage,
            total_reward=self._total_reward,
            done=self._done,
            correct_path_steps=self._correct_path_steps.copy(),
        )

    def _mark_correct_path(self, step_name: str) -> None:
        if step_name not in self._correct_path_steps:
            self._correct_path_steps.append(step_name)

    def _get_handler(self, action_type: str) -> Optional[Callable[[dict[str, Any]], tuple[str, float, bool]]]:
        handlers = {
            "submit_auth_request": self._handle_submit_auth,
            "get_patient_records": self._handle_get_records,
            "get_denial_details": self._handle_get_denial_details,
            "check_payer_criteria": self._handle_check_criteria,
            "submit_supporting_docs": self._handle_submit_docs,
            "submit_appeal": self._handle_submit_appeal,
            "request_peer_to_peer": self._handle_request_p2p,
            "prepare_clinical_summary": self._handle_prepare_summary,
            "submit_peer_to_peer_summary": self._handle_submit_p2p,
            "check_auth_status": self._handle_check_status,
            "escalate_to_external_review": self._handle_escalate,
            "resolve": self._handle_resolve,
        }
        return handlers.get(action_type)

    def _handle_submit_auth(self, params: dict[str, Any]) -> tuple[str, float, bool]:
        assert self._scenario is not None

        proc = params.get("procedure_code", "")
        diag = params.get("diagnosis_code", "")

        if self._payer_status != "pending":
            self._unnecessary_actions += 1
            return "Auth request already submitted.", -0.05, False

        if proc == self._scenario["procedure"]["code"] and diag == self._scenario["diagnosis"]["code"]:
            self._mark_correct_path("submit_auth_request")

        denial_seq = self._scenario.get("denial_sequence", [])
        if denial_seq and self._denial_sequence_index < len(denial_seq):
            denial = denial_seq[self._denial_sequence_index]
            if denial["trigger"] == "initial_submit":
                self._payer_status = "info_requested" if self._task_name == "easy_missing_docs" else "denied"
                self._denial_count += 1
                self._denial_sequence_index += 1
                self._scenario["current_denial_reason"] = denial["response"]
                self._scenario["current_denial_code"] = denial.get("reason_code", "CO-197")
                return (
                    f"Authorization request received. Status: {self._payer_status.upper()}. "
                    f"Reason: {denial['response']} "
                    f"Reason code: {denial.get('reason_code', 'CO-197')}",
                    0.0,
                    False,
                )

        self._payer_status = "approved"
        return "Authorization APPROVED.", 0.0, False

    def _handle_get_records(self, params: dict[str, Any]) -> tuple[str, float, bool]:
        assert self._scenario is not None

        record_type = params.get("record_type", "")
        available_records = self._scenario.get("available_records", {})

        if record_type not in available_records:
            self._unnecessary_actions += 1
            return (
                f"No {record_type} records found for this patient. "
                f"Available record types: {list(available_records.keys())}",
                -0.02,
                False,
            )

        if record_type in self._retrieved_records:
            self._unnecessary_actions += 1
            return f"{record_type} already retrieved.", -0.03, False

        self._retrieved_records[record_type] = deepcopy(available_records[record_type])
        if record_type in self._scenario.get("correct_docs_required", []):
            self._mark_correct_path(f"get_{record_type}")

        return (
            f"Retrieved {record_type} records: {available_records[record_type]['summary']}",
            0.0,
            False,
        )

    def _handle_get_denial_details(self, params: dict[str, Any]) -> tuple[str, float, bool]:
        assert self._scenario is not None

        if self._payer_status not in ("info_requested", "denied"):
            self._unnecessary_actions += 1
            return "No active denial to retrieve details for.", -0.03, False

        self._mark_correct_path("get_denial_details")
        criteria = self._scenario.get("payer_criteria", "No specific criteria available.")
        return (
            f"Denial details: {self._scenario.get('current_denial_reason', 'Unknown')}. "
            f"Payer criteria: {criteria}",
            0.0,
            False,
        )

    def _handle_check_criteria(self, params: dict[str, Any]) -> tuple[str, float, bool]:
        assert self._scenario is not None

        self._mark_correct_path("check_payer_criteria")
        criteria = self._scenario.get("payer_criteria", "Criteria not available.")
        return f"Coverage criteria for {self._scenario['procedure']['name']}: {criteria}", 0.0, False

    def _handle_submit_docs(self, params: dict[str, Any]) -> tuple[str, float, bool]:
        assert self._scenario is not None

        doc_type = params.get("doc_type", "")
        if not doc_type:
            self._unnecessary_actions += 1
            return "doc_type parameter required.", -0.05, False

        if doc_type in self._submitted_docs:
            self._unnecessary_actions += 1
            return f"{doc_type} already submitted.", -0.03, False

        if doc_type not in self._retrieved_records:
            self._unnecessary_actions += 1
            return f"Cannot submit {doc_type} - not retrieved from patient chart first.", -0.05, False

        self._submitted_docs.append(doc_type)
        if doc_type in self._scenario.get("correct_docs_required", []):
            self._mark_correct_path(f"submit_{doc_type}")

        required = self._scenario.get("required_docs_by_stage", {})
        current_stage_key = str(max(self._denial_sequence_index - 1, 0))
        current_stage_required = required.get(current_stage_key, [])

        all_satisfied = all(doc in self._submitted_docs for doc in current_stage_required)
        if all_satisfied and current_stage_required:
            denial_seq = self._scenario.get("denial_sequence", [])
            if self._task_name == "hard":
                pass
            if self._denial_sequence_index < len(denial_seq):
                next_denial = denial_seq[self._denial_sequence_index]
                if next_denial["trigger"] in ("after_stage_0", "after_stage_1"):
                    self._denial_count += 1
                    self._denial_sequence_index += 1
                    self._payer_status = "info_requested"
                    self._scenario["current_denial_reason"] = next_denial["response"]
                    self._scenario["current_denial_code"] = next_denial.get("reason_code", "CO-197")
                    return (
                        "Documentation received. Additional information required: "
                        f"{next_denial['response']} (Code: {next_denial.get('reason_code', 'CO-197')})",
                        0.05,
                        False,
                    )

            self._payer_status = "approved"
            self._scenario["current_denial_reason"] = None
            self._scenario["current_denial_code"] = None
            return (
                "Documentation reviewed and accepted. "
                f"Authorization APPROVED. Auth number: PA-{datetime.now().strftime('%Y%m%d')}-{self._episode_id[:4].upper()}",
                0.10,
                False,
            )

        return f"{doc_type} submitted successfully. Awaiting payer review.", 0.02, False

    def _handle_submit_appeal(self, params: dict[str, Any]) -> tuple[str, float, bool]:
        assert self._scenario is not None

        if self._payer_status not in ("info_requested", "denied"):
            self._unnecessary_actions += 1
            return "No denial to appeal.", -0.05, False

        if self._appeal_stage >= 1:
            self._unnecessary_actions += 1
            return "Appeal already submitted.", -0.03, False

        self._appeal_stage = 1
        self._mark_correct_path("submit_appeal")

        denial_seq = self._scenario.get("denial_sequence", [])
        if self._denial_sequence_index < len(denial_seq):
            next_denial = denial_seq[self._denial_sequence_index]
            if next_denial["trigger"] == "after_appeal":
                self._payer_status = "denied"
                self._denial_count += 1
                self._denial_sequence_index += 1
                self._scenario["current_denial_reason"] = next_denial["response"]
                self._scenario["current_denial_code"] = next_denial.get("reason_code", "CO-197")
                return (
                    f"Appeal received. Payer response: {next_denial['response']}",
                    0.05,
                    False,
                )

        return "Appeal submitted. Awaiting payer decision (5-7 business days).", 0.05, False

    def _handle_request_p2p(self, params: dict[str, Any]) -> tuple[str, float, bool]:
        if self._appeal_stage < 1:
            self._unnecessary_actions += 1
            return "Formal appeal must be submitted before requesting peer-to-peer.", -0.05, False

        if self._appeal_stage >= 2:
            self._unnecessary_actions += 1
            return "Peer-to-peer already requested.", -0.03, False

        self._appeal_stage = 2
        self._mark_correct_path("request_peer_to_peer")
        return (
            "Peer-to-peer review requested. Medical director will contact treating physician "
            "within 2 business days. Prepare clinical summary before the call.",
            0.05,
            False,
        )

    def _handle_prepare_summary(self, params: dict[str, Any]) -> tuple[str, float, bool]:
        if self._appeal_stage < 2:
            self._unnecessary_actions += 1
            return "Request peer-to-peer review before preparing summary.", -0.03, False

        key_findings = params.get("key_findings", [])
        if not isinstance(key_findings, list):
            key_findings = []

        self._retrieved_records["clinical_summary"] = {"key_findings": key_findings}
        self._mark_correct_path("prepare_clinical_summary")
        if not key_findings:
            return "Clinical summary prepared (no key findings specified).", 0.02, False
        return f"Clinical summary prepared with {len(key_findings)} key findings.", 0.03, False

    def _handle_submit_p2p(self, params: dict[str, Any]) -> tuple[str, float, bool]:
        assert self._scenario is not None

        if self._appeal_stage < 2:
            self._unnecessary_actions += 1
            return "Peer-to-peer not yet requested.", -0.05, False

        if "clinical_summary" not in self._retrieved_records:
            self._unnecessary_actions += 1
            return "Submit clinical summary preparation first.", -0.03, False

        self._appeal_stage = 3
        self._mark_correct_path("submit_peer_to_peer_summary")

        denial_seq = self._scenario.get("denial_sequence", [])
        if self._denial_sequence_index < len(denial_seq):
            next_denial = denial_seq[self._denial_sequence_index]
            if next_denial["trigger"] == "after_p2p":
                self._denial_count += 1
                self._denial_sequence_index += 1
                self._scenario["current_denial_reason"] = next_denial["response"]
                return f"P2P review complete. Payer response: {next_denial['response']}", 0.05, False

        self._payer_status = "approved"
        self._scenario["current_denial_reason"] = None
        self._scenario["current_denial_code"] = None
        return (
            "Peer-to-peer review complete. Medical director agreed with clinical necessity. "
            f"Authorization APPROVED. Auth number: PA-{datetime.now().strftime('%Y%m%d')}-{self._episode_id[:4].upper()}",
            0.10,
            False,
        )

    def _handle_check_status(self, params: dict[str, Any]) -> tuple[str, float, bool]:
        assert self._scenario is not None
        return (
            f"Current status: {self._payer_status.upper()}. "
            f"Documents submitted: {self._submitted_docs}. "
            f"Step {self._step_count} of {self._scenario['step_limit']}.",
            0.0,
            False,
        )

    def _handle_escalate(self, params: dict[str, Any]) -> tuple[str, float, bool]:
        if self._appeal_stage < 2:
            self._unnecessary_actions += 1
            return "Exhausting internal appeals first is required before external review.", -0.05, False

        self._appeal_stage = 4
        self._payer_status = "approved"
        self._mark_correct_path("escalate_to_external_review")
        return (
            "Case escalated to Independent Review Organization (IRO). "
            "IRO determination: Medically necessary. Authorization APPROVED.",
            0.08,
            False,
        )

    def _handle_resolve(self, params: dict[str, Any]) -> tuple[str, float, bool]:
        self._episode_done = True
        outcome = params.get("outcome", "unknown")
        notes = params.get("notes", "")
        return (
            f"Episode resolved. Outcome: {outcome}. Authorization status: {self._payer_status}. Notes: {notes}",
            0.0,
            True,
        )
