# Copilot CLI Toolkit

> Build a persistent AI assistant in GitHub Copilot CLI that remembers you, automates your workflows, and gets smarter every session.

🌐 **[View the landing page](https://ronmillsmsft.github.io/copilot-cli-toolkit/)** for an interactive overview with setup wizard.

## What This Is

A modular toolkit for turning GitHub Copilot CLI into a **persistent, personalized AI teammate**. Instead of starting fresh every conversation, your assistant remembers your preferences, tracks decisions, automates routine work, and learns your patterns over time.

Built by a busy PM who needed to save time, not learn a framework.

## Quick Start (5 Minutes)

### Option A: Setup Wizard (Recommended)

Open **[starter/setup-wizard.html](starter/setup-wizard.html)** in your browser. It checks prerequisites, generates config files, and walks you through post-download steps. No command line experience needed.

### Option B: Manual Setup

```bash
# 1. Clone this repo
git clone https://github.com/ronmillsmsft/copilot-cli-toolkit.git
cd copilot-cli-toolkit

# 2. Edit the instruction files to match your role and style
# See instructions/USER.md, instructions/SOUL.md, etc.

# 3. Initialize the memory system
cd memory
python cli.py status

# 4. Start Copilot CLI with persistent memory
gh copilot
```

That's it. Your assistant will greet you by name, remember past sessions, and build context over time.

## How It Works

> 📐 **[Full architecture diagrams →](docs/architecture.md)** (system overview, data flow, tier map, role modules)

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

The **core platform** (memory + instructions + CLI tools) is universal. **Role-specific modules** (PM workflows, engineering tools, analyst pipelines) plug in on top. See the [architecture docs](docs/architecture.md) for the full visual breakdown.

## Tiers

Pick your level. Each tier builds on the previous.

### 🟢 Tier 1: Start Here
**Time: 5 minutes** | Zero dependencies

Give your Copilot CLI a personality, custom instructions, and consistent behavior.

- `starter/copilot-instructions.md` - Drop-in custom instruction template
- `starter/QUICK-START.md` - Step-by-step setup guide

### 🔵 Tier 2: Foundation (Memory)
**Time: 15 minutes** | Requires: Python 3.10+

Add persistent memory so your assistant remembers across sessions.

- `memory/` - Full memory system (SQLite + FTS5 search)
- `memory/cli.py` - CLI for preferences, insights, conversations
- `instructions/` - Structured instruction files (SOUL, USER, AGENTS, TOOLS, BOUNDARIES)
- `docs/memory-guide.md` - How the memory system works

### 🟡 Tier 3: Workflows
**Time: 30 minutes** | Requires: Tier 2

Automate real work: meeting prep, standup scans, action tracking.

- `workflows/meeting-prep/` - Meeting configs, topic tracking, prep skeleton generation
- `workflows/standup-prep/` - Work item analysis with staleness detection and portfolio pulse
- `workflows/action-tracker/` - Ops playbook with recurring routines and copy-paste CLI prompts
- `workflows/daily-ops/` - Aggregation scanner across all workflow databases

### 🔴 Tier 4: Advanced
**Time: 1 hour** | Requires: Tier 2

Multi-agent orchestration, dashboards, MCP server integrations.

- `advanced/agent-team/` - Agent engine with task tracking, trust scoring, governance
- `advanced/dashboard/` - Streamlit ops dashboard with 7 pages (Playbook, Meeting Hub, Agent Team, Session Close-Out, Notebook, Tools, Reliability)
- `advanced/mcp-configs/` - MCP server configurations (Planner, ADO, OneNote, etc.)

## What Makes This Different

| Traditional AI Chat | Copilot CLI Toolkit |
|---|---|
| Forgets everything between sessions | Remembers preferences, decisions, patterns |
| Generic responses | Personalized to your role, tools, and style |
| You do the work, AI advises | AI executes, you review |
| One-size-fits-all | Modular - use only what you need |
| Requires frameworks/infra | Zero dependencies (Python + SQLite) |

## Design Principles

1. **Action Over Discussion** - Default to doing, not describing what could be done
2. **Own End-to-End** - When the assistant takes a task, it owns it to completion
3. **Teach While Doing** - Explain the why, not just the what
4. **Persistent Context** - Every session builds on the last

## Real Results

Built and used daily by a PM managing 15+ Power BI reports across a 130+ item ADO backlog:

- **88 sessions** with full conversation memory
- **115 preferences** learned and applied automatically
- **280 active insights** tracking decisions, patterns, and goals
- **11 specialized agents** (CoreIdentity approvals, meeting prep, standup scan, etc.)
- **40+ hours of manual work saved** (and counting)

## Requirements

- GitHub CLI (`gh`) with Copilot extension
- Python 3.10+ (for memory system)
- SQLite (included with Python)
- No cloud services, no API keys, no external dependencies

Use the [setup wizard](starter/setup-wizard.html) to check prerequisites automatically.

## Staying Updated

The toolkit includes a self-updater that pulls improvements while protecting your personalized files:

```bash
python toolkit-update.py check    # Check for updates
python toolkit-update.py update   # Apply updates (with backup)
python toolkit-update.py status   # Current version info
```

Your customized files (USER.md, SOUL.md, copilot-instructions.md, databases) are never overwritten.

## Project Structure

```
copilot-cli-toolkit/
├── index.html                  # Landing page (GitHub Pages)
├── README.md                   # You are here
├── toolkit-update.py           # Self-updater (safe updates)
├── starter/                    # Tier 1: Quick start
│   ├── QUICK-START.md
│   ├── copilot-instructions.md
│   └── setup-wizard.html       # Guided setup wizard
├── memory/                     # Tier 2: Persistent memory
│   ├── cli.py
│   ├── setup_db.py
│   ├── src/
│   └── README.md
├── instructions/               # Tier 2: Instruction files
│   ├── AGENTS.md
│   ├── BOUNDARIES.md
│   ├── SOUL.md
│   ├── TOOLS.md
│   └── USER.md
├── workflows/                  # Tier 3: Automation
│   ├── README.md
│   ├── action-tracker/
│   ├── meeting-prep/
│   ├── standup-prep/
│   └── daily-ops/
├── advanced/                   # Tier 4: Advanced
│   ├── agent-team/
│   ├── dashboard/
│   │   └── ops_dashboard.py    # 7-page Streamlit dashboard
│   └── mcp-configs/
└── docs/                       # Guides and reference
    ├── architecture.md
    ├── instruction-files.md
    └── memory-guide.md
```

## Contributing

This is currently a personal toolkit. If you find it useful, let me know - happy to collaborate.

## License

MIT

---

*Built by Ron Mills with Max Headroom* 📺
