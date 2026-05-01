#!/usr/bin/env python3
"""Tasks MCP Server.

A personal task list for Claude Desktop. Tasks persist across sessions in
~/.claude-tasks/tasks.json. Tags map to emoji icons via ~/.claude-tasks/config.json.

Tools:
  task_create(subject, description?, tags?)
  task_list(filter_tag?, filter_status?, limit?, include_deleted?)
  task_update(id, status?, subject?, description?, tags?)
  task_delete(id)
  tag_set_icon(tag, icon)
  tag_list()

Storage layout:
  ~/.claude-tasks/tasks.json   -- task store, atomic writes
  ~/.claude-tasks/config.json  -- tag -> icon mapping
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Constants & paths
# ---------------------------------------------------------------------------
VALID_STATUSES = {"pending", "in_progress", "completed"}
DATA_DIR = Path(os.path.expanduser("~/.claude-tasks"))
TASKS_FILE = DATA_DIR / "tasks.json"
CONFIG_FILE = DATA_DIR / "config.json"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = SCRIPT_DIR / "default_config.json"

logging.basicConfig(
    level=logging.INFO,
    format="[tasks-mcp] %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("tasks-mcp")

_LOCK = threading.RLock()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: Path, payload: Any) -> None:
    _ensure_data_dir()
    fd, tmp_path = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _load_default_config() -> dict[str, Any]:
    fallback = {
        "tag_icons": {
            "urgent": "\U0001f525",
            "todo": "\U0001f4cb",
            "followup": "\U0001f4de",
            "meeting": "\U0001f5d3️",
            "demo": "\U0001f3af",
            "review": "\U0001f440",
            "blocked": "\U0001f6a7",
            "waiting": "⏳",
        }
    }
    if DEFAULT_CONFIG_FILE.exists():
        try:
            with open(DEFAULT_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            log.warning("Failed to read default_config.json (%s); using fallback", exc)
    return fallback


def _load_config() -> dict[str, Any]:
    _ensure_data_dir()
    if not CONFIG_FILE.exists():
        cfg = _load_default_config()
        try:
            _atomic_write_json(CONFIG_FILE, cfg)
        except Exception as exc:
            log.warning("Could not initialize config.json (%s)", exc)
        return cfg
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict) or "tag_icons" not in cfg:
            raise ValueError("config.json missing tag_icons")
        if not isinstance(cfg["tag_icons"], dict):
            raise ValueError("tag_icons must be an object")
        return cfg
    except Exception as exc:
        log.warning("config.json unreadable (%s); regenerating from defaults", exc)
        try:
            shutil.move(str(CONFIG_FILE), str(CONFIG_FILE) + ".corrupt")
        except OSError:
            pass
        cfg = _load_default_config()
        _atomic_write_json(CONFIG_FILE, cfg)
        return cfg


def _save_config(cfg: dict[str, Any]) -> None:
    _atomic_write_json(CONFIG_FILE, cfg)


def _empty_store() -> dict[str, Any]:
    return {"tasks": [], "next_id": 1}


def _load_tasks() -> dict[str, Any]:
    _ensure_data_dir()
    if not TASKS_FILE.exists():
        return _empty_store()
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "tasks" not in data or not isinstance(data["tasks"], list):
            raise ValueError("tasks.json malformed: missing tasks list")
        if "next_id" not in data or not isinstance(data["next_id"], int):
            existing_ids = [t.get("id", 0) for t in data["tasks"] if isinstance(t.get("id"), int)]
            data["next_id"] = (max(existing_ids) + 1) if existing_ids else 1
        return data
    except Exception as exc:
        log.warning("tasks.json corrupted (%s); quarantining and starting fresh", exc)
        try:
            stamp = datetime.now().strftime("%Y%m%d%H%M%S")
            quarantine = TASKS_FILE.parent / f"tasks.json.corrupt.{stamp}"
            shutil.move(str(TASKS_FILE), str(quarantine))
        except OSError as move_exc:
            log.warning("Could not quarantine corrupt tasks.json (%s)", move_exc)
        return _empty_store()


def _save_tasks(store: dict[str, Any]) -> None:
    _atomic_write_json(TASKS_FILE, store)


def _validate_status(status: str) -> str:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status '{status}'. Must be one of: {sorted(VALID_STATUSES)}")
    return status


def _normalize_tags(tags: Any) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(tags, list):
        raise ValueError("tags must be a list of strings")
    out: list[str] = []
    for t in tags:
        if not isinstance(t, str):
            raise ValueError("each tag must be a string")
        t = t.strip().lower()
        if t and t not in out:
            out.append(t)
    return out


def _validate_icon(icon: Any) -> str:
    if not isinstance(icon, str):
        raise ValueError("icon must be a string")
    if "\x00" in icon:
        icon = icon.replace("\x00", "")
    if not icon:
        raise ValueError("icon must be a non-empty string")
    if len(icon) > 16:
        raise ValueError("icon too long (max 16 chars)")
    return icon


def _render_task_line(task: dict[str, Any], icon_map: dict[str, str]) -> str:
    tags = task.get("tags", [])
    icon_prefix = ""
    unmapped: list[str] = []
    for tag in tags:
        icon = icon_map.get(tag)
        if icon:
            icon_prefix += icon
        else:
            unmapped.append(tag)
    parts: list[str] = []
    if icon_prefix:
        parts.append(icon_prefix)
    parts.append(f"#{task['id']}")
    parts.append(task.get("subject", "<no subject>"))
    if unmapped:
        parts.append("[" + ", ".join(unmapped) + "]")
    status = task.get("status", "pending")
    if status != "pending":
        parts.append(f"({status})")
    return " ".join(parts)


def _public_view(task: dict[str, Any], icon_map: dict[str, str]) -> dict[str, Any]:
    out = dict(task)
    out["rendered"] = _render_task_line(task, icon_map)
    return out


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("tasks")


@mcp.tool()
def task_create(
    subject: str,
    description: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new task."""
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("subject is required and must be a non-empty string")
    norm_tags = _normalize_tags(tags)
    desc = description if isinstance(description, str) else None
    with _LOCK:
        store = _load_tasks()
        existing_ids = [t.get("id", 0) for t in store["tasks"] if isinstance(t.get("id"), int)]
        next_id = max(existing_ids + [store.get("next_id", 1) - 1]) + 1
        task = {
            "id": next_id,
            "subject": subject.strip(),
            "description": desc,
            "tags": norm_tags,
            "status": "pending",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "completed_at": None,
            "deleted_at": None,
        }
        store["tasks"].append(task)
        store["next_id"] = next_id + 1
        _save_tasks(store)
        cfg = _load_config()
    return _public_view(task, cfg["tag_icons"])


@mcp.tool()
def task_list(
    filter_tag: str | None = None,
    filter_status: str | None = None,
    limit: int | None = None,
    include_deleted: bool = False,
) -> dict[str, Any]:
    """List tasks with rendered icon prefixes."""
    if filter_status is not None:
        _validate_status(filter_status)
    norm_tag = filter_tag.strip().lower() if isinstance(filter_tag, str) and filter_tag.strip() else None
    with _LOCK:
        store = _load_tasks()
        cfg = _load_config()
    icon_map = cfg["tag_icons"]
    tasks = list(store["tasks"])
    if not include_deleted:
        tasks = [t for t in tasks if not t.get("deleted_at")]
    if norm_tag is not None:
        tasks = [t for t in tasks if norm_tag in t.get("tags", [])]
    if filter_status is not None:
        tasks = [t for t in tasks if t.get("status") == filter_status]
    active = [t for t in tasks if t.get("status") in ("pending", "in_progress")]
    done = [t for t in tasks if t.get("status") == "completed"]
    active.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    done.sort(key=lambda t: (t.get("completed_at") or t.get("updated_at") or ""), reverse=True)
    ordered = active + done
    if isinstance(limit, int) and limit >= 0:
        ordered = ordered[:limit]
    public = [_public_view(t, icon_map) for t in ordered]
    rendered_text = "No tasks yet. Use task_create to add one." if not public else "\n".join(p["rendered"] for p in public)
    return {"count": len(public), "tasks": public, "rendered": rendered_text}


@mcp.tool()
def task_update(
    id: int,
    status: str | None = None,
    subject: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Update fields on a task."""
    if not isinstance(id, int):
        raise ValueError("id must be an integer")
    with _LOCK:
        store = _load_tasks()
        cfg = _load_config()
        task = next((t for t in store["tasks"] if t.get("id") == id), None)
        if task is None:
            raise ValueError(f"task #{id} not found")
        if task.get("deleted_at"):
            raise ValueError(f"task #{id} is deleted; cannot update")
        if status is not None:
            _validate_status(status)
            prev = task.get("status")
            task["status"] = status
            if status == "completed" and prev != "completed":
                task["completed_at"] = _now_iso()
            if status != "completed":
                task["completed_at"] = None
        if subject is not None:
            if not isinstance(subject, str) or not subject.strip():
                raise ValueError("subject must be a non-empty string")
            task["subject"] = subject.strip()
        if description is not None:
            task["description"] = description
        if tags is not None:
            task["tags"] = _normalize_tags(tags)
        task["updated_at"] = _now_iso()
        _save_tasks(store)
    return _public_view(task, cfg["tag_icons"])


@mcp.tool()
def task_delete(id: int) -> dict[str, Any]:
    """Soft-delete a task (sets deleted_at). Hidden from list by default."""
    if not isinstance(id, int):
        raise ValueError("id must be an integer")
    with _LOCK:
        store = _load_tasks()
        cfg = _load_config()
        task = next((t for t in store["tasks"] if t.get("id") == id), None)
        if task is None:
            raise ValueError(f"task #{id} not found")
        if task.get("deleted_at"):
            return {"ok": True, "already_deleted": True, "task": _public_view(task, cfg["tag_icons"])}
        task["deleted_at"] = _now_iso()
        task["updated_at"] = task["deleted_at"]
        _save_tasks(store)
    return {"ok": True, "task": _public_view(task, cfg["tag_icons"])}


@mcp.tool()
def tag_set_icon(tag: str, icon: str) -> dict[str, Any]:
    """Map a tag to an emoji/icon. Persists to ~/.claude-tasks/config.json."""
    if not isinstance(tag, str) or not tag.strip():
        raise ValueError("tag must be a non-empty string")
    norm = tag.strip().lower()
    icon = _validate_icon(icon)
    with _LOCK:
        cfg = _load_config()
        cfg.setdefault("tag_icons", {})
        cfg["tag_icons"][norm] = icon
        _save_config(cfg)
    return {"ok": True, "tag": norm, "icon": icon, "tag_icons": cfg["tag_icons"]}


@mcp.tool()
def tag_list() -> dict[str, Any]:
    """Return the current tag -> icon mapping."""
    with _LOCK:
        cfg = _load_config()
    return cfg["tag_icons"]


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    log.info("tasks-mcp starting; data dir = %s", DATA_DIR)
    _ensure_data_dir()
    _load_config()
    mcp.run()


if __name__ == "__main__":
    main()
