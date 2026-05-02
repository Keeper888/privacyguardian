# Guardian Agent

Built **2026-05-02** for **MongoDB.local London** hackathon, on top of the existing [PrivacyGuardian](../README.md) foundation.

## What's new in this layer

PrivacyGuardian (the base project, built Jan 2026) catches PII via static regex. Useful, but it can't know what's sensitive to *you*: internal codenames, customer names, project labels, the things only your context defines.

Guardian Agent adds:

- **Vector memory** in MongoDB Atlas — semantic record of what you've marked sensitive
- **Learning loop** — one correction becomes a rule that catches every variant
- **Cross-runtime intent** — same memory shields any agent (Claude Code, OpenClaw, …) talking on your behalf

## Run the demo

```bash
cd agent
cp .env.example .env  # fill in MONGODB_URI + OPENAI_API_KEY
pip install -r requirements.txt
cd ..
python -m agent.demo.run_demo
```

## Run the learning server

```bash
python -m agent.learning.server
# POST http://127.0.0.1:4180/correct  {"label","example","context","reason"}
# POST http://127.0.0.1:4180/scan     {"text"}
# GET  http://127.0.0.1:4180/stats
```

## Atlas vector index

Once-off setup on the `sensitivity_memory` collection:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    }
  ]
}
```

## Layout

```
agent/
├── memory/          MongoDB Atlas vector store + embeddings
├── learning/        FastAPI server for corrections + scans
└── demo/            Recordable 4-act demo
```
