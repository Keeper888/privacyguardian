# Why Hybrid Approach: Use Python for Easy Logic + C for Serious Stuff

**Date:** 2026-01-02
**Context:** PrivacyGuardian architecture decision

## The Pattern

```
┌─────────────────────────────────────────────────────────┐
│                    Python Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │ FastAPI     │  │ PII         │  │ Request     │      │
│  │ Proxy       │  │ Detector    │  │ Parser      │      │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │
│         │                │                │              │
│         └────────────────┼────────────────┘              │
│                          │                               │
│                          ▼                               │
│                  ┌───────────────┐                       │
│                  │ crypto_native │ (Python ctypes)       │
│                  └───────┬───────┘                       │
└──────────────────────────┼───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                    C Layer (libpgcrypto.so)              │
│           XChaCha20-Poly1305 via libsodium               │
│                 (fast, native encryption)                │
└──────────────────────────────────────────────────────────┘
```

## What Goes Where

| Layer | Handles | Why |
|-------|---------|-----|
| **Python** | HTTP proxy, PII detection, JSON parsing, SQLite, GUI | I/O bound, easy to write and maintain |
| **C** | Encryption/decryption | CPU bound, needs raw speed |

## Why Not All C?

Rewriting everything in C would be:
- Massive effort for little gain
- Harder to maintain (memory management, segfaults)
- More error-prone
- Unnecessary - proxy is mostly waiting for network I/O

The proxy spends 99% of its time waiting for:
- HTTP requests to arrive
- Responses from upstream APIs
- Database writes

Only encryption is CPU-intensive. That's what we moved to C.

## Why Not All Python?

Python's `cryptography` package works, but:
- It's a heavy dependency (pulls OpenSSL bindings, cffi, etc.)
- Fernet uses AES-128-CBC (older algorithm)
- Interpreted = slower for tight loops

C with libsodium gives us:
- XChaCha20-Poly1305 (modern, 256-bit)
- Native speed
- Single system dependency (`libsodium`)

## The Bridge: ctypes

`crypto_native.py` uses Python's `ctypes` to call C functions:

```python
# Load C library
self._lib = ctypes.CDLL("build/libpgcrypto.so")

# Call C function from Python
result_ptr = self._lib.privacy_guardian_encrypt(
    plaintext.encode('utf-8'),
    pii_type.encode('utf-8')
)
```

No compilation needed for Python code. C library compiles once with `make`.

## Real-World Examples

This pattern is everywhere:
- **numpy** - Python API, C/Fortran math
- **TensorFlow** - Python API, C++ compute
- **cryptography** - Python API, OpenSSL C
- **Pillow** - Python API, C image processing

## Key Takeaway

Use the right tool for each job:
- Python for glue, logic, I/O
- C for compute-heavy operations

Don't rewrite everything in C just because "C is faster". Most code is waiting, not computing.
