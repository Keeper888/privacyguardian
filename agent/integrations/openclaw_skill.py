"""Guardian Agent as a portable skill — loadable by OpenClaw, callable
from a NeMo Guardrails rail, or wrappable into any agent runtime that
expects a tool with a JSON schema.

The skill is **stateless** at the call site: it talks to a running
Guardian learning server (default http://127.0.0.1:4180) so any number
of agents on the same machine share the same memory. Cross-runtime
intent: a codename you taught Guardian once via Claude Code is shielded
the next time an OpenClaw agent on the same box mentions it.

Drop this file into your skills directory:

    openclaw/
      skills/
        guardian_shield.py    <-- this file

then load with `from skills.guardian_shield import SKILL` and register
SKILL with your runtime. NeMo Guardrails users can wrap `shield()` as a
custom action and call it from input/output rails.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import httpx


GUARDIAN_URL = os.environ.get("GUARDIAN_URL", "http://127.0.0.1:4180")


SKILL_MANIFEST: Dict[str, Any] = {
    "name": "guardian_shield",
    "version": "0.1.0",
    "description": (
        "Privacy shield for outbound LLM calls. Replaces sensitive spans "
        "with reversible tokens before the LLM sees them, restores them "
        "in the reply. Memory is shared across every agent runtime on "
        "the same machine via MongoDB Atlas Vector Search."
    ),
    "inputs": {
        "text": {
            "type": "string",
            "description": "Raw text the agent is about to send to an LLM.",
        }
    },
    "outputs": {
        "redacted": {"type": "string", "description": "Text safe to forward to the LLM."},
        "tokens": {"type": "object", "description": "Map of placeholder -> real value, for local detokenize."},
        "regex_matches": {"type": "array"},
        "semantic_matches": {"type": "array"},
    },
    "tags": ["privacy", "redaction", "memory", "vector-search", "tinyml"],
    "runtime_compatibility": ["openclaw", "nemo-guardrails", "langgraph", "langchain", "raw-python"],
}


def shield(text: str, *, base_url: str = GUARDIAN_URL, timeout: float = 10.0) -> Dict[str, Any]:
    """Outbound side: scan + tokenize before sending to an LLM.

    Returns the redacted text, the token map (for local detokenize on the
    return path), and the matches that fired (for logging/audit)."""
    with httpx.Client(timeout=timeout) as client:
        scan = client.post(f"{base_url}/scan", json={"text": text}).json()
    return {
        "redacted": scan["redacted"],
        "regex_matches": scan["regex_matches"],
        "semantic_matches": scan["semantic_matches"],
    }


def remember(label: str, example: str, *, context: str = "", reason: str = "",
             base_url: str = GUARDIAN_URL, timeout: float = 10.0) -> Dict[str, Any]:
    """Teach the shield a new sensitivity rule. Embeds + stores in
    Atlas Vector Search; every subsequent shield() call across every
    runtime catches semantic variants of this example."""
    with httpx.Client(timeout=timeout) as client:
        return client.post(
            f"{base_url}/correct",
            json={"label": label, "example": example, "context": context, "reason": reason},
        ).json()


def suggest(text: str, *, base_url: str = GUARDIAN_URL, timeout: float = 10.0) -> List[Dict[str, Any]]:
    """Local TinyML pass — flags candidates the regex+memory missed.
    Useful as a NeMo Guardrails *output* rail to alert the user before
    committing a leak."""
    with httpx.Client(timeout=timeout) as client:
        return client.post(f"{base_url}/suggest", json={"text": text}).json()["suggestions"]


SKILL = {
    "manifest": SKILL_MANIFEST,
    "shield": shield,
    "remember": remember,
    "suggest": suggest,
}


if __name__ == "__main__":
    import json, sys
    sample = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "Hi I am alex@example.com working on Project Halcyon"
    )
    print(json.dumps(shield(sample), indent=2))
