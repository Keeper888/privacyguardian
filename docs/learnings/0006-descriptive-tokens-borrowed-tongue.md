# Descriptive Tokens: The "Borrowed Tongue" Architecture

**Date:** 2026-01-02
**Status:** Concept Design
**Priority:** High - Major Feature Enhancement

## The Problem

Current PrivacyGuardian protects PII (emails, passwords, API keys) by replacing them with opaque tokens like `◈PG:EMAIL_a7f2◈`. But:

1. **Only PII is protected** - function names, hostnames, company names leak through
2. **Opaque tokens limit AI understanding** - `◈F01◈` tells the AI nothing useful
3. **Context clues can reconstruct meaning** - "connect to acme" + hostname pattern = identity leak

## The Insight: Borrowed Tongue Metaphor

> "We have our own language that only works in our courtyard. Once you leave, it's incomprehensible. You borrow a tongue - while using it you understand us, but once outside you can't reconstruct what you learned."

The "tongue" is a **local-only mapping** that exists solely on the user's machine.

## Key Realization: What AI Needs vs What Leaks Privacy

```
┌─────────────────────────────────────────────────────────────────┐
│                     THE TRADEOFF                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   AI NEEDS (to help effectively):     PRIVACY LEAK:             │
│   ─────────────────────────────────   ─────────────────────     │
│   • Library names (psycopg2)          • Company names           │
│   • Function signatures               • Internal hostnames      │
│   • Parameter types                   • Employee names          │
│   • Code structure                    • Credentials             │
│   • Design patterns                   • Infrastructure details  │
│                                                                  │
│   SOLUTION: Keep TYPE visible, hide VALUE                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## The Descriptive Token Innovation

Instead of opaque tokens, use **descriptive tokens** that reveal structure without revealing values:

### Old Approach (Opaque)
```python
def ◈F01◈():
    return psycopg2.connect(host=◈S01◈, user=◈S02◈)
```
AI sees: "Some function connecting to something with something"

### New Approach (Descriptive)
```python
def ◈F01|len:26|pre:connect_to_|suf:_production|snake◈():
    return psycopg2.connect(
        host=◈S01|len:22|hostname|suf:.internal|parts:3◈,
        user=◈S02|len:10|username|suf:_admin◈
    )
```
AI sees: "A production connection function using internal hostname and admin user"

## What Descriptive Tokens Reveal

| Original Value | Token | AI Understands |
|----------------|-------|----------------|
| `connect_to_acme_production` | `◈F01\|len:26\|pre:connect_to_\|suf:_production\|snake◈` | Connection function for production |
| `db.acme-corp.internal` | `◈S01\|len:22\|hostname\|suf:.internal\|parts:3◈` | Internal 3-part hostname |
| `john_admin` | `◈S02\|len:10\|username\|suf:_admin◈` | Admin-level username |
| `SuperS3cret!` | `◈S03\|len:12\|credential\|entropy:high◈` | Strong credential |

## What AI Can Do With This

1. **Suggest consistent naming**: "For staging, use `◈F02|pre:connect_to_|suf:_staging◈`"
2. **Understand patterns**: Knows it's PostgreSQL, internal network, admin access
3. **Write compatible code**: Matches your naming conventions
4. **Debug effectively**: Understands the architecture without seeing secrets

## What AI CANNOT Do

1. **Reconstruct company name**: "acme-corp" is hidden in the middle
2. **Identify specific users**: "john" is never revealed
3. **Access credentials**: Only knows entropy level, not value
4. **Map infrastructure**: Knows pattern, not actual hosts

## Token Metadata Categories

### For Identifiers (function/variable names)
```
|len:N|          - Character length
|pre:xxx|        - Prefix (safe portion)
|suf:xxx|        - Suffix (safe portion)
|snake|camel|pascal|  - Case style
|words:N|        - Word count in identifier
```

### For Strings
```
|len:N|          - Character length
|hostname|email|path|url|credential|  - Type classification
|parts:N|        - Segments (e.g., 3 for "a.b.c")
|entropy:low|med|high|  - Randomness level
|pre:xxx|suf:xxx|  - Safe prefix/suffix
```

### For Comments
```
|len:N|          - Character length
|docstring|inline|block|  - Comment type
|mentions:kw1,kw2|  - Safe keywords mentioned
```

## Safety Rules for Hint Extraction

**SAFE to reveal:**
- Common prefixes: `get_`, `set_`, `connect_`, `init_`, `handle_`
- Common suffixes: `_production`, `_staging`, `_handler`, `_service`, `_data`
- Generic type hints: hostname, credential, username, email
- Structural info: length, parts count, case style

**NEVER reveal:**
- Company/org names
- Person names
- Domain-specific identifiers
- Unique project names
- Anything that appears in only one place (unique identifier)

## Implementation Approach

### Phase 1: AST-Based Tokenization
- Parse code using language-specific AST
- Identify: function names, variable names, string literals, comments
- Extract safe metadata
- Generate descriptive tokens

### Phase 2: Hint Safety Analysis
- Check if prefix/suffix contains sensitive patterns
- Use entropy detection for strings
- Maintain blocklist of company-specific terms
- User-configurable sensitivity rules

### Phase 3: Local Tongue Storage
```
~/.privacyguardian/
├── vault.db           # Encrypted token→value mapping
├── tongue.json        # Current session's descriptive tokens
└── safety_rules.yaml  # User-defined hint safety rules
```

## Example: Full Transformation

### Input (Your File)
```python
def connect_to_acme_production():
    """Initialize connection to Acme Corp's main database."""
    return psycopg2.connect(
        host="db.acme-corp.internal",
        port=5432,
        user="john_admin",
        password="SuperS3cret!",
        database="customer_data"
    )
```

### Output (What Cloud Sees)
```python
def ◈F01|len:26|pre:connect_to_|suf:_production|snake◈():
    """◈C01|len:48|docstring|mentions:connection,database◈"""
    return psycopg2.connect(
        host=◈S01|len:22|hostname|suf:.internal|parts:3◈,
        port=5432,
        user=◈S02|len:10|username|suf:_admin◈,
        password=◈S03|len:12|credential|entropy:high◈,
        database=◈S04|len:13|dbname|suf:_data◈
    )
```

### What AI Understands
- PostgreSQL connection function (sees `psycopg2.connect`)
- Production environment (sees `_production` suffix)
- Internal network (sees `.internal` suffix)
- Admin-level access (sees `_admin` suffix)
- Strong password (sees `entropy:high`)
- Data-focused database (sees `_data` suffix)

### What AI Cannot Reconstruct
- Company is "Acme Corp"
- Admin is "John"
- Actual hostname, password, database name

## Open Questions

1. **Language Support**: Start with Python? Need AST parsers per language
2. **Performance**: AST parsing adds latency - acceptable?
3. **Edge Cases**: What if prefix IS the sensitive part?
4. **User Config**: How much control over what's revealed?
5. **Backwards Compat**: Mix with current PII-only approach?

## Next Steps

1. Prototype Python AST tokenizer
2. Define safety rules for common patterns
3. Test with real codebases for quality of AI assistance
4. Measure information leakage vs AI helpfulness tradeoff

---

*This learning emerged from a deep discussion about the fundamental tension between AI assistance (needs to understand code) and privacy (code contains secrets). The "borrowed tongue" metaphor clarified the goal: local comprehension with remote obfuscation.*
