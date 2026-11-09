import re
from typing import List, Tuple

from app.ml.anomaly_detector import BehavioralAnomalyDetector
from app.schemas.agent_payload import AgentActionRequest, InspectionResult


class AgentInspector:
    """Service d'inspection, de masquage PII et d'évaluation du risque des requêtes d'agents IA."""

    INJECTION_PATTERNS: List[str] = [
        "ignore previous instructions",
        "ignore instructions",
        "drop table",
        "system override",
        "bypass security",
        "ignore all rules",
    ]

    SENSITIVE_TOOLS: List[str] = [
        "delete",
        "execute",
        "payment",
    ]

    # Expressions régulières pour le masquage PII (ordre important : Carte Bancaire avant Téléphone)
    EMAIL_REGEX = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )
    CARD_REGEX = re.compile(
        r"\b(?:\d{4}[-\s]?){3}\d{4}\b"
    )
    PHONE_REGEX = re.compile(
        r"(?:(?:\+|00)\d{1,3}[\s.-]?\(?\d{1,4}\)?(?:[\s.-]?\d{2,4}){2,4}|\b0[1-9](?:[\s.-]?\d{2}){4}\b)"
    )

    HIGH_COST_THRESHOLD: float = 10.0

    def __init__(self) -> None:
        self.anomaly_detector = BehavioralAnomalyDetector()

    def sanitize_pii(self, text: str) -> Tuple[str, List[str]]:
        """Détecte et masque les données personnelles (Emails, Cartes bancaires, Téléphones)."""
        sanitized = text
        detected_types: List[str] = []

        # 1. Emails -> [EMAIL_PROTECTED]
        if self.EMAIL_REGEX.search(sanitized):
            sanitized = self.EMAIL_REGEX.sub("[EMAIL_PROTECTED]", sanitized)
            detected_types.append("EMAIL")

        # 2. Cartes bancaires (16 chiffres avec ou sans espaces/tirets) -> [CARD_MASKED]
        if self.CARD_REGEX.search(sanitized):
            sanitized = self.CARD_REGEX.sub("[CARD_MASKED]", sanitized)
            detected_types.append("CARD")

        # 3. Numéros de téléphone français ou internationaux -> [PHONE_MASKED]
        if self.PHONE_REGEX.search(sanitized):
            sanitized = self.PHONE_REGEX.sub("[PHONE_MASKED]", sanitized)
            detected_types.append("PHONE")

        return sanitized, detected_types

    def inspect(self, payload: AgentActionRequest) -> InspectionResult:
        risk_score = 0.0
        reasons: List[str] = []
        sanitized_prompt = payload.prompt

        # 1. Nettoyage des données sensibles (PII Masking)
        sanitized_prompt, pii_types = self.sanitize_pii(sanitized_prompt)
        if pii_types:
            risk_score += 0.2 * len(pii_types)
            for pii_type in pii_types:
                reasons.append(f"Donnée sensible détectée et masquée : {pii_type}")

        # 2. Détection d'injections de prompt basiques
        prompt_lower = payload.prompt.lower()
        for pattern in self.INJECTION_PATTERNS:
            if pattern in prompt_lower:
                risk_score += 0.85
                reasons.append(f"Motif d'injection de prompt détecté : '{pattern}'")
                sanitized_prompt = re.sub(
                    re.escape(pattern),
                    "[REDACTED]",
                    sanitized_prompt,
                    flags=re.IGNORECASE,
                )

        # 3. Détection d'actions / outils sensibles
        if payload.tool_called:
            tool_lower = payload.tool_called.lower()
            matched_keywords = [
                kw for kw in self.SENSITIVE_TOOLS if kw in tool_lower
            ]
            if matched_keywords:
                risk_score += 0.5
                reasons.append(
                    f"Appel d'un outil sensible détecté : '{payload.tool_called}' (mots-clés : {', '.join(matched_keywords)})"
                )

        # 4. Vérification des paramètres pour détecter d'éventuelles injections cachées
        if payload.parameters:
            params_str = str(payload.parameters).lower()
            for pattern in self.INJECTION_PATTERNS:
                if pattern in params_str:
                    risk_score += 0.85
                    reasons.append(f"Motif suspect dans les paramètres de l'outil : '{pattern}'")

        # 5. Évaluation du coût estimé
        if payload.estimated_cost >= self.HIGH_COST_THRESHOLD:
            risk_score += 0.3
            reasons.append(
                f"Coût estimé élevé ({payload.estimated_cost}$ >= {self.HIGH_COST_THRESHOLD}$)"
            )

        # 6. Détection d'anomalies comportementales (boucles répétitives / dérive de budget)
        ml_risk, ml_reasons = self.anomaly_detector.evaluate(payload)
        if ml_risk > 0:
            risk_score += ml_risk
            reasons.extend(ml_reasons)

        # Bornage du score entre 0.0 et 1.0
        risk_score = min(max(round(risk_score, 2), 0.0), 1.0)

        # Détermination du statut selon le score de risque
        if risk_score >= 0.8:
            status = "BLOCKED"
        elif risk_score >= 0.5:
            status = "PENDING_APPROVAL"
        else:
            status = "APPROVED"
            if not reasons:
                reasons.append("Aucune anomalie détectée.")

        return InspectionResult(
            status=status,
            risk_score=risk_score,
            reasons=reasons,
            sanitized_prompt=sanitized_prompt,
        )
