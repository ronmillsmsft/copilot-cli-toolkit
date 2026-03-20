# Tier 3: Automation Workflows

> Move from "AI that remembers" to "AI that runs your operations."

## What's Here

Four standalone Python tools that automate recurring workflows. Each uses SQLite for storage, has zero external dependencies, and integrates with your Copilot CLI assistant.

| Tool | Purpose | Time Saved |
|------|---------|------------|
| **[Action Tracker](action-tracker/)** | Ops Playbook: recurring routines with scheduling and execution history | 15-30 min/day |
| **[Meeting Prep](meeting-prep/)** | Meeting configs, topic tracking, and prep skeleton generation | 20-40 min/meeting |
| **[Standup Prep](standup-prep/)** | Work item analysis: P1s, stale items, state changes, portfolio pulse | 15-20 min/standup |
| **[Daily Ops](daily-ops/)** | Aggregation scanner across all workflow databases | 10-15 min/day |

## How They Connect

```
┌─────────────────────────────────────────────────────────┐
│                    Daily Ops Scanner                     │
│            (runs at every session start)                 │
│                                                         │
│   Reads from:                                           │
│   ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
│   │   Action     │  │   Meeting    │  │   Standup    │  │
│   │   Tracker    │  │   Prep       │  │   Prep       │  │
│   │   .db        │  │   .db        │  │   .db        │  │
│   └─────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
  Due routines?      Upcoming meetings?   P1s or stale items?
  Overdue items?     Active topics?       State changes?
```

The Daily Ops scanner aggregates alerts from all three tools into a single output that your AI assistant reads at session start. This is the "proactive intelligence" layer.

## Getting Started

### 1. Pick a tool and seed it

```bash
cd workflows/action-tracker
python action_tracker.py seed
python action_tracker.py playbook
```

### 2. Wire into your boot sequence

Add to your `copilot-instructions.md`:

```markdown
At session start, run:
  python workflows/daily-ops/daily_ops.py scan
Surface results in your greeting.
```

### 3. Customize for your workflow

Each tool has seed data for demo purposes. Replace with your own:
- **Action Tracker**: Add your recurring routines (standups, reviews, approvals)
- **Meeting Prep**: Configure your actual meetings and stakeholders
- **Standup Prep**: Import work items from your tracking system (ADO, Jira, GitHub)

## Design Principles

- **Zero dependencies**: Python stdlib + SQLite only. No pip install required.
- **Standalone tools**: Each works independently. Use one or all four.
- **AI-ready output**: Structured data that your AI assistant can parse and act on.
- **Seed then customize**: Start with examples, replace with your real workflows.
- **Graceful degradation**: Daily Ops skips missing databases instead of crashing.

## CLI Quick Reference

```bash
# Action Tracker
python action_tracker.py playbook          # List routines
python action_tracker.py due               # What needs to run now?
python action_tracker.py run <id>          # Start a routine run
python action_tracker.py complete <run_id> # Complete a run

# Meeting Prep
python meeting_prep.py list               # Show configured meetings
python meeting_prep.py prep <id>          # Generate prep skeleton
python meeting_prep.py topic add <id> "text"  # Add discussion topic
python meeting_prep.py upcoming           # Next 7 days of meetings

# Standup Prep
python standup_prep.py scan               # Analyze work items
python standup_prep.py pulse              # Portfolio breakdown
python standup_prep.py import items.json  # Load from JSON

# Daily Ops
python daily_ops.py scan                  # Full aggregation scan
python daily_ops.py status                # Quick health check
```
