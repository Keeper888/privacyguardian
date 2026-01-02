# GUI Apps (Electron) Cannot Use Environment Variable Approach

**Date:** 2026-01-02
**Status:** Blocked
**Related:** Issue #10

## The Problem

CLI tools like `claude` respect environment variables like `ANTHROPIC_BASE_URL`. We set this to our proxy (`http://localhost:6660`) and traffic flows through.

GUI apps like Antigravity, Cursor, Windsurf, Zed are different:
- They're Electron apps (Chromium-based)
- They make **direct HTTPS calls** to `https://api.anthropic.com`, `https://api.openai.com`, etc.
- They ignore `ANTHROPIC_BASE_URL` and similar env vars
- They ignore `HTTP_PROXY`/`HTTPS_PROXY` for API calls (those are for general web traffic)

## What We Tried

1. **API base URL env vars** (`ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`, `GOOGLE_AI_BASE_URL`)
   - Result: Ignored by Electron apps

2. **System proxy env vars** (`HTTP_PROXY`, `HTTPS_PROXY`)
   - Result: Would require our proxy to handle CONNECT tunneling + TLS termination

3. **Electron's `--proxy-server` flag**
   - Result: Same issue - HTTPS needs TLS termination

## Why It's Hard

```
Normal CLI flow:
  claude → reads ANTHROPIC_BASE_URL → http://localhost:6660 → proxy → api.anthropic.com

GUI app flow:
  Antigravity → direct HTTPS → api.anthropic.com (bypasses everything)
```

To intercept HTTPS, we need Man-in-the-Middle (MITM):
1. Generate a local CA certificate
2. Install CA in system trust store (requires root)
3. Proxy terminates TLS, inspects/modifies, re-encrypts
4. Use iptables to redirect traffic (requires root)

This is the "transparent proxy" approach we rejected in `0002-transparent-proxy-rejected.md`.

## Possible Solutions

### Option A: App-Specific Settings
Some AI IDEs have settings for custom API endpoints. If Antigravity/Cursor has this:
- User configures `http://localhost:6660` as the API base
- No MITM needed

**Status:** Need to investigate each app's settings

### Option B: Lightweight MITM (User Opt-in)
A "stealth mode" that:
1. Generates local CA
2. User manually installs CA (guided setup)
3. Uses `--proxy-server` with our HTTPS-capable proxy
4. Only intercepts known LLM API domains

**Pros:** Works with any app
**Cons:** Requires user to trust our CA, more complex

### Option C: Browser Extension
For web-based LLM interfaces (ChatGPT web, Claude web):
- Browser extension intercepts requests
- Modifies request body before sending
- No MITM needed

**Status:** Different problem, doesn't help desktop apps

## Current State

- `gui-launcher` created but **does not work** for HTTPS API calls
- Launchers exist in `~/.local/bin/` but are ineffective
- CLI tools (`claude`, etc.) work fine

## Next Steps

1. Research if Antigravity/Cursor have custom API endpoint settings
2. If not, consider implementing Option B with clear user consent
3. Document which apps are supported vs not supported
