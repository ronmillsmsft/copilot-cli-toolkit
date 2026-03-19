# Quick Start Guide

> From zero to a persistent AI assistant in 5 minutes.

## Prerequisites

- [GitHub Copilot CLI](https://docs.github.com/en/copilot/github-copilot-in-the-cli) installed and authenticated
- Python 3.10+ installed
- A terminal (Windows Terminal, iTerm2, etc.)

## Step 1: Get the Toolkit

```bash
git clone https://github.com/ronmillsmsft/copilot-cli-toolkit.git
cd copilot-cli-toolkit
```

## Step 2: Set Up Custom Instructions

Custom instructions tell Copilot CLI *who it is* and *how to behave* every session.

```bash
# Copy the starter instruction to your Copilot CLI config
cp starter/copilot-instructions.md <your-copilot-instructions-location>
```

Edit `copilot-instructions.md` and personalize:
- **Your name** — so it knows who it's talking to
- **Your role** — PM, engineer, designer, etc.
- **Your tools** — what you use daily
- **Your preferences** — tone, teaching style, decision approach

This single file is enough for Tier 1. Your assistant will now have consistent personality and behavior.

## Step 3: Add Memory (Tier 2)

Memory is what makes this transformative. Your assistant remembers across sessions.

```bash
cd memory
python cli.py status
```

First run creates the SQLite database. Then add your boot sequence to the custom instructions:

```markdown
## Boot Sequence
At session start, run:
- python cli.py status
- python cli.py pref list
- python cli.py insight list
```

Now your assistant loads your preferences, past decisions, and recent context every time it starts.

## Step 4: Start a Session

```bash
copilot
```

Your assistant will:
1. Load the custom instructions
2. Run the boot sequence (read memory)
3. Greet you with relevant context
4. Ask what you're working on

## Step 5: End a Session

When you're done, tell your assistant to close out. It will automatically:
- Log the conversation summary to memory
- Save any new preferences discovered
- Record decisions and insights for next time

## What to Do Next

- **Customize instruction files** — See `instructions/` for the full set (SOUL, USER, AGENTS, TOOLS, BOUNDARIES)
- **Teach it your preferences** — Just work naturally; it learns from context
- **Add workflows** — See Tier 3 for meeting prep, standup scans, and more
- **Read the memory guide** — See `docs/memory-guide.md` for the full system

## Common Questions

**Q: Does this require any cloud services or API keys?**
No. Everything runs locally with Python and SQLite. Zero external dependencies.

**Q: Will this work on Mac/Linux?**
Yes. Python and SQLite are cross-platform. Some workflow scripts reference Windows paths that you'd need to adjust.

**Q: How is this different from just using Copilot CLI?**
Copilot CLI is stateless — it forgets everything between sessions. This toolkit adds persistent memory, structured instructions, and automation. Your assistant gets better over time instead of starting from scratch.

**Q: Can I use this with other AI assistants?**
The memory system and instruction patterns are portable. The memory CLI is just Python/SQLite. The instruction files are markdown. Adapt them to any assistant that supports custom instructions.
