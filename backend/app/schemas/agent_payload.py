from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class AgentActionRequest(BaseModel):
    agent_id: str = Field(..., description="Identifiant unique de l'agent IA")
    prompt: str = Field(..., description="Prompt ou intention d'action de l'agent")
    tool_called: Optional[str] = Field(default=None, description="Nom de l'outil appelé par l'agent")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Paramètres passés à l'outil")
    estimated_cost: float = Field(default=0.0, ge=0.0, description="Coût estimé de l'opération en USD")


class InspectionResult(BaseModel):
    status: Literal["APPROVED", "BLOCKED", "PENDING_APPROVAL"]
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Score de risque compris entre 0.0 et 1.0")
    reasons: List[str] = Field(default_factory=list, description="Motifs justifiant la décision")
    sanitized_prompt: str = Field(..., description="Prompt nettoyé des motifs dangereux éventuels")


class KillSwitchPayload(BaseModel):
    active: bool = Field(..., description="État d'activation du Kill-Switch global")


class ApprovalDecisionPayload(BaseModel):
    decision: Literal["APPROVED", "BLOCKED"] = Field(
        ..., description="Décision manuelle d'un opérateur sur une action en attente"
    )


