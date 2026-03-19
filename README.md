# Copilot CLI Toolkit

> Build a persistent AI assistant in GitHub Copilot CLI that remembers you, automates your workflows, and gets smarter every session.

## What This Is

A modular toolkit for turning GitHub Copilot CLI into a **persistent, personalized AI teammate**. Instead of starting fresh every conversation, your assistant remembers your preferences, tracks decisions, automates routine work, and learns your patterns over time.

Built by a busy PM who needed to save time, not learn a framework.

## Quick Start (5 Minutes)

```bash
# 1. Clone this repo
git clone https://github.com/ronmillsmsft/copilot-cli-toolkit.git
cd copilot-cli-toolkit

# 2. Copy the starter instructions to your Copilot CLI config
cp starter/copilot-instructions.md ~/.copilot/

# 3. Initialize the memory system
cd memory
python cli.py status

# 4. Start Copilot CLI — your assistant now has persistent memory
copilot
```

That's it. Your assistant will greet you by name, remember past sessions, and build context over time.

## How It Works

```
┌─────────────────────────────────────────────────────┐
│                  Copilot CLI Session                │
│                                                     │
│  ┌──────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │  Instruction  │  │   Memory    │  │  Tools &  │  │
│  │    Files      │  │   System    │  │   MCPs    │  │
│  │              │  │             │  │           │  │
│  │  SOUL.md     │  │  Prefs DB   │  │  GitHub   │  │
│  │  USER.md     │  │  Insights   │  │  Azure    │  │
│  │  AGENTS.md   │  │  Convos     │  │  Planner  │  │
│  │  TOOLS.md    │  │  Search     │  │  Browser  │  │
│  └──────────────┘  └─────────────┘  └───────────┘  │
│                         │                           │
│              ┌──────────┴──────────┐                │
│              │   SQLite Databases  │                │
│              │   (zero-dependency  │                │
│              │    persistence)     │                │
│              └─────────────────────┘                │
└─────────────────────────────────────────────────────┘
```

Your assistant loads instruction files at session start, queries memory for context, uses available tools to get work done, and logs meaningful work back to memory at session end.

## Tiers

Pick your level. Each tier builds on the previous.

### 🟢 Tier 1: Start Here
**Time: 5 minutes** | Zero dependencies

Give your Copilot CLI a personality, custom instructions, and consistent behavior.

- `starter/copilot-instructions.md` — Drop-in custom instruction template
- `starter/QUICK-START.md` — Step-by-step setup guide

### 🔵 Tier 2: Foundation (Memory)
**Time: 15 minutes** | Requires: Python 3.10+

Add persistent memory so your assistant remembers across sessions.

- `memory/` — Full memory system (SQLite + FTS5 search)
- `memory/cli.py` — CLI for preferences, insights, conversations
- `instructions/` — Structured instruction files (SOUL, USER, AGENTS, TOOLS, BOUNDARIES)
- `docs/memory-guide.md` — How the memory system works

### 🟡 Tier 3: Workflows
**Time: 30 minutes** | Requires: Tier 2

Automate real work — meeting prep, standup scans, action tracking.

- `workflows/meeting-prep/` — ADO-integrated meeting preparation
- `workflows/standup-prep/` — Automated standup scan with stale item detection
- `workflows/action-tracker/` — Ops playbook with recurring routines
- `workflows/daily-ops/` — Daily health scan across all systems

### 🔴 Tier 4: Advanced
**Time: 1 hour** | Requires: Tier 2

Multi-agent orchestration, dashboards, MCP server integrations.

- `advanced/agent-team/` — Agent engine with task tracking, trust scoring, governance
- `advanced/dashboard/` — Streamlit ops dashboard connecting all databases
- `advanced/mcp-configs/` — MCP server configurations (Planner, ADO, OneNote, etc.)

## What Makes This Different

| Traditional AI Chat | Copilot CLI Toolkit |
|---|---|
| Forgets everything between sessions | Remembers preferences, decisions, patterns |
| Generic responses | Personalized to your role, tools, and style |
| You do the work, AI advises | AI executes, you review |
| One-size-fits-all | Modular — use only what you need |
| Requires frameworks/infra | Zero dependencies (Python + SQLite) |

## Design Principles

1. **Action Over Discussion** — Default to doing, not describing what could be done
2. **Own End-to-End** — When the assistant takes a task, it owns it to completion
3. **Teach While Doing** — Explain the why, not just the what
4. **Persistent Context** — Every session builds on the last

## Real Results

Built and used daily by a PM managing 15+ Power BI reports across a 130+ item ADO backlog:

- **88 sessions** with full conversation memory
- **115 preferences** learned and applied automatically
- **280 active insights** tracking decisions, patterns, and goals
- **11 specialized agents** (CoreIdentity approvals, meeting prep, standup scan, etc.)
- **24+ hours of manual work saved** (and counting)

## Requirements

- GitHub Copilot CLI (with custom instructions support)
- Python 3.10+ (for memory system)
- SQLite (included with Python)
- No cloud services, no API keys, no external dependencies

## Project Structure

```
copilot-cli-toolkit/
├── README.md                   # You are here
├── starter/                    # Tier 1: Quick start
│   ├── QUICK-START.md
│   └── copilot-instructions.md
├── memory/                     # Tier 2: Persistent memory
│   ├── cli.py
│   ├── memory.db (created on first run)
│   └── README.md
├── instructions/               # Tier 2: Instruction files
│   ├── SOUL.md
│   ├── USER.md
│   ├── AGENTS.md
│   ├── TOOLS.md
│   ├── BOUNDARIES.md
│   └── MEMORY-GUIDE.md
├── workflows/                  # Tier 3: Automation
│   ├── meeting-prep/
│   ├── standup-prep/
│   ├── action-tracker/
│   └── daily-ops/
├── advanced/                   # Tier 4: Multi-agent
│   ├── agent-team/
│   ├── dashboard/
│   └── mcp-configs/
└── docs/                       # Guides and reference
    ├── memory-guide.md
    ├── instruction-files.md
    └── architecture.md
```

## Contributing

This is currently a personal toolkit. If you find it useful, let me know — happy to collaborate.

## License

MIT

---

*Built by Ron Mills with Max Headroom* 📺
