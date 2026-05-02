"""TinyML agent beat — local zero-shot NER that flags potentially sensitive
spans the regex layer would miss. Runs entirely on-device (gliner_small-v2.1,
~165MB). No external API call. Privacy by construction."""

import os
from dataclasses import dataclass
from typing import List, Optional, Set

from gliner import GLiNER


DEFAULT_LABELS = [
    "internal project codename",
    "company name",
    "client name",
    "product name",
    "person name",
    "secret",
]


@dataclass
class Suggestion:
    label: str
    text: str
    score: float
    start: int
    end: int


class Suggester:
    def __init__(self, model_name: Optional[str] = None, threshold: float = 0.4):
        name = model_name or os.environ.get(
            "SUGGESTER_MODEL", "urchade/gliner_small-v2.1"
        )
        self.threshold = float(os.environ.get("SUGGESTER_THRESHOLD", threshold))
        self.model = GLiNER.from_pretrained(name)

    def suggest(
        self,
        text: str,
        labels: Optional[List[str]] = None,
        skip_spans: Optional[Set[str]] = None,
    ) -> List[Suggestion]:
        used_labels = labels or DEFAULT_LABELS
        skip = {s.lower() for s in (skip_spans or set())}

        ents = self.model.predict_entities(
            text, used_labels, threshold=self.threshold
        )

        seen: Set[str] = set()
        results: List[Suggestion] = []
        for e in ents:
            span = e["text"].strip()
            if not span or span.lower() in skip:
                continue
            key = (span.lower(), e["label"])
            if key in seen:
                continue
            seen.add(key)
            results.append(
                Suggestion(
                    label=e["label"],
                    text=span,
                    score=float(e["score"]),
                    start=int(e["start"]),
                    end=int(e["end"]),
                )
            )

        results.sort(key=lambda s: s.score, reverse=True)
        return results
