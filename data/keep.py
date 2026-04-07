"""
keep.py – Fetches notes from Google Keep via gkeepapi.

Config:
  keep:
    username: "email@gmail.com"
    password: "app_specific_password"  # Google app-specific password (not your main password)
    label: "dashboard"                 # optional: filter by label name
    max_notes: 5                       # optional, default 5
    ttl_minutes: 60                    # optional, default 60
"""

import json
import logging
from datetime import datetime
from pathlib import Path

CACHE_FILE  = Path("cache/keep.json")
DEFAULT_TTL = 60
DEFAULT_MAX = 5

log = logging.getLogger(__name__)


class DataFetchError(Exception):
    pass


def _cache_is_fresh(ttl_minutes: int) -> bool:
    if not CACHE_FILE.exists():
        return False
    age = datetime.now().timestamp() - CACHE_FILE.stat().st_mtime
    return age < ttl_minutes * 60


def _load_cache() -> dict | None:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(data: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def fetch(config: dict, use_cache: bool = True) -> dict:
    keep_cfg   = config.get("keep", {})
    ttl        = int(keep_cfg.get("ttl_minutes", DEFAULT_TTL))
    max_notes  = int(keep_cfg.get("max_notes", DEFAULT_MAX))
    username   = keep_cfg.get("username")
    password   = keep_cfg.get("password")
    label_name = keep_cfg.get("label")  # may be None

    if not username or not password:
        raise DataFetchError("keep.username and keep.password are required in config")

    if use_cache and _cache_is_fresh(ttl):
        cached = _load_cache()
        if cached:
            return cached

    try:
        import gkeepapi  # imported here so missing library gives a clear error

        keep = gkeepapi.Keep()
        # Strip spaces from app-specific passwords (Google displays them with spaces)
        clean_password = password.replace(" ", "")
        keep.authenticate(username, clean_password)

        # Resolve label filter
        target_label = None
        if label_name:
            target_label = keep.findLabel(label_name)
            # findLabel returns None if no match — degrade gracefully to all notes

        notes_gen = keep.find(
            labels=[target_label] if target_label else None,
            archived=False,
            trashed=False,
        )

        notes = []
        for node in notes_gen:
            if len(notes) >= max_notes:
                break
            title   = (node.title or "").strip()
            body    = (node.text  or "").strip()
            snippet = body[:120]
            notes.append({
                "title":   title,
                "snippet": snippet,
                "pinned":  bool(node.pinned),
            })

        # Pinned notes first, preserve server order within each group
        notes.sort(key=lambda n: not n["pinned"])

    except Exception as e:
        cached = _load_cache()
        if cached:
            cached["_stale"] = True
            log.warning("keep fetch failed, using stale cache: %s", e)
            return cached
        raise DataFetchError(f"Google Keep fetch failed: {e}") from e

    data = {
        "notes":      notes,
        "label":      label_name or "",
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save_cache(data)
    return data
