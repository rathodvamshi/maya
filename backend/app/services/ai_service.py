# backend/app/services/ai_service.py

import google.generativeai as genai
import cohere
import anthropic
from app.config import settings

# --- Client Initialization ---
gemini_keys = [key.strip() for key in settings.GEMINI_API_KEYS.split(',')]
cohere_client = cohere.Client(settings.COHERE_API_KEY)
anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# --- Global State for Key Rotation ---
current_gemini_key_index = 0

def _try_gemini(prompt: str):
    """Attempts to get a response from Gemini, rotating keys on failure."""
    global current_gemini_key_index
    if not gemini_keys or not all(gemini_keys):
        raise ValueError("Gemini API keys are not configured.")

    start_index = current_gemini_key_index
    while True:
        try:
            key_to_try = gemini_keys[current_gemini_key_index]
            genai.configure(api_key=key_to_try)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Gemini key at index {current_gemini_key_index} failed. Error: {e}")
            current_gemini_key_index = (current_gemini_key_index + 1) % len(gemini_keys)
            if current_gemini_key_index == start_index:
                print("All Gemini keys failed.")
                # Add more descriptive error for chat workflow
                raise RuntimeError(f"All Gemini API keys failed. Last error: {e}. Please check your quota or API keys.")

def _try_cohere(prompt: str):
    """Gets a response from Cohere."""
    try:
        # Use a supported Cohere model (see docs for latest options)
        response = cohere_client.chat(message=prompt, model="command-r-08-2024")
        return response.text
    except Exception as e:
        print(f"Cohere API failed. Error: {e}")
        # Add more descriptive error for chat workflow
        raise RuntimeError(f"Cohere API error: {e}. Please check your model name or API quota.")

def _try_anthropic(prompt: str):
    """Gets a response from Anthropic (Claude)."""
    try:
        message = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except Exception as e:
        print(f"Anthropic API failed. Error: {e}")
        # Add more descriptive error for chat workflow
        raise RuntimeError(f"Anthropic API error: {e}. Please check your credit balance or API key.")

# --- Unified Generation Function ---
# This is the only function our routers will need to call.
def generate_ai_response(prompt: str) -> str:
    """
    Tries to generate a response using a prioritized list of AI services.
    It will always try Gemini first.
    """
    # Prioritized list of generation functions
    service_fallbacks = [_try_gemini, _try_cohere, _try_anthropic]

    for service_func in service_fallbacks:
        try:
            # Attempt to get a response from the current service in the list
            response = service_func(prompt)
            # If successful, return the response immediately
            return response
        except Exception:
            # If the service fails for any reason (rate limit, invalid key, etc.),
            # the loop will simply continue to the next service.
            continue
    
    # If all services fail, return a final error message.
    return "I'm sorry, all of my AI services are currently unavailable. Please try again later."
