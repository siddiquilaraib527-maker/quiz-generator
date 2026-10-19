"""
Common Ollama/Gemma Client Utility
Shared across all 90 projects for consistent LLM interaction.

Speed notes:
- keep_alive keeps the model loaded in memory, so only the first call is slow.
- num_ctx is limited so the model does not allocate a huge context window.
- json_mode makes the model output only JSON (less extra text, faster, easier to parse).
"""

import requests
import json
import sys
from typing import Optional, Generator


OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma3:4b"

# Keep the model in memory between requests (avoids reloading every time).
KEEP_ALIVE = "30m"

# Smaller context = faster. Raise it only if your prompts get cut off.
NUM_CTX = 4096


def check_ollama_running() -> bool:
    """Check if Ollama server is running."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except requests.ConnectionError:
        return False


def list_models() -> list:
    """List available Ollama models."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _options(temperature: float, max_tokens: int, num_ctx: int) -> dict:
    return {
        "temperature": temperature,
        "num_predict": max_tokens,
        "num_ctx": num_ctx,
    }


def chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    num_ctx: int = NUM_CTX,
    json_mode: bool = False,
) -> str:
    """
    Send a chat request to Ollama and return the full response.

    Args:
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts
        model: Model name
        system_prompt: Optional system prompt
        temperature: Creativity (0.0-1.0)
        max_tokens: Max response tokens (lower = faster)
        num_ctx: Context window size (lower = faster)
        json_mode: Force the model to reply with valid JSON only

    Returns:
        The assistant's response text
    """
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": _options(temperature, max_tokens, num_ctx),
    }
    if json_mode:
        payload["format"] = "json"

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except requests.exceptions.ConnectionError:
        print("Error: Ollama is not running. Start it with: ollama serve")
        sys.exit(1)
    except Exception as e:
        print(f"Error communicating with Ollama: {e}")
        sys.exit(1)


def chat_stream(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    num_ctx: int = NUM_CTX,
) -> Generator[str, None, None]:
    """
    Stream a chat response from Ollama token by token.

    Yields:
        Individual tokens as they arrive
    """
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "keep_alive": KEEP_ALIVE,
        "options": _options(temperature, max_tokens, num_ctx),
    }

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            stream=True,
            timeout=300,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                data = json.loads(line)
                token = data.get("message", {}).get("content", "")
                if token:
                    yield token
                if data.get("done", False):
                    break
    except requests.exceptions.ConnectionError:
        print("Error: Ollama is not running. Start it with: ollama serve")
        sys.exit(1)


def generate(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    num_ctx: int = NUM_CTX,
    json_mode: bool = False,
) -> str:
    """
    Simple single-turn generation (non-chat API).

    Args:
        prompt: The input prompt
        model: Model name
        system_prompt: Optional system instruction
        temperature: Creativity level
        max_tokens: Max response tokens (lower = faster)
        num_ctx: Context window size (lower = faster)
        json_mode: Force the model to reply with valid JSON only

    Returns:
        Generated text
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": _options(temperature, max_tokens, num_ctx),
    }
    if system_prompt:
        payload["system"] = system_prompt
    if json_mode:
        payload["format"] = "json"

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()["response"]
    except requests.exceptions.ConnectionError:
        print("Error: Ollama is not running. Start it with: ollama serve")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def embed(text: str, model: str = DEFAULT_MODEL) -> list[float]:
    """
    Get embeddings for text using Ollama.

    Tip: for speed, pass a small dedicated embedding model such as
    "nomic-embed-text" instead of the chat model.

    Args:
        text: Input text to embed
        model: Model name

    Returns:
        List of floats (embedding vector)
    """
    payload = {"model": model, "input": text, "keep_alive": KEEP_ALIVE}
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]
    except Exception as e:
        print(f"Error getting embeddings: {e}")
        return []