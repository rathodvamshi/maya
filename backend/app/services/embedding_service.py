import time
import logging
from app.config import settings
from app.services import gemini_service, cohere_service

logger = logging.getLogger(__name__)

# -------------------------------
# Circuit Breaker for Providers
# -------------------------------
FAILED_PROVIDERS: dict[str, float] = {}  # { provider_name: last_failure_time }

# Provider priority order: Gemini → Cohere
EMBEDDING_PROVIDERS = [
    ("gemini", gemini_service.create_embedding),
    ("cohere", cohere_service.create_embedding),
]


def is_provider_available(name: str) -> bool:
    """
    Checks if a provider is available (i.e., not in failure timeout).
    """
    failure_time = FAILED_PROVIDERS.get(name)
    if failure_time and (time.time() - failure_time) < settings.AI_PROVIDER_FAILURE_TIMEOUT:
        logger.warning(f"[Embedding] Provider '{name}' temporarily disabled (cooldown active).")
        return False
    return True


def create_embedding(text: str) -> list[float]:
    """
    Attempts to create an embedding using providers in priority order.
    Falls back if one fails. Circuit-breaker avoids rapid retries.

    Raises:
        RuntimeError: If all providers fail.
    """
    for name, provider_func in EMBEDDING_PROVIDERS:
        if not is_provider_available(name):
            continue

        try:
            logger.info(f"[Embedding] Trying provider '{name}'.")
            embedding = provider_func(text)

            if not embedding:
                raise ValueError("Empty embedding returned")

            # ✅ Success → clear failure state
            FAILED_PROVIDERS.pop(name, None)
            return embedding

        except Exception as e:
            logger.error(f"[Embedding] Provider '{name}' failed: {e}")
            FAILED_PROVIDERS[name] = time.time()

    # 🚨 If no provider succeeded
    raise RuntimeError("All embedding providers failed. Check logs for details.")
