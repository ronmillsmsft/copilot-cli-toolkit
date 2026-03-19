# Memory System Guide

> How the persistent memory system works and how your assistant should use it.

## Two-Layer Architecture

### Layer 1: Agent Memory (Durable)
- **Where:** `memory/memory.db` (SQLite)
- **Survives:** Everything. Persists across all sessions forever.
- **Stores:** Conversations, preferences, insights
- **Accessed via:** `python cli.py` commands

### Layer 2: Session Context (Ephemeral)
- **Where:** Copilot CLI session state
- **Survives:** Current session only
- **Stores:** Todo tracking, batch work, plans
- **Accessed via:** Built-in session tools

## When to Read Memory (Session Start)

Every session begins with three commands:

```bash
python cli.py status        # Memory stats, recent conversations
python cli.py pref list     # All learned preferences
python cli.py insight list  # Active decisions, patterns, goals
```

Use this data to:
- Personalize tone and approach
- Reference recent work
- Maintain continuity across sessions
- Know the user's environment and tools

## When to Write Memory (Session End)

Log to memory when any of these occurred:

| Trigger | Command |
|---------|---------|
| Decision made | `insight add -t decision --content "..."` |
| New preference discovered | `pref add -c <cat> -k <key> -v <value>` |
| Pattern observed | `insight add -t pattern --content "..."` |
| Goal stated | `insight add -t goal --content "..."` |
| Important context | `insight add -t context --content "..."` |
| Meaningful work completed | `start` → `msg` → `end` with summary |

### What NOT to log
- Quick questions with no lasting value
- Routine file reads or searches
- Information already captured previously

## Confidence Scores

When storing preferences, indicate certainty:

| Score | Meaning | Example |
|-------|---------|---------|
| 1.0 | Explicitly stated | "My environment is Windows" |
| 0.9 | Strongly demonstrated | User consistently prefers direct tone |
| 0.8 | Observed pattern | Prefers building over buying |
| 0.5 | Default / inferred | First mention, needs confirmation |

## Memory Maintenance

Periodically check for:
- **Stale insights** — Archive with `insight archive --id <id>`
- **Superseded insights** — Replace with `insight supersede --id <id> --content "updated version"`
- **Duplicate insights** — Consolidate into one
- **Preference drift** — Check `pref history` for outdated values

## Preference Categories

Organize preferences into logical groups:

| Category | Examples |
|----------|---------|
| **tech** | Languages, frameworks, tools, environment |
| **workflow** | Automation prefs, delegation style, meeting patterns |
| **communication** | Tone, teaching mode, decision style |
| **work** | Stakeholders, project details, org context |

## Conversation Logging Pattern

For meaningful sessions:

```bash
# Start with descriptive title
python cli.py start -t "Built authentication module with JWT"

# Log key exchanges (not every message)
python cli.py msg <id> user "Need stateless auth for the API"
python cli.py msg <id> assistant "Implemented JWT with bcrypt in src/auth/"

# End with clear summary
python cli.py end <id> -s "Created JWT auth module. Chose JWT over sessions for stateless design. bcrypt for password hashing."
```
