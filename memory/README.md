# Agent Memory System

> Persistent memory for your AI assistant. Remembers preferences, decisions, conversations, and patterns across sessions.

## What It Does

The memory system gives your AI assistant a SQLite-backed brain:

- **Preferences** — Learned key-value pairs organized by category (tech, workflow, communication, etc.)
- **Insights** — Decisions, patterns, goals, and context that persist across sessions
- **Conversations** — Logged interactions with searchable full-text index
- **Search** — FTS5-powered search across all memory

## Quick Start

```bash
# Initialize the database (creates memory.db)
python cli.py init

# Check status
python cli.py status

# Add a preference
python cli.py pref add -c tech -k language -v "Python 3.12" --confidence 1.0

# Add an insight
python cli.py insight add -t decision --content "Using SQLite for all local storage. Zero dependencies, portable, good enough for single-user."

# Log a conversation
python cli.py log "How do I set up meeting prep?" -a "Created meeting_prep.py with ADO integration" -t "Meeting prep setup" -s "Built meeting prep pipeline"

# Search everything
python cli.py search "meeting prep"

# List preferences
python cli.py pref list
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `init` | Initialize the database |
| `status` | Show memory summary (counts, recent conversations) |
| `pref add -c <cat> -k <key> -v <value>` | Add/update a preference |
| `pref list` | List all preferences |
| `pref history` | Show preference change history |
| `insight add -t <type> --content <text>` | Add an insight (decision/pattern/goal/context) |
| `insight list` | List active insights |
| `insight archive --id <id>` | Archive a stale insight |
| `insight supersede --id <id> --content <new>` | Replace an insight with updated version |
| `log <message>` | Log a quick interaction |
| `start -t <title>` | Start a multi-message conversation |
| `msg <id> <role> <content>` | Add message to conversation |
| `end <id> -s <summary>` | End a conversation |
| `search <query>` | Full-text search across all memory |
| `export` | Export all memory as JSON |

## How Your Assistant Uses It

Add this to your custom instructions boot sequence:

```markdown
At session start, run:
1. python cli.py status        # How much memory exists
2. python cli.py pref list     # All learned preferences
3. python cli.py insight list  # Active decisions and patterns
```

At session end, log meaningful work:

```bash
# Log conversation
python cli.py start -t "Built new API endpoint"
python cli.py msg <id> user "Need a REST endpoint for user auth"
python cli.py msg <id> assistant "Created JWT-based auth in src/auth/"
python cli.py end <id> -s "Built JWT auth endpoint with bcrypt password hashing"

# Save new preferences discovered
python cli.py pref add -c tech -k auth_pattern -v "JWT with bcrypt" --confidence 0.9

# Save decisions
python cli.py insight add -t decision --content "Using JWT over session-based auth for stateless API design"
```

## Database Schema

All data lives in `memory.db` (SQLite):

- `conversations` — id, title, started_at, ended_at, summary, tags
- `messages` — conversation_id, role, content, timestamp (with FTS5 index)
- `preferences` — category, key, value, confidence, learned_at
- `preference_history` — tracks every change to preferences
- `insights` — type, content, active, superseded_by (with FTS5 index)

## Architecture

```
memory/
├── cli.py          # CLI interface (all commands)
├── setup_db.py     # Schema initialization
├── memory.db       # Created on first run (gitignored)
└── src/
    ├── __init__.py
    ├── db.py           # Connection management, helpers
    ├── conversations.py # Conversation CRUD
    ├── preferences.py   # Preferences + insights CRUD
    └── search.py        # FTS5 search + context summary
```
