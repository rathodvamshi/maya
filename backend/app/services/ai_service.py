# backend/app/services/ai_service.py

import time
import logging
from typing import List, Optional
import google.generativeai as genai
import cohere
import anthropic
from app.config import settings

logger = logging.getLogger(__name__)

# =====================================================
# Client Initialization
# =====================================================
gemini_keys = [key.strip() for key in settings.GEMINI_API_KEYS.split(",") if key.strip()]
cohere_client = cohere.Client(settings.COHERE_API_KEY) if settings.COHERE_API_KEY else None
anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None

# Key rotation state
current_gemini_key_index = 0

# =====================================================
# Circuit Breaker State
# =====================================================
FAILED_PROVIDERS = {}  # { provider_name: last_failure_time }
AI_PROVIDERS = ["gemini", "anthropic", "cohere"]


def _is_provider_available(name: str) -> bool:
    """Checks if a provider is currently available (not in cooldown)."""
    failure_time = FAILED_PROVIDERS.get(name)
    if failure_time and (time.time() - failure_time) < settings.AI_PROVIDER_FAILURE_TIMEOUT:
        logger.warning(f"[AI] Provider '{name}' is in cooldown after failure, skipping.")
        return False
    return True


# =====================================================
# Gemini with Key Rotation
# =====================================================
def _try_gemini(prompt: str) -> str:
    global current_gemini_key_index
    if not gemini_keys:
        raise RuntimeError("No Gemini API keys configured.")

    start_index = current_gemini_key_index
    while True:
        try:
            key_to_try = gemini_keys[current_gemini_key_index]
            genai.configure(api_key=key_to_try)
            model = genai.GenerativeModel("gemini-1.5-flash-latest")
            response = model.generate_content(prompt)
            return response.text

        except Exception as e:
            logger.error(f"[Gemini] Key {current_gemini_key_index} failed: {e}")
            current_gemini_key_index = (current_gemini_key_index + 1) % len(gemini_keys)

            if current_gemini_key_index == start_index:
                raise RuntimeError("All Gemini API keys failed.")


# =====================================================
# Cohere helper
# =====================================================
def _try_cohere(prompt: str) -> str:
    if not cohere_client:
        raise RuntimeError("Cohere API client not configured.")
    try:
        response = cohere_client.chat(message=prompt, model="command-r-08-2024")
        return response.text
    except Exception as e:
        raise RuntimeError(f"Cohere API error: {e}")


# =====================================================
# Anthropic helper
# =====================================================
def _try_anthropic(prompt: str) -> str:
    if not anthropic_client:
        raise RuntimeError("Anthropic API client not configured.")
    try:
        message = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",  # fast + affordable
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as e:
        raise RuntimeError(f"Anthropic API error: {e}")


# =====================================================
# Prompt Construction
# =====================================================
def _construct_prompt(prompt: str, history: Optional[List[dict]], context: Optional[str]) -> str:
    """Builds a full AI prompt with context + history + user message."""
    full_prompt = ""
    if context:
        full_prompt += f"CONTEXT (from earlier conversation):\n---\n{context}\n---\n\n"
    if history:
        full_prompt += "RECENT CHAT HISTORY:\n"
        for msg in history:
            speaker = "Human" if msg.get("sender") == "user" else "Assistant"
            full_prompt += f"{speaker}: {msg.get('text')}\n"
        full_prompt += "\n"
    full_prompt += f"NOW RESPOND TO THE HUMAN:\nHuman: {prompt}"
    return full_prompt


# =====================================================
# Main Response Generator (with Fallback + Circuit Breaker)
# =====================================================
def get_response(prompt: str, history: Optional[List[dict]] = None, context: Optional[str] = None) -> str:
    """Gets an AI response using Gemini → Anthropic → Cohere with fallback and circuit breaker."""
    full_prompt = _construct_prompt(prompt, history, context)

    for provider in AI_PROVIDERS:
        if not _is_provider_available(provider):
            continue

        try:
            if provider == "gemini":
                result = _try_gemini(full_prompt)
            elif provider == "anthropic":
                result = _try_anthropic(full_prompt)
            elif provider == "cohere":
                result = _try_cohere(full_prompt)
            else:
                continue

            FAILED_PROVIDERS.pop(provider, None)  # clear failure on success
            return result

        except Exception as e:
            logger.error(f"[AI] Provider '{provider}' failed: {e}")
            FAILED_PROVIDERS[provider] = time.time()  # mark as failed

    return "❌ All AI services are currently unavailable. Please try again later."


# =====================================================
# Summarization
# =====================================================
def summarize_text(text: str) -> str:
    """Uses the best available AI provider to summarize text."""
    summary_prompt = (
        "You are an expert at summarizing conversations. "
        "Provide a concise, third-person summary of the following transcript:\n\n"
        f"---\n{text}\n---\n\nSUMMARY:"
    )

    for provider in AI_PROVIDERS:
        if not _is_provider_available(provider):
            continue
        try:
            if provider == "gemini":
                return _try_gemini(summary_prompt)
            elif provider == "anthropic":
                return _try_anthropic(summary_prompt)
            elif provider == "cohere":
                return _try_cohere(summary_prompt)
        except Exception as e:
            logger.error(f"[AI] Summarization failed with '{provider}': {e}")
            FAILED_PROVIDERS[provider] = time.time()

    return "❌ Failed to generate summary. All AI services unavailable."
