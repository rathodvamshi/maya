# backend/app/services/ai_service.py

import time
import logging
import json
from typing import List, Optional, Dict, Any

import google.generativeai as genai
import cohere
import anthropic

from app.config import settings
from app.prompt_templates import MAIN_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 AI Client Initialization
# =====================================================
gemini_keys = [key.strip() for key in settings.GEMINI_API_KEYS.split(",") if key.strip()]
current_gemini_key_index = 0
cohere_client = cohere.Client(settings.COHERE_API_KEY) if settings.COHERE_API_KEY else None
anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None

# =====================================================
# 🔹 Circuit Breaker & Provider Fallback
# =====================================================
FAILED_PROVIDERS: dict[str, float] = {}
AI_PROVIDERS = ["gemini", "anthropic", "cohere"]

def _is_provider_available(name: str) -> bool:
    """Check if provider is available (not in cooldown)."""
    failure_time = FAILED_PROVIDERS.get(name)
    if failure_time and (time.time() - failure_time) < settings.AI_PROVIDER_FAILURE_TIMEOUT:
        logger.warning(f"[AI] Provider '{name}' in cooldown. Skipping.")
        return False
    return True

# =====================================================
# 🔹 Provider Helpers
# =====================================================
def _try_gemini(prompt: str) -> str:
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
    if not cohere_client:
        raise RuntimeError("Cohere API client not configured.")
    try:
        response = cohere_client.chat(message=prompt, model="command-r-08-2024")
        return response.text
    except Exception as e:
        raise RuntimeError(f"Cohere API error: {e}")

def _try_anthropic(prompt: str) -> str:
    if not anthropic_client:
        raise RuntimeError("Anthropic API client not configured.")
    try:
        message = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        # Ensure compatibility with newer API responses
        if hasattr(message, "content") and message.content:
            return message.content[0].text
        elif hasattr(message, "completion"):
            return message.completion
        else:
            raise RuntimeError("Anthropic response parsing failed.")
    except Exception as e:
        raise RuntimeError(f"Anthropic API error: {e}")

# =====================================================
# 🔹 Main AI Response Generator
# =====================================================
def get_response(
    prompt: str,
    history: Optional[List[dict]] = None,
    pinecone_context: Optional[str] = None,
    neo4j_facts: Optional[str] = None,
    state: str = "general_conversation"
) -> str:
    """Generates AI response using multiple providers with fallback."""

    history_str = ""
    if history:
        for msg in history:
            speaker = "Human" if msg.get("sender") == "user" else "Assistant"
            history_str += f"{speaker}: {msg.get('text')}\n"

    full_prompt = MAIN_SYSTEM_PROMPT.format(
        neo4j_facts=neo4j_facts or "No facts available.",
        pinecone_context=pinecone_context or "No similar conversations found.",
        state=state,
        history=history_str or "This is the first message in the conversation.",
        prompt=prompt
    )

    logger.debug("----- Full AI Prompt -----\n%s\n--------------------------", full_prompt)

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
            FAILED_PROVIDERS.pop(provider, None)
            return result
        except Exception as e:
            logger.error(f"[AI] Provider '{provider}' failed: {e}")
            FAILED_PROVIDERS[provider] = time.time()

    return "❌ All AI services are currently unavailable. Please try again later."

# =====================================================
# 🔹 Summarization Utility
# =====================================================
def summarize_text(text: str) -> str:
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
# 🔹 Fact Extraction Utility
# =====================================================
def extract_facts_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract structured facts (entities + relationships) from a conversation transcript.
    Returns a JSON dict with 'entities' and 'relationships'.
    """
    extraction_prompt = f"""
    Analyze the following transcript. Your only task is to extract entities and relationships.
    Respond with ONLY a valid JSON object. Do not include markdown, explanations, or any text
    outside of the JSON structure. If no facts are found, return {{"entities": [], "relationships": []}}.

    Transcript:
    ---
    {text}
    ---
    """
    try:
        # Use the providers most suited for structured output
        fact_providers = [_try_gemini, _try_anthropic]
        raw_response = ""
        for func in fact_providers:
            try:
                raw_response = func(extraction_prompt)
                if raw_response:
                    break
            except Exception as e:
                logger.warning(f"Fact extraction attempt failed for provider {func.__name__}: {e}")

        if not raw_response:
            raise RuntimeError("All fact-extraction providers failed.")

        # Attempt robust JSON parsing
        start = raw_response.find("{")
        end = raw_response.rfind("}")
        if start != -1 and end != -1:
            json_str = raw_response[start:end + 1]
            return json.loads(json_str)
        else:
            logger.warning(f"Fact extraction returned no valid JSON. Raw: {raw_response}")
            return {"entities": [], "relationships": []}

    except Exception as e:
        logger.error(f"Failed to extract facts from text: {e}")
        return {"entities": [], "relationships": []}
