# ADR-0001: Wrapper-Based Protection over System-Wide Proxy

**Date:** 2024-12-29
**Status:** Accepted

## Context

PrivacyGuardian needs to intercept and tokenize sensitive data (emails, phone numbers, etc.) before it reaches LLM services. There are several ways to achieve this:

1. System-wide proxy configuration
2. Application-specific wrappers
3. Browser extensions
4. Network-level interception (iptables)

We needed an approach that is:
- Reliable and predictable
- Easy to enable/disable
- Doesn't break other applications
- Works across different LLM tools (CLI apps, IDEs, etc.)

## Decision

Use a wrapper-based approach where:
- `pg-wrapper` is a script that wraps LLM applications
- Shell aliases redirect commands (like `claude`) through the wrapper
- A flag file (`~/.privacyguardian/enabled`) controls whether protection is active
- The wrapper checks proxy health before redirecting traffic

## Consequences

### Positive

- Explicit user intent: protection only applies where aliases are configured
- No system-wide side effects: other applications work normally
- Easy to bypass: use the full path to skip the wrapper
- Portable: works on any Linux system with bash
- No root required for basic operation

### Negative

- Requires per-application configuration
- Users must source their shell rc file after setup
- Won't protect applications not configured with aliases

### Neutral

- Aliases are shell-specific (bash, zsh, fish each need different setup)
- Users can see exactly which apps are protected

## Alternatives Considered

### Alternative 1: System-wide HTTP_PROXY

Setting `HTTP_PROXY` and `HTTPS_PROXY` environment variables globally.

Rejected because:
- Affects all applications, not just LLM tools
- Can break applications that don't handle proxies well
- Harder to debug when things go wrong
- Privacy concerns: all traffic would route through our proxy

### Alternative 2: iptables/nftables Redirection

Using firewall rules to redirect traffic to specific domains.

Rejected because:
- Requires root privileges
- Complex to set up and maintain
- Risk of breaking system if misconfigured
- Difficult to enable/disable dynamically

### Alternative 3: Browser Extension Only

Building a browser extension for web-based LLM interfaces.

Rejected because:
- Doesn't cover CLI tools (main use case)
- Different extension needed per browser
- Can't protect IDE integrations

## Implementation Notes

- `pg-wrapper` checks for enabled flag before proxying
- Setup wizard detects user's shell and installs appropriate aliases
- GUI toggle writes/removes the enabled flag file
- Wrapper validates proxy health before redirecting

## References

- `pg-wrapper` script in project root
- `guardian` CLI tool for setup/management
- GUI toggle in `code/gui/`
