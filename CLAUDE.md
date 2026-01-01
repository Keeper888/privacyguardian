# PrivacyGuardian - Claude Code Instructions

## Before Every Commit

**ALWAYS check for personal data before committing:**

```bash
# Check for username (replace YOUR_USERNAME with actual username)
grep -r "YOUR_USERNAME" --include="*.py" --include="*.sh" --include="*.md" . | grep -v ".git"

# Check for home paths
grep -r "/home/" --include="*.py" --include="*.sh" --include="*.md" . | grep -v ".git"

# Check for real emails (not examples)
grep -rE "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}" --include="*.py" --include="*.md" . | grep -v ".git" | grep -v "example" | grep -v "john@" | grep -v "user@"
```

If any personal data is found, replace with generic placeholders before committing.

## Project Structure

- `guardian` - Main CLI entry point
- `pg-wrapper` - Wrapper script for LLM apps
- `code/` - Python source code
- `code/gui/` - GTK4 dashboard
- `packaging/` - .deb package build scripts
- `images/` - Screenshots for README
