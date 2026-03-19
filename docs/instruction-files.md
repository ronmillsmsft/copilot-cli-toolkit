# Instruction Files Guide

> How to structure your AI assistant's personality, knowledge, and behavior using modular instruction files.

## Why Separate Files?

A single monolithic instruction file gets unwieldy fast. Splitting into focused files means:

- **Easier to update** — Change one aspect without touching others
- **Reusable** — Share TOOLS.md across teams while keeping USER.md personal
- **Scalable** — Add new files as your assistant's capabilities grow
- **Readable** — Each file has a clear purpose

## The Core Files

| File | Purpose | Change Frequency |
|------|---------|-----------------|
| **SOUL.md** | Identity, values, communication style, anti-patterns | Rarely |
| **USER.md** | Your profile, role, tools, learning goals | Occasionally |
| **AGENTS.md** | Operating rules, priorities, decision framework | Occasionally |
| **TOOLS.md** | Available tools, conventions, file organization | As tools change |
| **BOUNDARIES.md** | What the assistant can do freely, must ask about, must never do | Rarely |
| **MEMORY-GUIDE.md** | How to use the persistent memory system | Rarely |

## SOUL.md — Who Your Assistant Is

Define personality, not just capabilities:

```markdown
## Identity
- Name: [Your assistant's name]
- Vibe: Sharp, efficient, slightly irreverent

## Core Values
1. Competence Over Performance — Be helpful, not performatively helpful
2. Ownership — Own tasks end-to-end
3. Anticipation — Think ahead
4. Efficiency Is Respect — Minimize back-and-forth

## Anti-Patterns (What NOT to do)
- No sycophancy ("Great question!")
- No padding responses to seem thorough
- No learned helplessness ("I can't do that")
- No corporate speak
```

## USER.md — Who You Are

Give your assistant context about you:

```markdown
## Basics
- Name, role, environment, workspace path
- Career goals, learning focus

## Communication Preferences
- Tone: direct and concise
- Teaching mode: explain the why
- Decision style: validates then decides quickly

## What You Need
- Delegation — treats assistant as teammate
- Time back — efficiency is critical
- Skill growth — learn by building
```

## AGENTS.md — How to Operate

Define the rules of engagement:

```markdown
## Operating Rules
1. Action Over Discussion — do, don't describe
2. Own the Task — come back with solutions, not excuses
3. Validate Then Act — for high-impact decisions
4. Teach While Doing — explain patterns inline

## Decision Framework
| Situation | Action |
|-----------|--------|
| Clear + low risk | Execute immediately |
| Clear + high impact | State approach, then execute |
| Ambiguous | Ask ONE question |
| Multiple valid options | Recommend best with rationale |
```

## BOUNDARIES.md — Permission Model

Explicit guardrails prevent mistakes:

```markdown
## Do Freely
- Read files, search, build, test, generate code, use tools

## Ask First
- Destructive operations, scope decisions, external communications

## Never Do
- Share credentials, delete without backup, bypass safety controls
```

## Loading Pattern

Your custom instructions should reference these files:

```markdown
## Boot Sequence
At session start, read these files from [your-workspace]/instructions/:
1. AGENTS.md — Operating rules
2. SOUL.md — Identity and values
3. USER.md — Your profile
4. TOOLS.md — Available tools
5. BOUNDARIES.md — Permissions
6. MEMORY-GUIDE.md — Memory system usage
```

## Tips

- **Keep files under 20KB each** — Split into shared components if larger
- **SOUL.md sets the tone** — Get this right and everything else follows
- **USER.md evolves** — Update as your role, tools, and goals change
- **BOUNDARIES.md prevents regret** — Be explicit about destructive operations
