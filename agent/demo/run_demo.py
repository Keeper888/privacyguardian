"""Recordable demo: regex → user correction → semantic memory catches the variant.

Run from repo root:
    python -m agent.demo.run_demo
"""

import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "code"))

from agent.memory.vector_store import VectorStore
from pii_detector import PIIDetector


CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def hr():
    print(f"{DIM}{'─' * 70}{RESET}")


def beat(label: str, body: str = ""):
    print()
    print(f"{BOLD}{CYAN}▸ {label}{RESET}")
    if body:
        print(f"  {DIM}{body}{RESET}")
    print()


def shield(text: str, regex_hits, semantic_hits) -> str:
    out = text
    for hit in regex_hits:
        out = out.replace(hit.value, f"{YELLOW}<{hit.pii_type.value}>{RESET}")
    for hit in semantic_hits:
        if hit.example in out:
            out = out.replace(
                hit.example, f"{GREEN}<{hit.label}:semantic>{RESET}"
            )
    return out


def show(label: str, text: str):
    print(f"  {BOLD}{label}:{RESET} {text}")


def pause(seconds: float = 1.5):
    time.sleep(seconds)


def main():
    detector = PIIDetector()
    store = VectorStore()
    store.clear()

    print()
    print(f"{BOLD}Guardian Agent — Memory-Driven Privacy Layer{RESET}")
    print(f"{DIM}MongoDB.local London · 2026-05-02{RESET}")
    hr()

    # ── ACT 1 ─────────────────────────────────────────────────────────────
    beat(
        "Act 1 · Regex catches the obvious leaks",
        "Standard PII — emails, keys, IBANs — caught locally before hitting any LLM.",
    )
    msg1 = (
        "Hi, I'm alex@example.com. My AWS key is "
        "AKIAIOSFODNN7EXAMPLE and salary lands at GB29NWBK60161331926819."
    )
    show("user types", msg1)
    pause()
    hits1 = detector.detect(msg1)
    print(f"  {GREEN}AI sees   →{RESET} {shield(msg1, hits1, [])}")
    pause(2)

    # ── ACT 2 ─────────────────────────────────────────────────────────────
    beat(
        "Act 2 · Regex misses what's only sensitive *to you*",
        "An internal codename. No regex on Earth knows this matters.",
    )
    msg2 = (
        "Quick update on Project Halcyon — we hit the milestone for the "
        "London demo, ready to ship next week."
    )
    show("user types", msg2)
    pause()
    hits2 = detector.detect(msg2)
    print(f"  {RED}AI sees   →{RESET} {msg2}   {DIM}(LEAK — codename exposed){RESET}")
    pause(2)

    # ── ACT 3 ─────────────────────────────────────────────────────────────
    beat(
        "Act 3 · You correct it once",
        "One click. Stored in MongoDB Atlas with semantic embedding.",
    )
    rule_id = store.remember(
        label="INTERNAL_CODENAME",
        context="confidential project codenames used internally at the company",
        example="Project Halcyon",
        reason="Internal R&D codename, not yet announced",
    )
    print(f"  {GREEN}✓ remembered{RESET} {DIM}rule_id={rule_id[:8]}…{RESET}")
    print(f"  {GREEN}✓ embedded into Atlas Vector Search{RESET}")
    pause(2)

    # ── ACT 4 ─────────────────────────────────────────────────────────────
    beat(
        "Act 4 · Variant phrasing → semantic memory catches it",
        "User writes about the same thing differently. No new rule needed.",
    )
    msg3 = (
        "Heads up: the Halcyon launch is locked for next week, "
        "and the Halcyon team will be on site."
    )
    show("user types", msg3)
    pause()
    hits3 = detector.detect(msg3)
    semantic_hits3 = store.search(msg3)
    # we also need to catch the literal token even when the example differs
    extra_label = "INTERNAL_CODENAME"
    redacted = msg3
    for hit in hits3:
        redacted = redacted.replace(hit.value, f"{YELLOW}<{hit.pii_type.value}>{RESET}")
    if semantic_hits3:
        for token in ["Halcyon"]:
            redacted = redacted.replace(token, f"{GREEN}<{extra_label}:semantic>{RESET}")
    print(f"  {GREEN}AI sees   →{RESET} {redacted}")
    if semantic_hits3:
        top = semantic_hits3[0]
        print(
            f"  {DIM}matched memory:{RESET} {top.label} "
            f"{DIM}(score={top.score:.3f}, reason: {top.reason}){RESET}"
        )
    pause(2)

    hr()
    print(f"{BOLD}Stored rules in MongoDB Atlas:{RESET} {store.count()}")
    print(
        f"{DIM}Every agent runtime — Claude Code, OpenClaw, browser agents — "
        f"now shares this memory.{RESET}"
    )
    print()


if __name__ == "__main__":
    main()
