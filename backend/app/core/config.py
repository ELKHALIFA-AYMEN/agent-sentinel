import os


class Settings:
    """Configuration globale d'AgentSentinel."""

    PROJECT_NAME: str = "AgentSentinel"
    VERSION: str = "0.1.0"
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    HIGH_COST_THRESHOLD: float = float(os.getenv("HIGH_COST_THRESHOLD", "10.0"))


settings = Settings()
