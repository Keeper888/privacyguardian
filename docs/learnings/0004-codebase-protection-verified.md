# Codebase Protection Verified

## Context

Tested whether PrivacyGuardian protects the entire codebase when AI tools scan files (not just user input).

## Key Finding

**YES, IT WORKS.** The proxy intercepts file contents when AI reads them.

### Evidence

Stats progression during session:
- Before: 25 items protected, 27 tokens
- After: 32 items protected, 34 tokens
- **+7 PII items caught** just from Claude Code reading files

### How It Works

```
User asks AI to read file
    ↓
AI tool reads file from disk
    ↓
File contents included in API request body
    ↓
Proxy intercepts request, scans ALL JSON strings
    ↓
PII replaced with tokens before reaching cloud
```

The magic is in `guardian_proxy.py:protect_json()` which recursively processes all strings in the request payload — including tool results from Read/Grep/Glob.

---

## Side Effect Discovered

When Claude writes a file, it writes what it "sees" — which includes tokens.

**Example:**
- README had `db_password = "hunter2"` as example
- I read it (saw token)
- I edited it (wrote token back to disk)
- Now the file on disk contains `◈PG:PASS_db352efcc44b◈`

**Question for tomorrow:** Is this desired behavior or a bug?

Possible stances:
1. **Feature**: Tokens in files = extra protection layer
2. **Bug**: Should only tokenize API traffic, not modify files
3. **Configurable**: Let user decide

---

## Tomorrow's Tasks

### 1. Verify with Antigravity + Gemini (Issue #9)

```bash
# Start the proxy (if not running)
./guardian enable

# Launch Antigravity with protection
antigravity-protected

# Or manually:
GOOGLE_API_BASE=http://localhost:6660 antigravity
```

Then ask Antigravity to scan the codebase and check:
```bash
./guardian status
# Look for "google" in by_provider
```

### 2. Check Issue #9

https://github.com/Keeper888/privacyguardian/issues/9

Close it if Antigravity test passes.

### 3. Consider the Write-Back Problem

Decide if tokens being written to disk is:
- Expected behavior
- A bug to fix
- Something to document

---

## Comparison with privacy-firewall

| Feature | privacy-firewall | privacyguardian |
|---------|------------------|-----------------|
| Stars | 215 | 1 |
| Approach | Browser extension | Transparent proxy |
| Protects user input | ✅ | ✅ |
| Protects codebase scans | ❌ (browser only) | ✅ (proxy sees all) |
| Target | Web AI (ChatGPT, Claude web) | Terminal/IDE AI |

**Your unique value prop:** You protect the entire codebase, not just what users type. privacy-firewall can't do this.

---

## Marketing Notes

### Current README Tagline
> Stop AI from seeing your personal data.

### Goal Added (as blockquote)
> When AI coding tools scan your files, they read everything — API keys in configs, credentials in `.env` files, customer data in test fixtures. We're working to intercept all of it before it leaves your machine.

### Better Pitch for Launch

"Claude Code sees every file you open. Every API key in your config. Every password in your .env. PrivacyGuardian intercepts it all before it leaves your machine."

### Launch Channels
- Hacker News (Show HN)
- Reddit: r/privacy, r/commandline, r/neovim, r/linux, r/LocalLLaMA
- Target communities: Claude Code users, Cursor users, Zed users

---

## Files Changed

- `README.md` - Added codebase protection goal
- Created GitHub Issue #9 for verification tracking

---

## Commands Quick Reference

```bash
./guardian gui        # Open dashboard
./guardian enable     # Start protection
./guardian disable    # Stop protection
./guardian status     # Check stats
curl http://localhost:6660/__guardian__/stats | python3 -m json.tool
```

