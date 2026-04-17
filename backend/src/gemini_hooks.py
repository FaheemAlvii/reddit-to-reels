"""
AI integration for generating attention-grabbing hooks and thumbnail text.

Supports two providers:
  - Gemini (Google AI Studio / generativelanguage endpoint)
  - OpenRouter (any model via openrouter.ai)

When enabled, this module:
1. Takes the full story text and generates a 3-4 second spoken hook/teaser
   that grabs attention WITHOUT spoiling the story.
2. Generates eye-catching thumbnail text optimized for clicks.

Both outputs are generated before TTS so the hook can be naturally
prepended to the narration timeline.
"""

import json
import os
import sys
import requests
from typing import Optional, Tuple

if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Prompts ──────────────────────────────────────────────────────────

HOOK_SYSTEM_PROMPT = """You are a viral short-form video scriptwriter. Your job is to write a spoken hook — the FIRST thing the narrator says — that makes viewers STOP scrolling.

Rules:
- The hook must be 1-2 sentences, speakable in 3-4 seconds max.
- It must tease the story's most dramatic/shocking/emotional element WITHOUT giving away the ending or resolution.
- Use direct, punchy language. Address the viewer or use rhetorical questions.
- Do NOT include any hashtags, emojis, or stage directions.
- Output ONLY the hook text, nothing else."""

THUMBNAIL_SYSTEM_PROMPT = """You are a viral thumbnail text copywriter for short-form video (TikTok/Reels/Shorts).

Rules:
- Write 3-6 words of BOLD, eye-catching text that would overlay a thumbnail image.
- It should create curiosity or shock value related to the story.
- Use ALL CAPS or Title Case for maximum impact.
- Do NOT spoil the story's resolution.
- Do NOT use hashtags or emojis.
- Output ONLY the thumbnail text, nothing else."""

# ── Default models per provider ──────────────────────────────────────

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash-preview-05-20",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash-lite",
]

OPENROUTER_MODELS = [
    "google/gemma-3-27b-it:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-4b-it:free",
    "google/gemma-3-1b-it:free",
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-2.5-flash-preview:thinking",
    "deepseek/deepseek-chat-v3-0324:free",
    "meta-llama/llama-4-maverick:free",
    "qwen/qwen3-235b-a22b:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
]

OLLAMA_MODELS = [
    "llama3.2",
    "llama3.1",
    "gemma3",
    "gemma2",
    "mistral",
    "qwen2.5",
    "phi3",
    "deepseek-r1",
]

NVIDIA_NIM_MODELS = [
    "meta/llama-3.1-405b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "google/gemma-2-27b-it",
    "google/gemma-2-9b-it",
    "mistralai/mixtral-8x22b-instruct-v0.1",
    "mistralai/mistral-large-2-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "deepseek-ai/deepseek-r1",
]

DEFAULT_OLLAMA_URL = "http://localhost:11434"


# ── Provider calls ───────────────────────────────────────────────────

def _call_gemini(api_key: str, prompt: str, system_prompt: str, model: str = "gemini-2.0-flash") -> Optional[str]:
    """Call the Gemini API. Returns generated text or None on failure."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 150,
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()

        print(f"⚠️  Gemini returned no candidates")
        return None

    except requests.exceptions.HTTPError as e:
        print(f"❌ Gemini API error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text[:300]}")
        return None
    except Exception as e:
        print(f"❌ Gemini request failed: {e}")
        return None


def _call_openrouter(api_key: str, prompt: str, system_prompt: str, model: str = "google/gemini-2.0-flash-exp:free") -> Optional[str]:
    """Call the OpenRouter API. Returns generated text or None on failure."""
    url = "https://openrouter.ai/api/v1/chat/completions"

    # Ensure API key is properly formatted
    clean_key = api_key.strip()
    if not clean_key:
        print("❌ OpenRouter API key is empty!")
        return None

    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://reddit-reel-maker.app",
        "X-Title": "Reddit Reel Maker",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.9,
        "max_tokens": 150,
    }

    print(f"🔗 OpenRouter request: model={model}, key={clean_key[:8]}...{clean_key[-4:]}")

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)

        # Log status before raising
        print(f"📡 OpenRouter response status: {resp.status_code}")

        if resp.status_code == 401:
            print(f"❌ OpenRouter 401 Unauthorized — API key is invalid or expired")
            print(f"   Key used: {clean_key[:8]}...{clean_key[-4:]}")
            return None

        if resp.status_code == 429:
            print(f"⚠️  OpenRouter 429 Rate Limited — too many requests or free tier limit reached")
            print(f"   Response: {resp.text[:300]}")
            return None

        resp.raise_for_status()
        data = resp.json()

        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if content:
                return content.strip()

        print(f"⚠️  OpenRouter returned no choices: {resp.text[:200]}")
        return None

    except requests.exceptions.HTTPError as e:
        print(f"❌ OpenRouter API error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ OpenRouter request failed: {e}")
        return None


def _strip_thinking_tags(text: str) -> str:
    """Strip <think>...</think> reasoning blocks from model output (e.g. DeepSeek-R1)."""
    import re
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text


def _call_ollama(base_url: str, prompt: str, system_prompt: str, model: str = "llama3.2") -> Optional[str]:
    """Call a local or cloud Ollama instance. Returns generated text or None on failure."""
    url = f"{base_url.rstrip('/')}/api/chat"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.9,
            "num_predict": 2048,
        },
    }

    print(f"🦙 Ollama request: model={model}, url={url}")

    try:
        resp = requests.post(url, json=payload, timeout=300)
        print(f"📡 Ollama response status: {resp.status_code}")

        if resp.status_code == 404:
            print(f"❌ Ollama model '{model}' not found. Try: ollama pull {model}")
            return None

        resp.raise_for_status()
        data = resp.json()

        message = data.get("message", {})
        content = message.get("content", "").strip()
        thinking = message.get("thinking", "").strip()

        # Log thinking field if present (reasoning models)
        if thinking:
            print(f"🧠 Ollama thinking field present ({len(thinking)} chars)")

        # Case 1: content is non-empty — normal response or post-thinking answer
        if content:
            return _strip_thinking_tags(content)

        # Case 2: content is empty but thinking has the answer (some reasoning models)
        if thinking:
            print(f"⚠️  Ollama content empty, extracting from thinking field...")
            # Strip <think> tags if embedded
            cleaned_thinking = _strip_thinking_tags(thinking)

            # Try to find JSON in the thinking output (AI content generation)
            import re as _re
            json_match = _re.search(r'\{[\s\S]*\}', cleaned_thinking)
            if json_match:
                print(f"✓ Found JSON in thinking field")
                return json_match.group(0)

            # Try to find the last substantial paragraph (hook generation)
            paragraphs = [p.strip() for p in cleaned_thinking.split('\n\n') if p.strip()]
            if paragraphs:
                # Return the last paragraph as the likely final answer
                result = paragraphs[-1]
                print(f"✓ Extracted answer from thinking field: {result[:100]}...")
                return result

        print(f"⚠️  Ollama returned no content: {resp.text[:200]}")
        return None

    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Ollama at {base_url} — is it running?")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"❌ Ollama API error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ Ollama request failed: {e}")
        return None


def _call_nvidia_nim(api_key: str, prompt: str, system_prompt: str, model: str = "meta/llama-3.1-405b-instruct") -> Optional[str]:
    """Call the Nvidia NIM API (OpenAI-compatible). Returns generated text or None on failure."""
    url = "https://integrate.api.nvidia.com/v1/chat/completions"

    clean_key = api_key.strip()
    if not clean_key:
        print("❌ Nvidia NIM API key is empty!")
        return None

    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.9,
        "max_tokens": 2048,
    }

    print(f"🟢 Nvidia NIM request: model={model}, key={clean_key[:8]}...{clean_key[-4:]}")

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        print(f"📡 Nvidia NIM response status: {resp.status_code}")

        if resp.status_code == 401:
            print(f"❌ Nvidia NIM 401 Unauthorized — API key is invalid or expired")
            return None

        if resp.status_code == 429:
            print(f"⚠️  Nvidia NIM 429 Rate Limited")
            return None

        resp.raise_for_status()
        data = resp.json()

        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if content:
                return _strip_thinking_tags(content.strip())

        print(f"⚠️  Nvidia NIM returned no choices: {resp.text[:200]}")
        return None

    except requests.exceptions.HTTPError as e:
        print(f"❌ Nvidia NIM API error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ Nvidia NIM request failed: {e}")
        return None


def _call_ai(provider: str, api_key: str, prompt: str, system_prompt: str, model: str, ollama_url: str = "") -> Optional[str]:
    """Route to the correct provider."""
    if provider == "openrouter":
        return _call_openrouter(api_key, prompt, system_prompt, model)
    elif provider == "ollama":
        base_url = ollama_url or DEFAULT_OLLAMA_URL
        return _call_ollama(base_url, prompt, system_prompt, model)
    elif provider == "nvidia_nim":
        return _call_nvidia_nim(api_key, prompt, system_prompt, model)
    else:
        return _call_gemini(api_key, prompt, system_prompt, model)


# ── Public API ───────────────────────────────────────────────────────

def generate_hook(provider: str, api_key: str, title: str, body: str, comments_text: str = "",
                  model: str = "gemini-2.0-flash", ollama_url: str = "") -> Optional[str]:
    """
    Generate an attention-grabbing spoken hook for the video intro.

    Returns:
        Hook text (1-2 sentences, ~3-4 seconds spoken) or None
    """
    story_context = f"Title: {title}\n\n"
    if body and body.strip():
        story_context += f"Story:\n{body[:2000]}\n\n"
    if comments_text and comments_text.strip():
        story_context += f"Top Comments:\n{comments_text[:1000]}\n"

    prompt = f"Write a 3-4 second spoken hook for this Reddit story:\n\n{story_context}"

    result = _call_ai(provider, api_key, prompt, HOOK_SYSTEM_PROMPT, model, ollama_url)
    if result:
        result = result.strip('"\'')
        print(f"✨ AI hook: \"{result}\"")
    return result


def generate_thumbnail_text(provider: str, api_key: str, title: str, body: str,
                            model: str = "gemini-2.0-flash", ollama_url: str = "") -> Optional[str]:
    """
    Generate eye-catching thumbnail overlay text.

    Returns:
        Short thumbnail text (3-6 words) or None
    """
    story_context = f"Title: {title}\n\n"
    if body and body.strip():
        story_context += f"Story:\n{body[:1500]}\n"

    prompt = f"Write short, bold thumbnail overlay text for this Reddit story:\n\n{story_context}"

    result = _call_ai(provider, api_key, prompt, THUMBNAIL_SYSTEM_PROMPT, model, ollama_url)
    if result:
        result = result.strip('"\'')
        print(f"✨ AI thumbnail text: \"{result}\"")
    return result


def generate_hooks(config: dict, title: str, body: str, comments_text: str = "") -> Tuple[Optional[str], Optional[str]]:
    """
    High-level function: generate both hook and thumbnail text if AI hooks are enabled.

    Returns:
        (hook_text, thumbnail_text) — either can be None if disabled or failed
    """
    gemini_cfg = config.get("gemini", {})

    if not gemini_cfg.get("enabled", False):
        return None, None

    provider = gemini_cfg.get("provider", "gemini")
    model = gemini_cfg.get("model", "gemini-2.0-flash")

    # Pick API key / URL based on provider
    ollama_url = gemini_cfg.get("ollama_url", DEFAULT_OLLAMA_URL)

    if provider == "ollama":
        api_key = ""  # Ollama doesn't need an API key
        if not model:
            model = "llama3.2"
    elif provider == "openrouter":
        api_key = gemini_cfg.get("openrouter_api_key", "")
        if not api_key:
            print("⚠️  OpenRouter enabled but no API key configured. Skipping.")
            return None, None
        if not model or model.startswith("gemini"):
            model = "google/gemini-2.0-flash-exp:free"
    elif provider == "nvidia_nim":
        api_key = gemini_cfg.get("nvidia_nim_api_key", "")
        if not api_key:
            print("⚠️  Nvidia NIM enabled but no API key configured. Skipping.")
            return None, None
        if not model:
            model = "meta/llama-3.1-405b-instruct"
    else:
        api_key = gemini_cfg.get("api_key", "")
        if not api_key:
            print("⚠️  Gemini enabled but no API key configured. Skipping.")
            return None, None

    hook_text = None
    thumbnail_text = None

    # Generate hook
    if gemini_cfg.get("generate_hook", True):
        print(f"🤖 Generating {provider} hook...")
        hook_text = generate_hook(provider, api_key, title, body, comments_text, model, ollama_url)

    # Generate thumbnail text
    if gemini_cfg.get("generate_thumbnail_text", True):
        print(f"🤖 Generating {provider} thumbnail text...")
        thumbnail_text = generate_thumbnail_text(provider, api_key, title, body, model, ollama_url)

    return hook_text, thumbnail_text
