# TOOLS.md — Tool Overview

> What tools are available and how to use them. Update as your toolkit evolves.

## Tool Selection Priority

1. **Dedicated MCP tool** if one exists (GitHub, Azure, Planner, etc.)
2. **Memory CLI** for persistent context operations
3. **Browser automation** for web interactions
4. **PowerShell/Bash** for system operations
5. **Python** for data processing and custom tooling
6. **Web search** for external information

## Python Conventions

- Use your installed Python version
- SQLite for local data storage (zero external dependencies)
- Explain code patterns when writing — teaching opportunity
- Prefer simple, readable code over clever abstractions
- Add comments only when the *why* isn't obvious

## File Organization

- **Workspace root:** [Your workspace path]
- **Memory:** [workspace]/memory/
- **Instructions:** [workspace]/instructions/
- **Session state:** ~/.copilot/session-state/
