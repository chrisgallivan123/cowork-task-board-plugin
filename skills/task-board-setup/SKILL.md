---
name: task-board-setup
description: >
  Use this skill when the user wants to set up or open their live task board, asks to
  "open the task board", "show me the board", "create the task board", "set up my task board",
  "I want a sidebar board for my tasks", or wants a persistent visual view of their tasks.
  Also use when the task board artifact is missing or needs to be recreated.
metadata:
  version: "0.1.0"
---

## Task Board Setup

Create a persistent Cowork artifact that shows the user's tasks in real time. The board:
- Loads tasks on open via the tasks MCP
- Auto-refreshes every 10 seconds (silent, no loading flash)
- Supports filtering by status (All / Pending / In Progress / Completed)
- Allows actioning tasks inline: Start, Done, Reopen, Delete
- Includes a "+ New Task" form with tag support

### Steps

1. Read the HTML template from `references/task-board.html` in this skill directory.
2. Call `mcp__cowork__create_artifact` (or `mcp__cowork__update_artifact` if it already exists) with:
   - `id`: `"task-board"`
   - `html_path`: path to the written HTML file
   - `description`: "Live task board — auto-refreshes from the tasks MCP every 10 seconds"
   - `mcp_tools`: `["mcp__tasks__task_list", "mcp__tasks__task_create", "mcp__tasks__task_update", "mcp__tasks__task_delete", "mcp__tasks__tag_list"]`
3. Confirm with a short message that the board is live.

### Important: MCP Response Format

The `callMcpTool` bridge in artifacts wraps results as:
```json
{ "structuredContent": { ... }, "content": [{ "type": "text", "text": "..." }], "isError": false }
```

Always read from `raw.structuredContent` first. The `parse()` helper in the HTML template handles this.
