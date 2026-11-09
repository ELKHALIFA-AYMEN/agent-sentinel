from datetime import datetime, timezone
from typing import Dict, List
import uuid

from app.schemas.agent_payload import AgentActionRequest, InspectionResult


class SentinelStateManager:
    """Gère l'état temps réel du Kill-Switch, des métriques et du journal d'audit."""

    def __init__(self) -> None:
        self.kill_switch_active: bool = False
        self.quarantined_agents: set[str] = set()
        self.total_intercepted: int = 0
        self.threats_blocked: int = 0
        self.estimated_cost_saved: float = 0.0
        self.recent_logs: List[Dict] = []

    def record_event(
        self, payload: AgentActionRequest, result: InspectionResult
    ) -> Dict:
        self.total_intercepted += 1
        if result.status == "BLOCKED":
            self.threats_blocked += 1
            self.estimated_cost_saved = round(
                self.estimated_cost_saved + payload.estimated_cost, 4
            )

        log_entry = {
            "id": f"req-{uuid.uuid4().hex[:6]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": payload.agent_id,
            "action": result.sanitized_prompt,
            "sanitized_prompt": result.sanitized_prompt,
            "tool_called": payload.tool_called or "none",
            "risk_score": result.risk_score,
            "status": result.status,
            "reason": result.reasons[0] if result.reasons else "Aucune anomalie détectée",
            "estimated_cost": payload.estimated_cost,
        }
        self.recent_logs.insert(0, log_entry)
        self.recent_logs = self.recent_logs[:50]
        return log_entry

    def update_log_status(self, log_id: str, decision: str) -> Dict | None:
        for entry in self.recent_logs:
            if entry["id"] == log_id:
                previous_status = entry["status"]
                entry["status"] = decision
                if decision == "BLOCKED" and previous_status != "BLOCKED":
                    self.threats_blocked += 1
                    self.estimated_cost_saved = round(
                        self.estimated_cost_saved + float(entry.get("estimated_cost", 0.0)),
                        4,
                    )
                return entry
        return None


state_manager = SentinelStateManager()
