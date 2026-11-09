from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status

from app.core.redis_store import kill_switch_store
from app.core.websocket import blocked_agents, manager
from app.schemas.agent_payload import (
    AgentActionRequest,
    ApprovalDecisionPayload,
    InspectionResult,
    KillSwitchPayload,
)
from app.services.inspector import AgentInspector
from app.services.state import state_manager

router = APIRouter(prefix="/api/v1", tags=["Interception"])
inspector = AgentInspector()


@router.post("/intercept", response_model=InspectionResult)
async def intercept_agent_action(payload: AgentActionRequest) -> InspectionResult:
    """Intercepte, analyse et diffuse en temps réel chaque action d'agent IA."""
    # 1. Avant toute inspection : rejet immédiat si l'agent fait partie de blocked_agents
    if kill_switch_store.is_agent_blocked(payload.agent_id):
        revoked_reason = "Agent révoqué par le Kill-Switch administrateur"
        result = InspectionResult(
            status="BLOCKED",
            risk_score=1.0,
            reasons=[revoked_reason],
            sanitized_prompt="[AGENT_TERMINATED]",
        )
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = state_manager.record_event(payload, result)
        await manager.broadcast(
            {
                "id": log_entry["id"],
                "agent_id": payload.agent_id,
                "prompt": payload.prompt,
                "sanitized_prompt": result.sanitized_prompt,
                "tool_called": payload.tool_called,
                "estimated_cost": payload.estimated_cost,
                "risk_score": result.risk_score,
                "status": "AGENT_TERMINATED",
                "reasons": result.reasons,
                "timestamp": timestamp,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": revoked_reason,
                "status": "BLOCKED",
                "risk_score": result.risk_score,
                "reasons": result.reasons,
                "sanitized_prompt": result.sanitized_prompt,
            },
        )

    # 2. Vérification du Kill-Switch global ou de la quarantaine
    if state_manager.kill_switch_active:
        result = InspectionResult(
            status="BLOCKED",
            risk_score=1.0,
            reasons=["Kill-Switch d'urgence actif : toutes les actions d'agents sont suspendues."],
            sanitized_prompt="[BLOCKED_BY_KILL_SWITCH]",
        )
    elif payload.agent_id in state_manager.quarantined_agents:
        result = InspectionResult(
            status="BLOCKED",
            risk_score=1.0,
            reasons=[f"Agent '{payload.agent_id}' placé en quarantaine par un opérateur."],
            sanitized_prompt="[BLOCKED_AGENT_QUARANTINED]",
        )
    else:
        result = inspector.inspect(payload)

    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = state_manager.record_event(payload, result)

    # Diffusion en temps réel à tous les clients WebSocket connectés
    alert_message = {
        "id": log_entry["id"],
        "agent_id": payload.agent_id,
        "prompt": payload.prompt,
        "sanitized_prompt": result.sanitized_prompt,
        "tool_called": payload.tool_called,
        "estimated_cost": payload.estimated_cost,
        "risk_score": result.risk_score,
        "status": result.status,
        "reasons": result.reasons,
        "timestamp": timestamp,
    }
    await manager.broadcast(alert_message)

    if result.status == "BLOCKED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": result.status,
                "risk_score": result.risk_score,
                "reasons": result.reasons,
                "sanitized_prompt": result.sanitized_prompt,
            },
        )

    return result


@router.get("/status")
async def get_system_status():
    """Retourne l'état du Kill-Switch, les métriques et le flux d'activité récent."""
    return {
        "kill_switch_active": state_manager.kill_switch_active,
        "blocked_agents": list(blocked_agents),
        "quarantined_agents": list(state_manager.quarantined_agents),
        "metrics": {
            "total_intercepted": state_manager.total_intercepted,
            "threats_blocked": state_manager.threats_blocked,
            "estimated_cost_saved": state_manager.estimated_cost_saved,
        },
        "recent_logs": state_manager.recent_logs,
    }


@router.post("/kill-switch")
async def toggle_kill_switch(payload: KillSwitchPayload):
    """Active ou désactive le Kill-Switch d'urgence global."""
    state_manager.kill_switch_active = payload.active
    return {
        "kill_switch_active": state_manager.kill_switch_active,
        "status": "KILL_SWITCH_ENGAGED" if payload.active else "SYSTEM_ARMED",
    }


@router.post("/logs/{log_id}/decision")
async def decide_pending_action(log_id: str, payload: ApprovalDecisionPayload):
    """Permet à un opérateur humain d'approuver ou de bloquer une requête PENDING_APPROVAL."""
    updated = state_manager.update_log_status(log_id, payload.decision)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Événement '{log_id}' introuvable.",
        )
    await manager.broadcast(
        {
            "type": "DECISION_UPDATE",
            "id": log_id,
            "status": payload.decision,
            "agent_id": updated["agent_id"],
            "estimated_cost": updated.get("estimated_cost", 0.0),
        }
    )
    return updated


@router.get("/logs/export")
async def export_audit_logs():
    """Exporte le journal complet d'audit de sécurité au format JSON."""
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total_intercepted": state_manager.total_intercepted,
        "threats_blocked": state_manager.threats_blocked,
        "estimated_cost_saved": state_manager.estimated_cost_saved,
        "blocked_agents": list(kill_switch_store.get_all_blocked()),
        "logs": state_manager.recent_logs,
    }

