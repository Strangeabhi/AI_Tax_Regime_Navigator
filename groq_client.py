"""
Groq API client for the AI Tax Regime Navigator.
Uses a single AI model for explanations, regime guidance, and RAG-backed answers.
"""

import os
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
DEFAULT_MODEL = "llama-3.3-70b-versatile"


def get_client() -> Groq:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set. Add it to .env or environment.")
    return Groq(api_key=GROQ_API_KEY)


def chat(messages: list[dict], model: str = DEFAULT_MODEL) -> str:
    """Send messages to Groq and return assistant reply text."""
    client = get_client()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=2048,
    )
    if not resp.choices:
        return ""
    return (resp.choices[0].message.content or "").strip()


def is_configured() -> bool:
    return bool(GROQ_API_KEY)
