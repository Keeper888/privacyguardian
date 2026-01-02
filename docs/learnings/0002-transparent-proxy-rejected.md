# Transparent Proxy Approach: Tried and Rejected

**Date:** 2026-01-02
**Status:** Rejected
**Related:** ADR-0001

## What We Tried

A "transparent" HTTPS proxy using iptables to intercept ALL traffic to LLM APIs at the network level. No app configuration needed.

**Components built:**
- `CertificateAuthority` - Local CA to generate fake TLS certs for MITM
- `IPTablesManager` - Redirect traffic at firewall level

## Why It Seemed Good

- Zero configuration for users
- Works with any app automatically
- "Just works" magic

## Problems Encountered

1. **Requires root privileges** - iptables needs sudo
2. **Complex setup** - CA cert must be installed system-wide
3. **Risk of breaking system** - misconfigured iptables can kill network
4. **Hard to enable/disable** - can't just flip a switch
5. **Privacy concerns** - intercepts ALL traffic, not just LLM apps
6. **Debugging nightmare** - when it breaks, good luck

## What We Did Instead

Wrapper-based approach (`pg-wrapper`):
- Shell alias redirects `claude` command through wrapper
- Wrapper checks if protection is enabled (flag file)
- Wrapper checks if proxy is healthy
- Explicit user intent, no magic

## Lesson Learned

"Just works" magic often means "just breaks mysteriously". Explicit is better than implicit. A simple alias that users understand beats invisible network interception.

## Code Removed

`transparent_proxy.py` deleted after this decision. The code lived from initial development until 2026-01-02.
