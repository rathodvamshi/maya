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
# 🔹 Client Initialization
# =====================================================

# Gemini API keys (supports multiple keys for rotation)
gemini_keys = [key.strip() for key in settings.GEMINI_API_KEYS.split(",") if key.strip()]

# Cohere client (optional if key is provided)
cohere_client = cohere.Client(settings.COHERE_API_KEY) if settings.COHERE_API_KEY else None

# Anthropic client (optional if key is provided)
anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None

# Key rotation state for Gemini
current_gemini_key_index = 0

# =====================================================
# 🔹 Circuit Breaker / Fallback State
# =====================================================

FAILED_PROVIDERS = {}  # { provider_name: last_failure_time }
AI_PROVIDERS = ["gemini", "anthropic", "cohere"]


def _is_provider_available(name: str) -> bool:
    """
    Checks if a provider is currently available (not in cooldown).
    If the provider failed recently, skip it until the timeout expires.
    """
    failure_time = FAILED_PROVIDERS.get(name)
    if failure_time and (time.time() - failure_time) < settings.AI_PROVIDER_FAILURE_TIMEOUT:
        logger.warning(f"[AI] Provider '{name}' is in cooldown after failure, skipping.")
        return False
    return True


# =====================================================
# 🔹 Gemini Helper (with Key Rotation)
# =====================================================
def _try_gemini(prompt: str) -> str:
    """Attempts to generate content using Google Gemini with key rotation."""
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

            # All keys tried, raise error
            if current_gemini_key_index == start_index:
                raise RuntimeError("All Gemini API keys failed.")


# =====================================================
# 🔹 Cohere Helper
# =====================================================
def _try_cohere(prompt: str) -> str:
    """Generates content using Cohere API."""
    if not cohere_client:
        raise RuntimeError("Cohere API client not configured.")

    try:
        response = cohere_client.chat(message=prompt, model="command-r-08-2024")
        return response.text
    except Exception as e:
        raise RuntimeError(f"Cohere API error: {e}")


# =====================================================
# 🔹 Anthropic Helper
# =====================================================
def _try_anthropic(prompt: str) -> str:
    """Generates content using Anthropic Claude."""
    if not anthropic_client:
        raise RuntimeError("Anthropic API client not configured.")

    try:
        message = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as e:
        raise RuntimeError(f"Anthropic API error: {e}")


# =====================================================
# 🔹 Prompt Construction
# =====================================================
def _construct_prompt(
    prompt: str,
    history: Optional[List[dict]],
    context: Optional[str],
    state: str = "general_conversation"
) -> str:
    """
    Builds a full AI prompt including:
    - Conversational state
    - Context from previous conversations
    - Recent chat history
    - Current user message
    """
    full_prompt = f"CURRENT CONVERSATIONAL STATE: {state}\n\n"

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
# 🔹 Main Response Generator (Fallback + Circuit Breaker)
# =====================================================
def get_response(
    prompt: str,
    history: Optional[List[dict]] = None,
    context: Optional[str] = None,
    state: str = "general_conversation"
) -> str:
    """
    Returns an AI response using the fallback chain:
    Gemini → Anthropic → Cohere
    Implements circuit breaker for failing providers.
    """
    full_prompt = _construct_prompt(prompt, history, context, state)

    # Debugging: see what prompt is sent
    logger.debug("----- Prompt Sent to AI -----\n%s\n-----------------------------", full_prompt)

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

            # Clear failure on success
            FAILED_PROVIDERS.pop(provider, None)
            return result

        except Exception as e:
            logger.error(f"[AI] Provider '{provider}' failed: {e}")
            FAILED_PROVIDERS[provider] = time.time()

    return "❌ All AI services are currently unavailable. Please try again later."


# =====================================================
# 🔹 Summarization
# =====================================================
def summarize_text(text: str) -> str:
    """
    Generates a concise summary of a conversation or transcript
    using the best available AI provider.
    """
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
