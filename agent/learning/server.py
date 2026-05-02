import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "code"))

from agent.memory.vector_store import VectorStore, Match
from agent.learning.suggester import Suggester
from pii_detector import PIIDetector


class CorrectionRequest(BaseModel):
    label: str
    example: str
    context: str = ""
    reason: str = ""


class ScanRequest(BaseModel):
    text: str


class SuggestRequest(BaseModel):
    text: str
    labels: list[str] = []


class ScanResponse(BaseModel):
    regex_matches: list[dict]
    semantic_matches: list[dict]
    redacted: str


app = FastAPI(title="Guardian Agent — Learning Server")
store = VectorStore()
detector = PIIDetector()
suggester = Suggester()

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(UI_DIR / "index.html")


@app.post("/correct")
def correct(req: CorrectionRequest):
    rule_id = store.remember(req.label, req.context, req.example, req.reason)
    return {"ok": True, "id": rule_id, "total_rules": store.count()}


@app.post("/scan", response_model=ScanResponse)
def scan(req: ScanRequest) -> ScanResponse:
    regex_hits = detector.detect(req.text)
    semantic_hits: list[Match] = store.search(req.text)

    redacted = req.text
    for hit in regex_hits:
        redacted = redacted.replace(hit.value, f"<{hit.pii_type.value}>")
    for hit in semantic_hits:
        if hit.example in redacted:
            redacted = redacted.replace(hit.example, f"<{hit.label}>")

    return ScanResponse(
        regex_matches=[
            {"type": h.pii_type.value, "value": h.value} for h in regex_hits
        ],
        semantic_matches=[
            {"label": h.label, "example": h.example, "score": round(h.score, 3)}
            for h in semantic_hits
        ],
        redacted=redacted,
    )


@app.post("/suggest")
def suggest(req: SuggestRequest):
    regex_hits = detector.detect(req.text)
    semantic_hits = store.search(req.text)

    skip = {h.value for h in regex_hits}
    skip |= store.list_examples()
    for hit in semantic_hits:
        for word in hit.example.split():
            if len(word) >= 3:
                skip.add(word)

    suggestions = suggester.suggest(
        req.text,
        labels=req.labels or None,
        skip_spans=skip,
    )
    return {
        "suggestions": [
            {
                "label": s.label,
                "text": s.text,
                "score": round(s.score, 3),
                "start": s.start,
                "end": s.end,
            }
            for s in suggestions
        ]
    }


@app.get("/stats")
def stats():
    return {"learned_rules": store.count()}


def main():
    import uvicorn

    port = int(os.environ.get("LEARNING_SERVER_PORT", "4180"))
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
