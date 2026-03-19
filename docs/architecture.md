# Architecture

> Visual overview of the Copilot CLI Toolkit — core platform + extensible role modules.

## System Architecture

```mermaid
graph TB
    subgraph CORE["🔧 COPILOT CLI CORE PLATFORM"]
        direction TB
        
        subgraph BOOT["Boot Sequence"]
            CI[/"📄 Custom Instructions<br/>(copilot-instructions.md)"/]
            IF["📁 Instruction Files<br/>SOUL · USER · AGENTS<br/>TOOLS · BOUNDARIES"]
        end

        subgraph MEMORY["Persistent Memory Layer"]
            MDB[("🧠 memory.db<br/>SQLite + FTS5")]
            PREFS["⚙️ Preferences<br/>Category · Key · Value<br/>Confidence Scoring"]
            INSIGHTS["💡 Insights<br/>Decisions · Patterns<br/>Goals · Context"]
            CONVOS["💬 Conversations<br/>Logged Sessions<br/>Full-Text Search"]
        end

        subgraph CLI_TOOLS["CLI & Tools"]
            MCLI["🔧 Memory CLI<br/>status · pref · insight<br/>search · log · export"]
            SHELL["⚡ PowerShell / Bash"]
            PYTHON["🐍 Python Runtime"]
            SQLITE[("💾 SQLite<br/>Zero-Dependency<br/>Persistence")]
        end

        CI --> IF
        IF --> MDB
        MDB --> PREFS
        MDB --> INSIGHTS
        MDB --> CONVOS
        MCLI --> MDB
        PYTHON --> SQLITE
    end

    subgraph MCP["🔌 MCP INTEGRATIONS"]
        direction LR
        GH["GitHub"]
        ADO["Azure DevOps"]
        PLAN["Planner"]
        NOTE["OneNote"]
        PBI["Power BI"]
        AZ["Azure"]
        PW["Playwright"]
        WIQ["WorkIQ"]
    end

    subgraph ROLES["📋 ROLE-SPECIFIC MODULES"]
        direction TB
        
        subgraph PM_ROLE["Program Manager"]
            MP["📊 Meeting Prep"]
            SP["📋 Standup Scan"]
            AT["✅ Action Tracker"]
            DO["🔍 Daily Ops"]
        end

        subgraph ENG_ROLE["Engineer"]
            CR["🔎 Code Review"]
            TD["🧪 Test Driver"]
            DP["🚀 Deploy Pipeline"]
            DB["🐛 Debug Assistant"]
        end

        subgraph ANALYST_ROLE["Analyst"]
            DQ["📈 Data Queries"]
            RG["📊 Report Generator"]
            DV["📉 Data Validation"]
            ET["🔄 ETL Monitor"]
        end

        subgraph CUSTOM["Your Role"]
            C1["🔧 Module 1"]
            C2["🔧 Module 2"]
            C3["🔧 Module 3"]
        end
    end

    CORE --> MCP
    CORE --> ROLES
    MCP --> ROLES

    style CORE fill:#1a1a2e,stroke:#00d4ff,stroke-width:3px,color:#e0e0e0
    style BOOT fill:#16213e,stroke:#0f3460,stroke-width:2px,color:#e0e0e0
    style MEMORY fill:#16213e,stroke:#0f3460,stroke-width:2px,color:#e0e0e0
    style CLI_TOOLS fill:#16213e,stroke:#0f3460,stroke-width:2px,color:#e0e0e0
    style MCP fill:#0a3d62,stroke:#00d4ff,stroke-width:2px,color:#e0e0e0
    style ROLES fill:#1e1e1e,stroke:#4ecdc4,stroke-width:2px,color:#e0e0e0,stroke-dasharray: 5 5
    style PM_ROLE fill:#2d3436,stroke:#00b894,stroke-width:2px,color:#e0e0e0
    style ENG_ROLE fill:#2d3436,stroke:#6c5ce7,stroke-width:2px,color:#e0e0e0
    style ANALYST_ROLE fill:#2d3436,stroke:#fdcb6e,stroke-width:2px,color:#e0e0e0
    style CUSTOM fill:#2d3436,stroke:#e17055,stroke-width:2px,color:#e0e0e0,stroke-dasharray: 5 5
```

## How It Fits Together

The **Core Platform** (solid border) is what every user gets — persistent memory, structured instructions, and the CLI tools to tie it all together. This is Tier 1 and Tier 2 of the toolkit.

**MCP Integrations** plug into the core to give your assistant access to external systems. Pick the ones relevant to your work.

**Role-Specific Modules** (dashed border) are where it gets personal. The PM module is battle-tested. Engineer, Analyst, and custom roles are templates showing how to extend the platform for any workflow.

## Data Flow

```mermaid
sequenceDiagram
    participant U as You
    participant C as Copilot CLI
    participant I as Instruction Files
    participant M as Memory System
    participant T as Tools & MCPs
    
    Note over U,T: SESSION START
    U->>C: Start session
    C->>I: Load SOUL, USER, AGENTS, TOOLS, BOUNDARIES
    C->>M: python cli.py status
    M-->>C: 88 conversations, 115 prefs, 280 insights
    C->>M: python cli.py pref list
    M-->>C: All learned preferences
    C->>M: python cli.py insight list
    M-->>C: Active decisions & patterns
    C-->>U: Personalized greeting with context

    Note over U,T: WORKING SESSION
    U->>C: "Run the standup prep scan"
    C->>T: Query ADO for work items
    T-->>C: 131 items returned
    C->>T: Analyze: P1s, stale, state changes
    C-->>U: Results + cache for dashboard

    Note over U,T: SESSION END
    U->>C: "Close out"
    C->>M: Log conversation summary
    C->>M: Save new preferences
    C->>M: Save new insights
    C-->>U: Memory updated ✅
```

## Tier Map

```mermaid
graph LR
    subgraph T1["🟢 Tier 1: Start Here"]
        A1["Custom Instructions"]
        A2["Quick Start Guide"]
    end
    
    subgraph T2["🔵 Tier 2: Foundation"]
        B1["Memory System"]
        B2["Instruction Files"]
        B3["Memory Guide"]
    end
    
    subgraph T3["🟡 Tier 3: Workflows"]
        C1["Meeting Prep"]
        C2["Standup Scan"]
        C3["Action Tracker"]
        C4["Daily Ops"]
    end
    
    subgraph T4["🔴 Tier 4: Advanced"]
        D1["Agent Engine"]
        D2["Ops Dashboard"]
        D3["MCP Configs"]
    end

    T1 --> T2 --> T3 --> T4

    style T1 fill:#00b894,stroke:#00b894,color:#fff
    style T2 fill:#0984e3,stroke:#0984e3,color:#fff
    style T3 fill:#fdcb6e,stroke:#fdcb6e,color:#333
    style T4 fill:#d63031,stroke:#d63031,color:#fff
```
