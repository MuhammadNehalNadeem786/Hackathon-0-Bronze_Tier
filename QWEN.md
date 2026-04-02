# Autonomous FTEs Project Context

## Project Overview

This directory contains a **Personal AI Employee Hackathon** project focused on building **Autonomous FTEs (Full-Time Equivalents)** — AI agents that work 24/7 to manage personal and business affairs autonomously.

**Core Concept:** A local-first, agent-driven system where Claude Code acts as the reasoning engine, Obsidian serves as the dashboard/memory, and lightweight Python "Watcher" scripts monitor external systems (Gmail, WhatsApp, bank accounts, social media) to trigger autonomous actions.

**Key Innovation:** The "Monday Morning CEO Briefing" — an AI that proactively audits transactions, tasks, and communications to provide actionable business insights without being prompted.

## Directory Structure

```
Autonomous FTEs/
├── Personal AI Employee Hackathon 0_ Building Autonomous FTEs in 2026.md  # Main blueprint (1201 lines)
├── skills-lock.json          # Qwen skills configuration
├── QWEN.md                   # This context file
└── .qwen/
    └── skills/
        └── browsing-with-playwright/  # Browser automation skill
            ├── SKILL.md
            ├── references/
            │   └── playwright-tools.md
            └── scripts/
                ├── mcp-client.py
                ├── start-server.sh
                ├── stop-server.sh
                └── verify.py
```

## Key Files

| File | Purpose |
|------|---------|
| `Personal AI Employee Hackathon 0_...md` | Comprehensive architectural blueprint with implementation guides, code templates, and tiered achievement levels (Bronze/Silver/Gold/Platinum) |
| `skills-lock.json` | Tracks installed Qwen skills (currently: browsing-with-playwright) |
| `.qwen/skills/browsing-with-playwright/` | Browser automation via Playwright MCP for web interactions |

## Architecture Components

### 1. **The Brain** — Claude Code
- Primary reasoning engine
- Uses "Ralph Wiggum" Stop hook pattern for persistent multi-step task completion
- Reads/writes to Obsidian vault for state management

### 2. **The Memory/GUI** — Obsidian
- Local Markdown-based dashboard
- Key folders: `/Inbox`, `/Needs_Action`, `/Done`, `/Pending_Approval`
- Key files: `Dashboard.md`, `Company_Handbook.md`, `Business_Goals.md`

### 3. **The Senses** — Watcher Scripts (Python)
- **Gmail Watcher:** Monitors unread/important emails
- **WhatsApp Watcher:** Uses Playwright to monitor WhatsApp Web for keywords
- **File System Watcher:** Monitors drop folders using `watchdog`
- **Finance Watcher:** Tracks bank transactions

### 4. **The Hands** — MCP (Model Context Protocol) Servers
- `filesystem`: Built-in file operations
- `email-mcp`: Send/draft/search emails
- `browser-mcp`: Navigate websites, fill forms, click buttons
- `calendar-mcp`: Schedule events
- Custom servers for domain-specific actions

## Development Tiers

| Tier | Time | Deliverables |
|------|------|--------------|
| **Bronze** | 8-12 hrs | Obsidian vault, 1 Watcher, Claude integration, basic folder structure |
| **Silver** | 20-30 hrs | 2+ Watchers, LinkedIn posting, Plan.md generation, 1 MCP server, HITL workflow |
| **Gold** | 40+ hrs | Full integration, Odoo accounting, social media (FB/IG/Twitter), weekly briefings, Ralph Wiggum loop |
| **Platinum** | 60+ hrs | Cloud deployment (24/7), Cloud/Local split, vault sync, production-ready |

## Building & Running

### Prerequisites
- **Claude Code:** Active subscription (Pro or free tier)
- **Obsidian:** v1.10.6+
- **Python:** 3.13+
- **Node.js:** v24+ LTS
- **GitHub Desktop:** For version control

### Setup Commands

```bash
# Verify Claude Code
claude --version

# Start Playwright MCP server (for browser automation)
bash .qwen/skills/browsing-with-playwright/scripts/start-server.sh

# Verify Playwright server
python3 .qwen/skills/browsing-with-playwright/scripts/verify.py

# Stop Playwright server when done
bash .qwen/skills/browsing-with-playwright/scripts/stop-server.sh
```

### Watcher Pattern Template

```python
from base_watcher import BaseWatcher

class CustomWatcher(BaseWatcher):
    def check_for_updates(self) -> list:
        # Return list of new items to process
        pass
    
    def create_action_file(self, item) -> Path:
        # Create .md file in Needs_Action folder
        pass
```

### Ralph Wiggum Loop (Persistence Pattern)

```bash
# Start autonomous loop
/ralph-loop "Process all files in /Needs_Action, move to /Done when complete" \
  --completion-promise "TASK_COMPLETE" \
  --max-iterations 10
```

## Human-in-the-Loop Pattern

For sensitive actions (payments, approvals), Claude writes approval request files instead of acting directly:

```markdown
---
type: approval_request
action: payment
amount: 500.00
status: pending
---

## To Approve
Move this file to /Approved folder.

## To Reject
Move this file to /Rejected folder.
```

## Development Conventions

### Coding Style
- Python scripts follow the `BaseWatcher` abstract class pattern
- All AI functionality should be implemented as [Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- Markdown files use YAML frontmatter for metadata

### Testing Practices
- Use `verify.py` scripts to validate MCP server connectivity
- Test Watchers individually before integrating
- Validate Ralph Wiggum loop completion conditions

### Security Rules
- Secrets never sync (.env, tokens, WhatsApp sessions, banking credentials)
- Cloud/Local split: Cloud drafts, Local approves/executes
- Single-writer rule for `Dashboard.md` (Local only)

## Usage Guidelines

### When Working in This Project

1. **Read the Hackathon document first** — It contains detailed implementation guides and code templates
2. **Use the Playwright skill** for any web automation tasks (form filling, scraping, UI testing)
3. **Follow the Watcher pattern** when creating new monitoring scripts
4. **Implement HITL** for any sensitive actions (payments, approvals, sends)
5. **Test incrementally** — Start with Bronze tier, then add complexity

### Common Workflows

| Task | Approach |
|------|----------|
| Add new input source | Create a new `*_watcher.py` following `BaseWatcher` pattern |
| Add new action type | Create or extend an MCP server |
| Automate multi-step task | Use Ralph Wiggum loop with completion promise |
| Add approval workflow | Write approval request file, watch `/Approved` folder |

## Meeting Information

**Weekly Research & Showcase:** Wednesdays at 10:00 PM PKT
- **Zoom:** [Link in hackathon doc](https://us06web.zoom.us/j/87188707642?pwd=a9XloCsinvn1JzICbPc2YGUvWTbOTr.1)
- **YouTube:** [@panaversity](https://www.youtube.com/@panaversity)

## Related Documentation

- [Playwright Tools Reference](.qwen/skills/browsing-with-playwright/references/playwright-tools.md)
- [Ralph Wiggum Pattern](https://github.com/anthropics/claude-code/tree/main/.claude/plugins/ralph-wiggum)
- [Agent Skills Documentation](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [MCP Servers](https://github.com/AlanOgic/mcp-odoo-adv)
