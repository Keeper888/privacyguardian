"""NemoClaw demo runner — Guardian as a skill, MiniMax as the LLM,
the full input/output rail pattern in ~30 lines.

What this proves: any agent runtime that can import a Python module
gets PII shielding for free. No HTTP server is needed at the call
site (we use Guardian's components as a library here); the same
SKILL["shield"] / SKILL["remember"] surface works across runtimes.

Run:
    python -m agent.integrations.nemoclaw_demo
    python -m agent.integrations.nemoclaw_demo "Quick update on Project Halcyon"

Requires agent/.env with MONGODB_URI and MINIMAX_API_KEY set.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "code"))

from agent.memory.vector_store import VectorStore
from agent.llm import minimax
from agent.llm.tokenizer import tokenize, detokenize
from pii_detector import PIIDetector


SYSTEM_PROMPT = (
    "You are a helpful assistant. The user's message may contain placeholder "
    "tokens like <EMAIL>, <INTERNAL_CODENAME>, <STRIPE_KEY>. These are "
    "redactions of private values that you must NEVER receive in plain. "
    "Treat each token as an opaque reference and reuse the EXACT same "
    "token (verbatim, including angle brackets) when referring to it. "
    "Reply in under 4 short sentences."
)


def turn(user_text: str, store: VectorStore, detector: PIIDetector) -> Dict[str, Any]:
    regex_hits = detector.detect(user_text)
    semantic_hits = store.search(user_text)
    redacted, token_map = tokenize(user_text, regex_hits, semantic_hits)

    reply_with_tokens = minimax.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": redacted},
        ]
    )
    reply_real = detokenize(reply_with_tokens, token_map)

    return {
        "user": user_text,
        "what_llm_saw": redacted,
        "what_llm_replied": reply_with_tokens,
        "what_user_sees": reply_real,
        "tokens": list(token_map.keys()),
    }


def main() -> int:
    text = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "Hi I am alex@example.com working on Project Halcyon for our launch."
    )
    store = VectorStore()
    detector = PIIDetector()

    result = turn(text, store, detector)

    BOLD, DIM, CYAN, GREEN, YELLOW, RESET = (
        "\033[1m", "\033[2m", "\033[96m", "\033[92m", "\033[93m", "\033[0m",
    )

    print()
    print(f"{BOLD}NemoClaw runner — Guardian skill + MiniMax{RESET}")
    print(f"{DIM}{'─' * 70}{RESET}")
    print(f"{BOLD}1 · USER (real){RESET}")
    print(f"  {result['user']}")
    print(f"{DIM}        ↓ guardian shield (regex + Atlas memory){RESET}")
    print(f"{BOLD}2 · WHAT MINIMAX RECEIVES{RESET}")
    print(f"  {YELLOW}{result['what_llm_saw']}{RESET}")
    print(f"{DIM}        ↓ MiniMax-M2{RESET}")
    print(f"{BOLD}3 · WHAT MINIMAX REPLIES (still tokenized){RESET}")
    print(f"  {YELLOW}{result['what_llm_replied']}{RESET}")
    print(f"{DIM}        ↓ guardian detokenize (tokens={result['tokens'] or '∅'}){RESET}")
    print(f"{BOLD}4 · WHAT THE USER SEES{RESET}")
    print(f"  {GREEN}{result['what_user_sees']}{RESET}")
    print()
    print(f"{DIM}MiniMax never received: {[v for v in [m.value for m in detector.detect(text)] + [h.example for h in store.search(text)]] or 'nothing sensitive'}{RESET}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
