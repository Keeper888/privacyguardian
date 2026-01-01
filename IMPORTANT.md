# IMPORTANT: PrivacyGuardian Setup Guide

## Quick Setup (One-Time)

Add this alias to your `~/.bashrc`:

```bash
# PrivacyGuardian protection
alias claude='/path/to/privacyguardian/pg-wrapper claude'
```

Then reload: `source ~/.bashrc`

---

## How to Use

### Option 1: GUI (Recommended)

```bash
./guardian gui
```

Use the master toggle switch at the top to enable/disable protection.

### Option 2: CLI

```bash
./guardian enable    # Turn ON protection
./guardian disable   # Turn OFF protection
./guardian toggle    # Flip current state
./guardian status    # Check status
```

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  You type: claude                                           │
│       ↓                                                     │
│  Alias runs: pg-wrapper claude                              │
│       ↓                                                     │
│  Wrapper checks: ~/.privacyguardian/enabled exists?         │
│       ↓                                                     │
│  YES → Route through proxy (PII filtered)                   │
│  NO  → Connect direct (no protection)                       │
└─────────────────────────────────────────────────────────────┘
```

The flag file (`~/.privacyguardian/enabled`) is the single source of truth:
- **Exists** = Protection ON
- **Missing** = Protection OFF

---

## DO NOT (Warning from 2025-12-31)

**NEVER** add global environment variables like:

```bash
# BAD - DO NOT DO THIS
export ANTHROPIC_BASE_URL=http://localhost:6660
```

This breaks Claude Code when the proxy isn't running.

The wrapper approach is **safe** because:
1. It checks if protection is enabled (flag file)
2. It checks if proxy is running (health check)
3. If proxy is dead, it asks you what to do instead of failing

---

## Supported Apps

The wrapper supports multiple LLM apps:

| App | Alias |
|-----|-------|
| Claude | `alias claude='pg-wrapper claude'` |
| ChatGPT | `alias chatgpt='pg-wrapper chatgpt'` |
| OpenAI | `alias openai='pg-wrapper openai'` |
| Gemini | `alias gemini='pg-wrapper gemini'` |
| Mistral | `alias mistral='pg-wrapper mistral'` |

---

## Troubleshooting

### Protection enabled but proxy not running

The wrapper will prompt you:
- **[S]** Start proxy and continue
- **[D]** Go direct this time (unprotected)
- **[C]** Cancel

### Check current status

```bash
./guardian status
ls ~/.privacyguardian/enabled  # exists = ON
```
