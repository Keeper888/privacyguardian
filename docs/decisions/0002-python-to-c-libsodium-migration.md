# ADR-0002: Migration from Python to C libsodium Encryption

**Date:** 2026-01-02
**Author:** Keeper

## Context

PrivacyGuardian was prototyped using Python Fernet (AES-128-CBC) to prove the concept works. Now that the architecture is validated, the next step is migrating to C with libsodium (XChaCha20-Poly1305) for optimization.

The repository contains only 2 commits because personal data had to be removed from the initial commit history.

## Current State

| Component | Technology | Status |
|-----------|------------|--------|
| Python encryption | cryptography.fernet (AES-128-CBC) | Proof of concept, working |
| C encryption | libsodium XChaCha20-Poly1305 (crypto_core.c) | Written, not integrated |

## Decision

Migrate from Python Fernet to C libsodium encryption.

**Reasons:**
- Python implementation proved the architecture works
- C is the natural next step for optimization
- Faster encryption/decryption (native performance)
- Lower memory footprint
- Fewer runtime dependencies (libsodium replaces Python cryptography package)
- XChaCha20-Poly1305 is more modern than AES-128-CBC (256-bit keys, built-in authentication)

## Implementation Plan

1. Clean up technical debt in Python codebase
2. Build libpgcrypto.so shared library from existing crypto_core.c
3. Create Python bindings (ctypes/cffi) to call C functions
4. Replace Fernet calls in guardian_proxy.py with C library calls
5. Remove Python cryptography dependency
6. Test and validate

## Dependencies

**Current (Python):**
- cryptography package (+ its transitive dependencies)

**After migration (C):**

Build-time:
- libsodium-dev — encryption library headers
- gcc — C compiler
- make — build automation

Run-time:
- libsodium23 — encryption library (single dependency)

## Technical Debt

One-click fix (next commit I'll fix it):

| File | Issues |
|------|--------|
| guardian_proxy.py | 3 unused imports |
| transparent_proxy.py | 10 unused imports |
| gui/dashboard.py | 10 unused imports/variables |
| installer.py | 2 unused imports |
| request_parser.py | 3 unused imports/variables |
| setup_wizard.py | 1 unused variable |
| pii_detector.py | 3 unused imports |
| llm_monitor.py | 4 unused imports |
| notifications.py | 1 unused import |

Auto-fix with: `ruff check code/ --fix`

## Consequences

### Positive

- Faster crypto operations (C vs interpreted Python)
- Smaller memory footprint
- Fewer dependencies (one system library vs Python package tree)
- Stronger algorithm (XChaCha20-Poly1305, 256-bit keys)
- Universal portability - C source compiles on any architecture

### Negative

- Users need build toolchain (gcc, make, libsodium-dev) — not a big problem to be honest
- One-time compilation step required

---

**Note:** The Python version remains functional for users who prefer not to compile. This migration optimizes performance, not fixes a broken system.
