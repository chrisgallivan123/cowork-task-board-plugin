---
name: task-manager
description: >
  Use this skill when the user wants to manage their personal task list via chat.
  Triggers include: "add a task", "create a task", "what's on my list", "show my tasks",
  "mark task done", "close task", "mark in progress", "tag it urgent", "set icon for tag",
  "show open tasks", "complete task", "delete task", or any request to create, update,
  list, or action tasks. Also use when the user asks to tag tasks or assign emoji to tags.
metadata:
  version: "0.1.0"
---

## Task Management via Chat

The tasks MCP server exposes six tools. Use them directly in response to user requests — no need to narrate what you're doing, just act and confirm briefly.

### Tools

**task_create(subject, description?, tags?)**
Create a task. Tags are lowercase strings. Always apply relevant tags — if the user says "urgent", include `["urgent"]`. If they mention a person by name (e.g. "for Sandrina"), tag with their first name lowercased (e.g. `["sandrina"]`).

**task_list(filter_tag?, filter_status?, limit?, include_deleted?)**
List tasks. Call with no args for all open tasks. Use `filter_status` to scope to pending/in_progress/completed.

**task_update(id, status?, subject?, description?, tags?)**
Update a task. To mark done: `status="completed"`. To start: `status="in_progress"`. To close/complete/mark done: `status="completed"`.

**task_delete(id)**
Soft-delete a task. Use when user says "delete", "remove", or "get rid of" a task.

**tag_set_icon(tag, icon)**
Assign an emoji to a tag. Persists across sessions.

**tag_list()**
Show all tag → emoji mappings.

### Behavior Rules

- Use full first + last names in task subjects. If only a first name is given, use it as-is in the tag but ask for the last name if it will appear in the subject.
- When creating a task, always echo back the rendered result (subject + tags).
- When listing tasks, present them concisely — one line per task with status badge and tags.
- "Close", "done", "complete", "finish" all mean `status="completed"`.
- After any update, confirm with a single short line — don't re-list everything.
- The task board artifact auto-refreshes every 10 seconds, so chat-created tasks will appear there automatically.
