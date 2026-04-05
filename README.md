# AI Employee - Bronze Tier

A Personal AI Employee system built with **Qwen Code** and Obsidian. This Bronze Tier implementation provides the foundational layer for autonomous task processing.

## 📋 Overview

The AI Employee is an autonomous agent system that:
- **Monitors** inputs (files, emails, messages) via Watcher scripts
- **Processes** tasks using **Qwen Code** as the reasoning engine
- **Acts** through MCP servers and human-in-the-loop approvals
- **Documents** everything in an Obsidian vault

### Bronze Tier Features

- ✅ Obsidian vault with Dashboard.md and Company_Handbook.md
- ✅ File System Watcher (monitors drop folder for new files)
- ✅ Orchestrator (triggers Qwen Code for processing)
- ✅ Basic folder structure: `/Inbox`, `/Needs_Action`, `/Done`
- ✅ Activity logging and audit trail

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL INPUTS                          │
│                    (Files, Emails, etc.)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    PERCEPTION LAYER                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Filesystem Watcher (Python)                        │   │
│  │  - Monitors /Drop folder                            │   │
│  │  - Creates action files in /Needs_Action            │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    OBSIDIAN VAULT                           │
│  /Inbox          → Raw incoming files                       │
│  /Needs_Action   → Items requiring processing               │
│  /Plans          → Qwen Code's execution plans              │
│  /Done           → Completed tasks                          │
│  /Pending_Approval → Awaiting human decision                │
│  /Approved       → Approved actions ready to execute        │
│  /Logs           → Activity logs                            │
│  Dashboard.md    → Real-time status                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    REASONING LAYER                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Qwen Code                                          │   │
│  │  - Reads action files                               │   │
│  │  - Creates plans                                    │   │
│  │  - Executes actions (with approval)                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
bronze_tier/
├── watchers/
│   ├── base_watcher.py         # Abstract base class for all watchers
│   └── filesystem_watcher.py   # File system monitoring implementation
├── orchestrator.py             # Master process for folder watching
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variable template
└── README.md                  # This file

AI_Employee_Vault/
├── Dashboard.md               # Real-time status dashboard
├── Company_Handbook.md        # Rules of engagement
├── Business_Goals.md          # Objectives and metrics
├── Inbox/                     # Raw incoming files
├── Needs_Action/              # Items requiring processing
├── Done/                      # Completed tasks
├── Plans/                     # Qwen Code's execution plans
├── Pending_Approval/          # Awaiting human decision
├── Approved/                  # Approved actions
├── Rejected/                  # Rejected actions
├── Logs/                      # Activity logs
├── Accounting/                # Financial records
├── Briefings/                 # CEO briefings
└── Drop/                      # File drop folder (monitored)
```

## 🚀 Quick Start

### Prerequisites

1. **Python 3.13+** - [Download](https://www.python.org/downloads/)
2. **Qwen Code** - [Download](https://https://qwen.ai/qwencode)
3. **Obsidian** - [Download](https://obsidian.md/download) (optional GUI)

### Installation

1. **Clone or download this repository**

2. **Install Python dependencies**
   ```bash
   cd bronze_tier
   pip install -r requirements.txt
   ```

3. **Setup environment variables**
   ```bash
   cd bronze_tier
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Open the Obsidian vault** (optional)
   - Launch Obsidian
   - Click "Open folder as vault"
   - Select the `AI_Employee_Vault` folder

### Running the System

**Terminal 1: Start the Filesystem Watcher**
```bash
cd "S:/Personal AI Employee/Autonomous FTEs/bronze_tier"
python watchers/filesystem_watcher.py --vault "S:/Personal AI Employee/Autonomous FTEs/AI_Employee_Vault"
```

**Terminal 2: Start the Orchestrator (with Qwen Code)**
```bash
cd "S:/Personal AI Employee/Autonomous FTEs/bronze_tier"
python orchestrator.py --vault "S:/Personal AI Employee/Autonomous FTEs/AI_Employee_Vault"
python orchestrator.py --vault "S:/Personal AI Employee/Autonomous FTEs/AI_Employee_Vault" --watch
```

### Testing the System

1. **Drop a file** into `AI_Employee_Vault/Drop/`
2. **Watch the logs** - The Filesystem Watcher should detect it
3. **Check Needs_Action** - An action file should be created
4. **Review in Obsidian** - Open Dashboard.md to see status

### Quick Demo

Run the demo script to see everything in action:

```bash
cd bronze_tier
python demo.py
```

This will:
1. Create a test file in `/Drop`
2. Detect it with the Filesystem Watcher
3. Create an action file in `/Needs_Action`
4. Process it with Qwen Code
5. Create a plan in `/Plans`

## 📖 Usage Guide

### How It Works

1. **File Drop**: Place any file in the `/Drop` folder
2. **Detection**: Filesystem Watcher detects the new file within 30 seconds
3. **Action File Creation**: Watcher creates a `.md` action file in `/Needs_Action`
4. **Processing**: Orchestrator triggers Qwen Code to process the action file
5. **Execution**: Qwen Code reads, plans, and executes (with approvals as needed)
6. **Completion**: File moves to `/Done`, Dashboard updates

### Folder Workflow

```
/Drop → [Watcher detects] → /Needs_Action → [Qwen Code processes] → /Done
                                      ↓
                              /Pending_Approval → [Human approves] → /Approved → [Execute] → /Done
```

### Approval Workflow

For actions requiring human approval:

1. Qwen Code creates a file in `/Pending_Approval/`
2. Review the file in Obsidian
3. **To Approve**: Move file to `/Approved/`
4. **To Reject**: Move file to `/Rejected/`
5. Orchestrator executes approved actions

## ⚙️ Configuration

### Watcher Options

| Option | Default | Description |
|--------|---------|-------------|
| `--vault`, `-v` | (required) | Path to Obsidian vault |
| `--drop-folder`, `-d` | vault/Drop | Folder to monitor |
| `--interval`, `-i` | 30 | Check interval in seconds |

### Orchestrator Options

| Option | Default | Description |
|--------|---------|-------------|
| `--vault`, `-v` | (required) | Path to Obsidian vault |
| `--interval`, `-i` | 60 | Check interval in seconds |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VAULT_PATH` | - | Path to Obsidian vault |
| `WATCHER_CHECK_INTERVAL` | 30 | Watcher check interval (seconds) |
| `ORCHESTRATOR_CHECK_INTERVAL` | 60 | Orchestrator check interval (seconds) |
| `DRY_RUN` | true | Enable dry-run mode |
| `LOG_LEVEL` | INFO | Logging level |

## 📊 Monitoring

### Logs

All activity is logged to:
- `AI_Employee_Vault/Logs/watcher_YYYY-MM-DD.log`
- `AI_Employee_Vault/Logs/orchestrator_YYYY-MM-DD.log`
- `AI_Employee_Vault/Logs/YYYY-MM-DD.json` (structured activity log)

### Dashboard

Open `Dashboard.md` in Obsidian to see:
- Pending actions count
- Tasks completed today
- Pending approvals
- Recent activity
- System status

## 🔧 Troubleshooting

### Qwen Code not processing
Qwen Code is already running in this environment. If you see processing issues:
1. Check that `--ai-agent qwen` is specified when running the orchestrator
2. Review the orchestrator log file for errors
3. Ensure action files have `.md` extension

### Watcher not detecting files
1. Check the watcher log file for errors
2. Verify the vault path is correct
3. Ensure the `/Drop` folder exists
4. Check file permissions

### Orchestrator not processing
1. Verify Qwen Code is available (check logs for "Qwen Code: Available")
2. Check the orchestrator log file for errors
3. Ensure action files have `.md` extension
4. Run with `--ai-agent qwen` flag

## 📈 Next Steps (Silver Tier)

To upgrade to Silver Tier, add:
- [ ] Gmail Watcher (email monitoring)
- [ ] WhatsApp Watcher (message monitoring)
- [ ] MCP server for sending emails
- [ ] Human-in-the-loop approval workflow
- [ ] Scheduled tasks (cron/Task Scheduler)

## 🔒 Security Notes

- **Never commit** `.env` files to version control
- **Review all approvals** before moving to `/Approved`
- **Regularly audit** logs in `/Logs`
- **Keep credentials** in secure storage (keychain, etc.)

## 📚 Documentation

- [Company Handbook](AI_Employee_Vault/Company_Handbook.md) - Rules of engagement
- [Business Goals](AI_Employee_Vault/Business_Goals.md) - Objectives and metrics
- [Dashboard](AI_Employee_Vault/Dashboard.md) - Real-time status

## 🤝 Contributing

This is part of the Personal AI Employee Hackathon 0. Share your improvements!

## 📄 License

MIT License - See LICENSE file for details.
