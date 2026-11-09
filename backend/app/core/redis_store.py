"""Adaptateur de persistance Redis avec repli automatique (fallback) en mémoire."""

from typing import Optional, Set
import redis

from app.core.config import settings
from app.core.websocket import blocked_agents


class KillSwitchStore:
    """Synchronise les agents révoqués avec Redis si disponible, sinon utilise blocked_agents en mémoire."""

    REDIS_SET_KEY = "agentsentinel:blocked_agents"

    def __init__(self) -> None:
        self._redis: Optional[redis.Redis] = None
        try:
            client = redis.Redis.from_url(
                settings.REDIS_URL, decode_responses=True, socket_connect_timeout=0.3
            )
            client.ping()
            self._redis = client
        except Exception:
            self._redis = None

    @property
    def is_redis_connected(self) -> bool:
        return self._redis is not None

    def add_blocked_agent(self, agent_id: str) -> None:
        blocked_agents.add(agent_id)
        if self._redis is not None:
            try:
                self._redis.sadd(self.REDIS_SET_KEY, agent_id)
            except Exception:
                pass

    def remove_blocked_agent(self, agent_id: str) -> None:
        blocked_agents.discard(agent_id)
        if self._redis is not None:
            try:
                self._redis.srem(self.REDIS_SET_KEY, agent_id)
            except Exception:
                pass

    def is_agent_blocked(self, agent_id: str) -> bool:
        if agent_id in blocked_agents:
            return True
        if self._redis is not None:
            try:
                if self._redis.sismember(self.REDIS_SET_KEY, agent_id):
                    blocked_agents.add(agent_id)
                    return True
            except Exception:
                pass
        return False

    def get_all_blocked(self) -> Set[str]:
        if self._redis is not None:
            try:
                members = self._redis.smembers(self.REDIS_SET_KEY)
                blocked_agents.update(members)
            except Exception:
                pass
        return set(blocked_agents)


kill_switch_store = KillSwitchStore()
