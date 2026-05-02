"""Minimal MiniMax chat completions wrapper. Only used for AI replies in
the chat surface — Guardian's own detection runs entirely on-device."""

import os
from typing import List, Dict

import httpx


ENDPOINT = "https://api.minimax.io/v1/text/chatcompletion_v2"
DEFAULT_MODEL = "MiniMax-M2"


class MiniMaxError(RuntimeError):
    pass


def chat(messages: List[Dict[str, str]], model: str = DEFAULT_MODEL, timeout: float = 30.0) -> str:
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        raise MiniMaxError("MINIMAX_API_KEY not set in agent/.env")

    with httpx.Client(timeout=timeout) as client:
        r = client.post(
            ENDPOINT,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={"model": model, "messages": messages},
        )
    r.raise_for_status()
    j = r.json()
    base = j.get("base_resp", {})
    if base.get("status_code") not in (0, None):
        raise MiniMaxError(f"MiniMax: {base.get('status_msg', 'unknown error')}")
    choices = j.get("choices") or []
    if not choices:
        raise MiniMaxError("MiniMax returned no choices")
    return choices[0]["message"]["content"]
