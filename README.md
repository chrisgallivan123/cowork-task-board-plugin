# Task Board Plugin

A personal task list for Cowork with a live sidebar board. Create and action tasks via chat or directly from the board.

## What it does

- **Chat-based task management** — create, update, tag, and close tasks conversationally
- **Live sidebar board** — a persistent artifact that auto-refreshes every 10 seconds
- **Tag system** — assign emoji icons to tags (e.g. 🔥 for `urgent`, ⭐ for a person's name)
- **Local persistence** — tasks stored in `~/.claude-tasks/` on your machine, survive across sessions

## Components

| Component | Type | Purpose |
|-----------|------|---------|
| task-manager | Skill | Manage tasks via chat |
| task-board-setup | Skill | Create or restore the live sidebar board |
| tasks | MCP Server | Local Python server that stores and serves tasks |

## Setup

### Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/) must be installed (`brew install uv` on macOS)
- Python 3.9+

The tasks MCP server uses `uv run` to handle dependencies automatically. On first launch it will download `mcp>=1.0.0` — this takes a few seconds.

### First run

1. Install the plugin in Cowork
2. Restart Cowork (or reload MCP servers)
3. Ask Claude: **"set up my task board"** to create the live sidebar board
4. Start adding tasks: **"add a task to follow up with [name]"**

## Usage

**Creating tasks via chat:**
> "Add a task to send the Q2 report to Sarah — tag it urgent"
> "Create a task for the demo prep meeting"

**Managing tasks:**
> "What's on my list?"
> "Mark task 3 in progress"
> "Close task 1"
> "Delete task 5"

**Tags and icons:**
> "Set the icon for tag 'sarah' to a star"
> "What tags do I have?"

**Board:**
> "Open my task board"
> "Set up my task board"

## Storage

Tasks are stored in `~/.claude-tasks/tasks.json`. Deletes are soft (recoverable via `include_deleted=true`). Config (tag icons) in `~/.claude-tasks/config.json`.

## Default tag icons

| Tag | Icon |
|-----|------|
| urgent | 🔥 |
| todo | 📋 |
| followup | 📞 |
| meeting | 🗓️ |
| demo | 🎯 |
| review | 👀 |
| blocked | 🚧 |
| waiting | ⏳ |

Custom tags get 🏷 by default until you assign an icon.
