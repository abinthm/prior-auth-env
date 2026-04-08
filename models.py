from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from openenv.core.env_server import Action, Observation, State
from pydantic import Field


class PriorAuthAction(Action):
    """What the agent sends to the environment."""

    action_type: str = Field(default="")
    params: Dict[str, Any] = Field(default_factory=dict)


class PriorAuthObservation(Observation):
    """What the agent sees after each step."""

    patient_summary: Dict[str, Any] = Field(default_factory=dict)
    payer_response: str = Field(default="")
    payer_status: str = Field(default="pending")
    denial_reason: Optional[str] = Field(default=None)
    denial_reason_code: Optional[str] = Field(default=None)
    available_actions: List[str] = Field(default_factory=list)
    retrieved_records: Dict[str, Any] = Field(default_factory=dict)
    submitted_documents: List[str] = Field(default_factory=list)
    appeal_stage: int = Field(default=0)
    step_number: int = Field(default=0)
    steps_remaining: int = Field(default=0)
    goal: str = Field(default="")
    task_name: str = Field(default="")


class PriorAuthState(State):
    """Internal state for debugging via GET /state."""

    task_name: str = Field(default="")
    payer_status: str = Field(default="pending")
    submitted_docs: List[str] = Field(default_factory=list)
    retrieved_records: List[str] = Field(default_factory=list)
    denial_count: int = Field(default=0)
    appeal_stage: int = Field(default=0)
    total_reward: float = Field(default=0.0)
    done: bool = Field(default=False)
    correct_path_steps: List[str] = Field(default_factory=list)
