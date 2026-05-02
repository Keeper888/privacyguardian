# Integrations — drop Guardian into any agent runtime

Guardian Agent runs as a local service (port 4180). Any agent runtime on the same machine can call it as a skill / tool / rail.

The shared memory is the point: a sensitivity rule you teach once in Claude Code applies *immediately* to OpenClaw, NeMo Guardrails, or a LangGraph node — same MongoDB Atlas Vector Search collection, same shield.

## OpenClaw skill

Drop [`openclaw_skill.py`](./openclaw_skill.py) into your OpenClaw `skills/` directory.

```python
from skills.guardian_shield import SKILL

# outbound
out = SKILL["shield"](user_text)
llm_input = out["redacted"]
token_map = ...  # build from out["regex_matches"] + out["semantic_matches"] if you want round-trip

# teach
SKILL["remember"](label="INTERNAL_CODENAME", example="Project Halcyon")
```

## NeMo Guardrails

Wrap `shield()` as a custom action and call it from an **input rail**:

```yaml
rails:
  input:
    flows:
      - guardian shield
```

```python
@action()
async def guardian_shield(context):
    out = SKILL["shield"](context["user_message"])
    return out["redacted"]
```

Wrap `suggest()` as an **output rail** if you want the runtime to surface "you almost leaked X" warnings before the LLM call commits.

## LangGraph / LangChain

```python
from langchain.tools import Tool
from skills.guardian_shield import shield, remember, suggest

guardian_tool = Tool(
    name="guardian_shield",
    description="Redact PII and learned sensitivities before an LLM call.",
    func=lambda text: shield(text)["redacted"],
)
```

## Why it ships as a skill

The hackathon brief asks for *agents that learn, adapt, and grow alongside us*. Privacy is the test of trust. A shield that lives outside any single runtime, learns from corrections you make in any of them, and applies that knowledge to all of them — that's a skill, not an app.
