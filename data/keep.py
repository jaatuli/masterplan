"""
keep.py – Fetches notes from Google Keep via gkeepapi.

Config:
  keep:
    username: "email@gmail.com"
    password: "xxxx xxxx xxxx xxxx"  # app-specific password (spaces OK); used only on
                                     # first run or when cache/keep_token.json is missing.
                                     # Generate at: https://myaccount.google.com/apppasswords
    label: "dashboard"               # optional: filter by label name
    max_notes: 5                     # optional, default 5
    ttl_minutes: 60                  # optional, default 60

Auth flow:
  First run  – gpsoauth.perform_master_login() exchanges the password for a long-lived
               master token which is saved to cache/keep_token.json.
  Later runs – keep.authenticate() uses the saved master token (no password needed).
  Token expiry – LoginException triggers deletion of the token file and a fresh login.
"""

import json
import logging
import secrets
from datetime import datetime
from pathlib import Path

CACHE_FILE  = Path("cache/keep.json")
_TOKEN_FILE = Path("cache/keep_token.json")
DEFAULT_TTL = 60
DEFAULT_MAX = 5

log = logging.getLogger(__name__)


class DataFetchError(Exception):
    pass


# ── Cache helpers ─────────────────────────────────────────────────────────────

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


# ── Token helpers ─────────────────────────────────────────────────────────────

def _load_token() -> dict:
    """Returns {"master_token": "...", "android_id": "..."} or {} if absent/corrupt."""
    try:
        return json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_token(data: dict):
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _get_master_token(email: str, password: str) -> tuple[str, str]:
    """Exchange a Google app-specific password for a long-lived master token.

    The android_id is reused from an existing token file (or generated fresh) so
    that Google sees a stable device fingerprint — changing it can invalidate tokens.
    """
    import gpsoauth

    saved      = _load_token()
    android_id = saved.get("android_id") or secrets.token_hex(8)  # 16 hex chars
    clean_pw   = password.replace(" ", "")  # Google displays app passwords with spaces

    response = gpsoauth.perform_master_login(email, clean_pw, android_id)
    token    = response.get("Token")
    if not token:
        raise DataFetchError(f"gpsoauth master login failed: {response}")

    _save_token({"master_token": token, "android_id": android_id})
    log.info("keep: obtained and saved new master token")
    return token, android_id


# ── Main fetch ────────────────────────────────────────────────────────────────

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
        import gkeepapi
        import gkeepapi.exception

        saved        = _load_token()
        master_token = saved.get("master_token")
        android_id   = saved.get("android_id")

        # First run (or token file missing): get master token from password
        if not master_token:
            master_token, android_id = _get_master_token(username, password)

        # Authenticate with master token
        keep = gkeepapi.Keep()
        try:
            keep.authenticate(username, master_token, device_id=android_id)
        except gkeepapi.exception.LoginException as exc:
            # Token expired or revoked — delete it and try once more via password
            log.warning("keep: master token rejected (%s); re-authenticating via password", exc)
            _TOKEN_FILE.unlink(missing_ok=True)
            master_token, android_id = _get_master_token(username, password)
            keep = gkeepapi.Keep()
            keep.authenticate(username, master_token, device_id=android_id)

        # Persist rotated token if Google issued a new one
        refreshed = keep.getMasterToken()
        if refreshed and refreshed != master_token:
            log.info("keep: master token rotated, saving updated token")
            _save_token({"master_token": refreshed, "android_id": android_id})

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
