"""SDK client et décorateur Python pour protéger les outils d'agents IA avec AgentSentinel."""

from functools import wraps
from typing import Any, Callable, Dict, Optional
import httpx


class AgentTerminatedError(PermissionError):
    """Exception levée lorsqu'une action d'agent est bloquée ou que l'agent est révoqué."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.details = details or {}


class SentinelClient:
    """Client léger permettant à un agent IA de valider ses actions auprès d'AgentSentinel."""

    def __init__(
        self,
        agent_id: str,
        base_url: str = "http://localhost:8000",
        http_client: Optional[Any] = None,
    ) -> None:
        self.agent_id = agent_id
        self.base_url = base_url.rstrip("/")
        self._client = http_client

    def verify_action(
        self,
        prompt: str,
        tool_called: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        estimated_cost: float = 0.01,
    ) -> Dict[str, Any]:
        payload = {
            "agent_id": self.agent_id,
            "prompt": prompt,
            "tool_called": tool_called,
            "parameters": parameters or {},
            "estimated_cost": estimated_cost,
        }
        if self._client is not None:
            response = self._client.post("/api/v1/intercept", json=payload)
        else:
            response = httpx.post(
                f"{self.base_url}/api/v1/intercept", json=payload, timeout=5.0
            )

        if response.status_code == 403:
            detail = response.json().get("detail", {})
            reasons = detail.get("reasons", ["Action blocked by AgentSentinel"])
            raise AgentTerminatedError(
                f"AgentSentinel BLOCKED ({self.agent_id}): {', '.join(reasons)}",
                details=detail,
            )

        response.raise_for_status()
        return response.json()

    def guard_tool(
        self, estimated_cost: float = 0.01
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Décorateur qui intercepte automatiquement l'exécution d'un outil Python."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                prompt_context = kwargs.get("prompt") or f"Execute {func.__name__}"
                self.verify_action(
                    prompt=str(prompt_context),
                    tool_called=func.__name__,
                    parameters=kwargs,
                    estimated_cost=estimated_cost,
                )
                return func(*args, **kwargs)

            return wrapper

        return decorator
