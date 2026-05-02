# Submission — paste-ready

> Use whichever block matches the form field. All written in first person singular since this is a solo entry.

---

## Project name

**Guardian Agent**

## One-line tagline (≤ 120 chars)

A memory-driven privacy layer that learns what's sensitive to *you* and shields it across every agent runtime.

## Short description (1–2 sentences)

Regex catches universal PII; it has no idea that "Project Halcyon" is your unannounced launch or that "Devotion" is your client's name. Guardian Agent adds an on-device TinyML detector, MongoDB Atlas Vector Search as semantic memory, and a learning loop that turns one user correction into a rule that catches every variant — across Claude Code, OpenClaw, NeMo Guardrails, or any runtime via a portable skill.

## Long description (paragraphs)

Every AI agent acting on your behalf is a data leak waiting to happen. Regex catches what's *universally* sensitive — emails, IBANs, API keys. But regex doesn't know what's sensitive *to you*: internal codenames, customer names, secret projects, that one phrase you'd be embarrassed to leak.

Guardian Agent makes the privacy layer learn. Today's hackathon work, all on the [`hackathon-mongodb-london` branch](https://github.com/Keeper888/privacyguardian/tree/hackathon-mongodb-london):

- **A local TinyML brain** — GLiNER (~165MB, zero-shot NER) runs entirely on-device and proactively flags candidates the regex misses. *No external API ever sees your text* — on-brand for a privacy product.
- **MongoDB Atlas Vector Search as semantic memory** — when you accept a suggestion, the agent embeds it and stores it. Every future paraphrase, lowercase variant, or rephrasing gets caught semantically. (Free M0 vector index, 384-dim, cosine.)
- **The full LLM round-trip** — text is tokenized before it leaves the machine; MiniMax only ever sees `<EMAIL>` and `<INTERNAL_CODENAME>`. The reply comes back with the same tokens; we detokenize locally so the user sees their real names. The "AI sees tokens" claim is *demonstrated*, not annotated.
- **Ships as a portable skill** — `agent/integrations/openclaw_skill.py` is loadable by OpenClaw, NeMo Guardrails, LangGraph, or any runtime that calls Python tools. Shared memory: a rule taught in Claude Code shields an OpenClaw agent on the same machine instantly.

The base project, [PrivacyGuardian](https://github.com/Keeper888/privacyguardian) (regex shield, Jan 2026), stays open-source on `main`. Today's contribution is the agent layer: memory, self-improvement, integrations.

## Tech / stack

- MongoDB Atlas Vector Search (semantic memory backbone)
- GLiNER (`urchade/gliner_small-v2.1`) — local zero-shot NER
- sentence-transformers (`all-MiniLM-L6-v2`) — local embeddings
- FastAPI + uvicorn — learning server on :4180
- MiniMax-M2 — LLM round-trip
- httpx, pymongo, vanilla HTML/CSS/JS

## Demo path (for judges)

1. `git clone -b hackathon-mongodb-london https://github.com/Keeper888/privacyguardian.git`
2. `cd privacyguardian && pip install -r agent/requirements.txt`
3. Fill `agent/.env` from `agent/.env.example` (MongoDB URI + MiniMax key)
4. `python -m agent.memory.setup_index` (one-shot Atlas vector index)
5. `python -m agent.learning.server` → open **http://127.0.0.1:4180**
6. Try: *"It's an AI orchestrator running on a system called Devotion"* → click **Yes** on the suggestion → next message containing *Devotion* gets shielded automatically.

Or run the scripted CLI demo: `python -m agent.demo.run_demo`.

## What was built today vs what existed

| Component                           | When     | Location                              |
|-------------------------------------|----------|---------------------------------------|
| Regex PII detector (35+ types)      | Jan 2026 | `code/pii_detector.py`                |
| Transparent LLM proxy               | Jan 2026 | `code/guardian_proxy.py`              |
| **TinyML suggester (GLiNER)**       | **May 2** | `agent/learning/suggester.py`         |
| **MongoDB Atlas vector memory**     | **May 2** | `agent/memory/vector_store.py`        |
| **Reversible tokenizer + MiniMax**  | **May 2** | `agent/llm/`                          |
| **Chat UI with Y/N learning**       | **May 2** | `agent/ui/`                           |
| **Portable skill (OpenClaw / NeMo)**| **May 2** | `agent/integrations/openclaw_skill.py`|
| **4-act CLI demo**                  | **May 2** | `agent/demo/run_demo.py`              |

`git log --since=2026-05-02 --oneline` on the branch shows every commit, all today.

## Repo

🔗 **https://github.com/Keeper888/privacyguardian/tree/hackathon-mongodb-london**

## Team

Solo entry — Antonio Gison ([@AntonioGison](https://github.com/AntonioGison) / [@Keeper888](https://github.com/Keeper888)).
