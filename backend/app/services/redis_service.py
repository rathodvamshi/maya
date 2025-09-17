# backend/app/services/redis_service.py

import redis
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# This reuses the redis_client you may have defined elsewhere,
# or creates a new one. A single client is efficient.
try:
    redis_pool = redis.ConnectionPool(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True # Automatically decode responses to strings
    )
    redis_client = redis.Redis(connection_pool=redis_pool)
    redis_client.ping()
    logger.info("✅ Successfully connected to Redis for state management.")
except Exception as e:
    logger.error(f"❌ Failed to connect to Redis: {e}")
    redis_client = None

def get_session_state(session_id: str) -> str:
    """
    Retrieves the current conversational state for a given session.
    Defaults to 'initial_greeting' if no state is found.
    """
    if not redis_client:
        return 'general_conversation' # Fallback if Redis is down

    state_key = f"session:state:{session_id}"
    state = redis_client.get(state_key)
    return state if state else 'initial_greeting'

def set_session_state(session_id: str, state: str):
    """
    Sets the conversational state for a session with a 24-hour expiration.
    """
    if not redis_client:
        return

    state_key = f"session:state:{session_id}"
    # The state will automatically expire after 24 hours of inactivity
    redis_client.set(state_key, state, ex=86400) # ex=seconds