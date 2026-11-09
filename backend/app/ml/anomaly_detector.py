from collections import defaultdict, deque
import time
from typing import Deque, Dict, List, Tuple

from app.schemas.agent_payload import AgentActionRequest


class BehavioralAnomalyDetector:
    """Détecteur comportemental temps réel (boucles infinies, dérive de coûts, obfuscation)."""

    def __init__(
        self,
        window_seconds: float = 60.0,
        max_repeated_calls: int = 4,
        budget_window_limit: float = 25.0,
    ) -> None:
        self.window_seconds = window_seconds
        self.max_repeated_calls = max_repeated_calls
        self.budget_window_limit = budget_window_limit
        # Historique par agent : deque de tuples (timestamp, tool_called, prompt_hash, cost)
        self._agent_history: Dict[str, Deque[Tuple[float, str, int, float]]] = defaultdict(deque)

    def reset(self) -> None:
        """Réinitialise l'historique comportemental."""
        self._agent_history.clear()

    def evaluate(self, payload: AgentActionRequest) -> Tuple[float, List[str]]:
        """Retourne (score_de_risque_additionnel, motifs_d_anomalie)."""
        now = time.time()
        history = self._agent_history[payload.agent_id]

        # Purge des événements hors de la fenêtre glissante
        while history and (now - history[0][0]) > self.window_seconds:
            history.popleft()

        tool_name = (payload.tool_called or "none").lower()
        prompt_sig = hash(payload.prompt.strip().lower())
        history.append((now, tool_name, prompt_sig, payload.estimated_cost))

        added_risk = 0.0
        reasons: List[str] = []

        # 1. Détection de boucle répétitive (Runaway Agent Loop)
        identical_actions = sum(
            1 for _, t, p, _ in history if t == tool_name and p == prompt_sig
        )
        if identical_actions >= self.max_repeated_calls:
            added_risk += 0.85
            reasons.append(
                f"Boucle d'agent détectée (Runaway Loop) : {identical_actions} appels identiques en < {int(self.window_seconds)}s"
            )

        # 2. Détection de dérive budgétaire cumulée sur la fenêtre glissante
        rolling_cost = sum(c for _, _, _, c in history)
        if rolling_cost >= self.budget_window_limit:
            added_risk += 0.5
            reasons.append(
                f"Dérive budgétaire détectée : {rolling_cost:.2f}$ cumulés sur {int(self.window_seconds)}s (seuil : {self.budget_window_limit:.2f}$)"
            )

        return added_risk, reasons
