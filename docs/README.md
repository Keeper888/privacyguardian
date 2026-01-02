# PrivacyGuardian Developer Documentation

This directory contains project documentation for tracking decisions, implementation progress, bugs, and learnings.

## Structure

```
docs/
├── README.md           # This file
├── decisions/          # Architecture Decision Records (ADRs)
├── journal/            # Implementation journal / session notes
├── bugs/               # Bug documentation and analysis
├── learnings/          # Technical learnings and research
├── templates/          # Templates for new entries
└── new-doc.sh          # Helper script for creating entries
```

## Quick Start

### Create a new entry

```bash
# Architecture Decision Record
./docs/new-doc.sh adr "Use SQLite for token storage"

# Journal entry (auto-dated)
./docs/new-doc.sh journal "Implemented regex-based tokenizer"

# Bug report
./docs/new-doc.sh bug "Proxy fails on malformed JSON"

# Learning note
./docs/new-doc.sh learning "GTK4 async patterns"
```

### Navigation

- **[decisions/](decisions/)** - Why we built things a certain way
- **[journal/](journal/)** - What we worked on and when
- **[bugs/](bugs/)** - Issues found and how they were fixed
- **[learnings/](learnings/)** - Technical knowledge gained

## Conventions

### Naming

- ADRs: `NNNN-kebab-case-title.md` (e.g., `0001-wrapper-based-protection.md`)
- Journal: `YYYY-MM-DD-brief-description.md`
- Bugs: `NNNN-brief-description.md`
- Learnings: `kebab-case-topic.md`

### Linking

Use relative links to connect related documents:
- `See [ADR-0001](../decisions/0001-wrapper-based-protection.md)`
- `Resolved in [journal entry](../journal/2025-01-02-proxy-rewrite.md)`

### Tags

Journal entries use tags: `feature`, `refactor`, `bugfix`, `research`, `infrastructure`

## Contributing

1. Use the appropriate template from `templates/`
2. Follow naming conventions
3. Update the relevant README index
4. Link related documents
