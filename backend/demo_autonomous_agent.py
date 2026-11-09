"""Démonstration d'un agent IA autonome protégé en temps réel par AgentSentinel.

Lancez ce script pendant que le backend FastAPI et le dashboard Next.js tournent,
puis cliquez sur le bouton rouge 'EMERGENCY KILL-SWITCH' dans l'interface web
pour observer l'arrêt instantané de l'agent dans le terminal.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.sdk.sentinel_client import AgentTerminatedError, SentinelClient

AGENT_ID = "agent-fintech-autonomous-01"
sentinel = SentinelClient(agent_id=AGENT_ID, base_url="http://localhost:8000")


@sentinel.guard_tool(estimated_cost=0.04)
def fetch_pending_invoices(batch_size: int = 10, prompt: str = "") -> str:
    return f"Récupération de {batch_size} factures fournisseurs..."


@sentinel.guard_tool(estimated_cost=0.12)
def verify_iban_compliance(iban: str, prompt: str = "") -> str:
    return f"IBAN {iban} vérifié."


def run_autonomous_loop() -> None:
    print(f"=== Démarrage de l'agent autonome : {AGENT_ID} ===")
    print("Supervisé en temps réel par AgentSentinel (http://localhost:3000)")
    print("Cliquez sur 'EMERGENCY KILL-SWITCH' dans le dashboard pour interrompre l'agent.\n")

    step = 1
    while True:
        try:
            res1 = fetch_pending_invoices(
                batch_size=5,
                prompt=f"[Étape #{step}] Lecture du lot de factures entrantes #{step}",
            )
            print(f"[APPROVED] {res1}")
            time.sleep(2.5)

            res2 = verify_iban_compliance(
                iban=f"FR76-3000-4000-{1000 + step}",
                prompt=f"[Étape #{step}] Contrôle de conformité bancaire lot #{step}",
            )
            print(f"[APPROVED] {res2}")
            time.sleep(2.5)
            step += 1

        except AgentTerminatedError as exc:
            print("\n" + "!" * 72)
            print(f"[KILL-SWITCH INTERCEPTED] {exc}")
            print("L'agent autonome a été immédiatement interrompu par AgentSentinel.")
            print("!" * 72)
            break
        except Exception as exc:
            print(f"[ERREUR CONNEXION] Serveur AgentSentinel injoignable : {exc}")
            break


if __name__ == "__main__":
    run_autonomous_loop()
