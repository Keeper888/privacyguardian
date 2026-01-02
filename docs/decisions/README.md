# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for PrivacyGuardian.

## What is an ADR?

An ADR captures an important architectural decision along with its context and consequences. We use ADRs to document significant decisions that affect the structure, non-functional characteristics, dependencies, interfaces, or construction techniques of the project.

## When to Write an ADR

Write an ADR when:
- Choosing between multiple viable approaches
- Making a decision that's difficult to reverse
- Adopting a new technology or pattern
- Deprecating an existing approach
- Making a decision others might question later

## Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| [ADR-0001](0001-wrapper-based-protection.md) | Wrapper-Based Protection over System-Wide Proxy | Accepted | 2024-12-29 |

## Status Definitions

- **Proposed**: Under discussion
- **Accepted**: Approved and implemented
- **Deprecated**: No longer recommended
- **Superseded**: Replaced by another ADR

## Creating a New ADR

```bash
./docs/new-doc.sh adr "Your ADR Title"
```

Or copy `../templates/ADR_TEMPLATE.md` and update the ID.
