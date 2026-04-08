from __future__ import annotations

from openenv.core.client_types import StepResult
from openenv.core.env_client import EnvClient

from models import PriorAuthAction, PriorAuthObservation, PriorAuthState


class PriorAuthEnv(EnvClient[PriorAuthAction, PriorAuthObservation, PriorAuthState]):
    """WebSocket client for the Prior Auth environment."""

    def _step_payload(self, action: PriorAuthAction) -> dict:
        return {
            "action_type": action.action_type,
            "params": action.params,
        }

    def _parse_result(self, payload: dict) -> StepResult[PriorAuthObservation]:
        obs_data = payload.get("observation", {})
        obs = PriorAuthObservation(
            patient_summary=obs_data.get("patient_summary", {}),
            payer_response=obs_data.get("payer_response", ""),
            payer_status=obs_data.get("payer_status", "pending"),
            denial_reason=obs_data.get("denial_reason"),
            denial_reason_code=obs_data.get("denial_reason_code"),
            available_actions=obs_data.get("available_actions", []),
            retrieved_records=obs_data.get("retrieved_records", {}),
            submitted_documents=obs_data.get("submitted_documents", []),
            appeal_stage=obs_data.get("appeal_stage", 0),
            step_number=obs_data.get("step_number", 0),
            steps_remaining=obs_data.get("steps_remaining", 0),
            goal=obs_data.get("goal", ""),
            task_name=obs_data.get("task_name", ""),
            done=obs_data.get("done", payload.get("done", False)),
            reward=obs_data.get("reward", payload.get("reward")),
            metadata=obs_data.get("metadata", {}),
        )
        return StepResult(
            observation=obs,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: dict) -> PriorAuthState:
        return PriorAuthState(
            episode_id=payload.get("episode_id", ""),
            step_count=payload.get("step_count", 0),
            task_name=payload.get("task_name", ""),
            payer_status=payload.get("payer_status", "pending"),
            submitted_docs=payload.get("submitted_docs", []),
            retrieved_records=payload.get("retrieved_records", []),
            denial_count=payload.get("denial_count", 0),
            appeal_stage=payload.get("appeal_stage", 0),
            total_reward=payload.get("total_reward", 0.0),
            done=payload.get("done", False),
            correct_path_steps=payload.get("correct_path_steps", []),
        )
