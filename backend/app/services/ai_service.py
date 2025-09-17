# backend/app/services/ai_service.py

import time
import logging
import json
from typing import List, Optional, Dict, Any
import google.generativeai as genai
import cohere
import anthropic
from app.config import settings

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 AI Client Initialization
# =====================================================

# Gemini API keys (supports rotation)
gemini_keys = [key.strip() for key in settings.GEMINI_API_KEYS.split(",") if key.strip()]
current_gemini_key_index = 0

# Cohere client (optional)
cohere_client = cohere.Client(settings.COHERE_API_KEY) if settings.COHERE_API_KEY else None

# Anthropic client (optional)
anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None

# =====================================================
# 🔹 Circuit Breaker & Fallback State
# =====================================================
FAILED_PROVIDERS = {}  # Tracks providers that failed recently
AI_PROVIDERS = ["gemini", "anthropic", "cohere"]

def _is_provider_available(name: str) -> bool:
    """
    Checks if a provider is available (not in cooldown).
    """
    failure_time = FAILED_PROVIDERS.get(name)
    if failure_time and (time.time() - failure_time) < settings.AI_PROVIDER_FAILURE_TIMEOUT:
        logger.warning(f"[AI] Provider '{name}' is in cooldown, skipping.")
        return False
    return True

# =====================================================
# 🔹 Provider Helpers
# =====================================================
def _try_gemini(prompt: str) -> str:
    """
    Generates text using Google Gemini with automatic key rotation.
    Raises RuntimeError if all keys fail.
    """
    global current_gemini_key_index
    if not gemini_keys:
        raise RuntimeError("No Gemini API keys configured.")

    start_index = current_gemini_key_index
    while True:
        try:
            key = gemini_keys[current_gemini_key_index]
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-1.5-flash-latest")
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"[Gemini] Key {current_gemini_key_index} failed: {e}")
            current_gemini_key_index = (current_gemini_key_index + 1) % len(gemini_keys)
            if current_gemini_key_index == start_index:
                raise RuntimeError("All Gemini API keys failed.")

def _try_cohere(prompt: str) -> str:
    """
    Generates text using Cohere API.
    """
    if not cohere_client:
        raise RuntimeError("Cohere API client not configured.")
    try:
        response = cohere_client.chat(message=prompt, model="command-r-08-2024")
        return response.text
    except Exception as e:
        raise RuntimeError(f"Cohere API error: {e}")

def _try_anthropic(prompt: str) -> str:
    """
    Generates text using Anthropic Claude API.
    """
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
    history: Optional[List[dict]] = None,
    context: Optional[str] = None,
    state: str = "general_conversation"
) -> str:
    """
    Builds a full AI prompt including:
    - Conversational state
    - Context from past chats
    - Recent history
    - Current user message
    """
    full_prompt = f"CURRENT CONVERSATIONAL STATE: {state}\n\n"

    if context:
        full_prompt += f"CONTEXT (from previous conversation):\n---\n{context}\n---\n\n"

    if history:
        full_prompt += "RECENT CHAT HISTORY:\n"
        for msg in history:
            speaker = "Human" if msg.get("sender") == "user" else "Assistant"
            full_prompt += f"{speaker}: {msg.get('text')}\n"
        full_prompt += "\n"

    full_prompt += f"NOW RESPOND TO THE HUMAN:\nHuman: {prompt}"
    return full_prompt

# =====================================================
# 🔹 Main AI Response Generator
# =====================================================
def get_response(
    prompt: str,
    history: Optional[List[dict]] = None,
    context: Optional[str] = None,
    state: str = "general_conversation"
) -> str:
    """
    Returns an AI response using the fallback chain:
    Gemini -> Anthropic -> Cohere
    Implements circuit breaker for failing providers.
    """
    full_prompt = _construct_prompt(prompt, history, context, state)
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

            # Reset failure record if successful
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
    Generates a concise, third-person summary of a conversation or transcript.
    Uses the best available AI provider with fallback.
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

# =====================================================
# 🔹 Fact Extraction
# =====================================================
def extract_facts_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Extracts structured facts (entities and relationships) from a conversation transcript.
    Returns a JSON dictionary with keys "entities" and "relationships".
    """
    extraction_prompt = f"""
    You are a highly intelligent data extraction agent. Analyze the following conversation
    transcript. Extract key entities and relationships. Present your findings in JSON format:

    - "entities": list of objects with "name" and "label" (e.g., PERSON, CITY, TOPIC, PREFERENCE)
    - "relationships": list of objects with "source", "target", and "type" (e.g., LIKES, PLANS_TRIP_TO)

    Example:
    Transcript: "Hi, my name is Alex. I want to plan a trip to Paris. I really love museums."
    JSON output:
    {{
      "entities": [
        {{"name": "Alex", "label": "PERSON"}},
        {{"name": "Paris", "label": "CITY"}},
        {{"name": "Museums", "label": "PREFERENCE"}}
      ],
      "relationships": [
        {{"source": "Alex", "target": "Paris", "type": "PLANS_TRIP_TO"}},
        {{"source": "Alex", "target": "Museums", "type": "HAS_PREFERENCE_FOR"}}
      ]
    }}

    Now, analyze this transcript:
    ---
    {text}
    ---
    JSON output:
    """
    try:
        raw_json_response = get_response(extraction_prompt)
        json_str = raw_json_response.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Failed to extract facts or parse JSON from AI response: {e}")
        return None
