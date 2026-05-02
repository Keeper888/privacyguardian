"""Reversible tokenization for the LLM round-trip.

Outgoing: replace each detected sensitive span with a labeled placeholder
(<EMAIL>, <INTERNAL_CODENAME>, …) so the LLM never sees the real value.
Incoming: scan the LLM reply for those same placeholders and substitute
back the real value so the user sees their actual data."""

from typing import Dict, List, Tuple


def tokenize(
    text: str,
    regex_hits: list,
    semantic_hits: list,
) -> Tuple[str, Dict[str, str]]:
    out = text
    token_map: Dict[str, str] = {}

    spans: List[Tuple[str, str]] = []
    for h in regex_hits:
        spans.append((h.value, h.pii_type.value))

    for h in semantic_hits:
        phrase = h.example
        if phrase and phrase in out:
            spans.append((phrase, h.label))
        else:
            for word in phrase.split():
                if len(word) >= 3 and word in out:
                    spans.append((word, h.label))

    spans.sort(key=lambda s: len(s[0]), reverse=True)

    seen_tokens: Dict[str, str] = {}
    for value, label in spans:
        if not value or value not in out:
            continue
        token = f"<{label}>"
        if token in seen_tokens and seen_tokens[token] != value:
            i = 2
            while f"<{label}_{i}>" in seen_tokens:
                i += 1
            token = f"<{label}_{i}>"
        seen_tokens[token] = value
        out = out.replace(value, token)
        token_map[token] = value

    return out, token_map


def detokenize(text: str, token_map: Dict[str, str]) -> str:
    longest_first = sorted(token_map.items(), key=lambda kv: -len(kv[0]))
    for token, real in longest_first:
        text = text.replace(token, real)
    return text
