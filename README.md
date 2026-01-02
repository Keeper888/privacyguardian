# PrivacyGuardian

**Stop AI from seeing your personal data.**

Your emails, passwords, medical records - encrypted before they leave your computer. AI sees tokens, you see your real data.

> **Goal: Protect your entire codebase, not just your input.**
>
> When AI coding tools scan your files, they read everything — API keys in configs, credentials in `.env` files, customer data in test fixtures. We're working to intercept all of it before it leaves your machine. [Track progress](https://github.com/Keeper888/privacyguardian/issues/9)

<p align="center">
  <img src="images/gui-dashboard.png" alt="PrivacyGuardian Dashboard" width="700"/>
</p>
<p align="center"><code>./guardian gui</code></p>

<p align="center">
  <img src="images/cli-demo.png" alt="CLI Protection Demo" width="700"/>
</p>

---

**Roadmap**

| Stars | What's Next |
|-------|-------------|
| **10** | Multi-platform support (tested on ARM64, expanding to x86_64) |
| **25** | Semantic PII detection (context-aware, not just regex patterns) |
| **50** | At this point I am hallucinating so I first need to go to a psychiatrist and check if I am ok then if 50 stars is true then I have to keep developing, I don't know what we do, we see the issues you guys open and I'll fix them |
| **100** | Mobile support (iOS/Android companion apps) |

Currently tested on Claude Code and Antigravity. Something broken? Open an issue.

---

## Quick Start (2 minutes)

```bash
# 1. Download
git clone https://github.com/Keeper888/privacyguardian.git
cd privacyguardian

# 2. Install dependencies + build
sudo apt install libsodium-dev  # encryption library
make                            # build C crypto library

# 3. Setup
./guardian setup

# 4. Open GUI
./guardian gui
```

### Want an easier install? Use the Python version

```bash
git clone https://github.com/Keeper888/privacyguardian.git
cd privacyguardian
git checkout python-stable   # no C build needed
./guardian setup
./guardian gui
```

The `python-stable` branch uses pure Python encryption (Fernet/AES).

**In the GUI:**
1. Click **Setup** → Select apps → **Apply**
2. Press **Enter** in the terminal that opens
3. Toggle **Protection ON**
4. Done! Use `claude` normally in any new terminal

---

## What it protects

| Personal | Financial | Health | Technical |
|----------|-----------|--------|-----------|
| Email | Credit Card | Medical Records | API Keys |
| Phone | Bank Account | Insurance ID | Passwords |
| SSN | IBAN | DEA/NPI Numbers | AWS/GitHub Tokens |
| Passport | Tax ID | ICD-10 Codes | Database URLs |

**35+ data types** - all detected locally, no cloud needed.

---

## How it works

```
You type:  "My email is john@example.com"
AI sees:   "My email is ◈PG:EMAI_a7f2◈"
You see:   "My email is john@example.com"
```

AI can still help you. It just never sees your real data.

---

## GUI Apps (Cursor, Antigravity, etc.)

For GUI apps, Setup creates launchers in `~/.local/bin/`:

```bash
# After setup, run protected versions:
cursor-protected      # Cursor with protection
antigravity-protected # Antigravity with protection
windsurf-protected    # Windsurf with protection
zed-protected         # Zed with protection
```

Or add `~/.local/bin` to your PATH, then use these from anywhere.

---

## Commands

```bash
./guardian gui       # Open dashboard
./guardian enable    # Turn on protection
./guardian disable   # Turn off protection
./guardian status    # Check if running
```

---

## Requirements

**System:**
- Linux (Ubuntu, Debian, Fedora, Arch)

**Build (C crypto):**
- gcc
- make
- libsodium-dev (`sudo apt install libsodium-dev`)

**Runtime (proxy server):**
- Python 3.8+
- pip packages (installed via `./guardian setup`)

---

## License

MIT
