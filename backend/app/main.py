from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.redis_store import kill_switch_store
from app.core.websocket import ConnectionManager, blocked_agents, manager
from app.api.intercept import router as intercept_router

__all__ = ["app", "ConnectionManager", "manager", "blocked_agents"]

app = FastAPI(
    title="AgentSentinel API",
    description="Plateforme de monitoring, de sécurité et de Kill-Switch en temps réel pour agents IA d'entreprise.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(intercept_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "AgentSentinel"}


@app.post("/api/v1/agents/{agent_id}/kill")
async def kill_agent(agent_id: str):
    """Ajoute l'agent dans blocked_agents et diffuse une alerte WebSocket AGENT_TERMINATED."""
    kill_switch_store.add_blocked_agent(agent_id)
    alert_message = {
        "type": "AGENT_KILLED",
        "agent_id": agent_id,
        "status": "AGENT_TERMINATED",
        "risk_score": 1.0,
        "reasons": ["Agent révoqué par le Kill-Switch administrateur"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast(alert_message)
    return {
        "status": "AGENT_TERMINATED",
        "agent_id": agent_id,
        "message": "Agent révoqué par le Kill-Switch administrateur",
        "blocked_agents": list(kill_switch_store.get_all_blocked()),
    }


@app.post("/api/v1/agents/{agent_id}/restore")
async def restore_agent(agent_id: str):
    """Réactive un agent précédemment révoqué."""
    kill_switch_store.remove_blocked_agent(agent_id)
    alert_message = {
        "type": "AGENT_RESTORED",
        "agent_id": agent_id,
        "status": "APPROVED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast(alert_message)
    return {
        "status": "ARMED",
        "agent_id": agent_id,
        "blocked_agents": list(kill_switch_store.get_all_blocked()),
    }


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
