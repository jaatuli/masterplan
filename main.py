#!/usr/bin/env python3
"""
main.py – E-ink dashboard main program.
Fetches data, renders the image and displays it.
"""

import argparse
import logging
import platform
import sys
from pathlib import Path

import yaml

# ── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("cache/error.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("dashboard")


# ── Configuration ────────────────────────────────────────────────────────────

def load_config(path: str = "config.yaml") -> dict:
    cfg_path = Path(path)
    if not cfg_path.exists():
        log.warning(
            "config.yaml not found. Copy config.example.yaml → config.yaml and fill in the details."
        )
        return {}
    with cfg_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ── Display ───────────────────────────────────────────────────────────────────

def get_display():
    """Selects the correct display driver based on the runtime environment."""
    if platform.system() == "Linux" and platform.machine().startswith("aarch"):
        from display.epaper import EPaperDisplay
        return EPaperDisplay()
    else:
        from display.simulator import SimulatorDisplay
        return SimulatorDisplay()


# ── Data fetching ───────────────────────────────────────────────────────────

def fetch_module(name: str, config: dict, use_cache: bool) -> "dict | None":
    """Fetches data for a single module. Returns None if fetching fails."""
    try:
        if name == "weather":
            from data.weather import fetch
        elif name == "electricity":
            from data.electricity import fetch
        elif name == "waste":
            from data.waste import fetch
        elif name == "calendar":
            from data.calendar import fetch
        elif name == "evaka":
            from data.evaka import fetch
        elif name == "hsl":
            from data.hsl import fetch
        elif name == "news":
            from data.news import fetch
        elif name == "keep":
            from data.keep import fetch
        else:
            log.error("Unknown module: %s", name)
            return None

        data = fetch(config, use_cache=use_cache)
        stale = data.get("_stale", False)
        status = " (stale cache)" if stale else ""
        log.info("✓ %s%s", name, status)
        return data

    except Exception as e:
        log.error("✗ %s failed: %s", name, e)
        return None


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="E-ink dashboard")
    parser.add_argument(
        "--preview", action="store_true",
        help="Open the rendered image in Preview (Mac only)"
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Force data refresh, ignore cache"
    )
    parser.add_argument(
        "--only",
        choices=["weather", "electricity", "waste", "calendar", "evaka", "hsl", "news", "keep"],
        help="Run only one module (for testing)"
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="Configuration file (default: config.yaml)"
    )
    return parser.parse_args()


# ── Main program ───────────────────────────────────────────────────────────

def main():
    args = parse_args()

    # Ensure cache directory exists
    Path("cache").mkdir(exist_ok=True)

    config = load_config(args.config)
    use_cache = not args.no_cache

    display_cfg = config.get("display", {})
    width  = display_cfg.get("width",  800)
    height = display_cfg.get("height", 480)

    if args.only:
        # Run only one module and print the result
        data = fetch_module(args.only, config, use_cache)
        import json
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    # Determine grid layout from config (falls back to default if absent/invalid)
    from render import DEFAULT_LAYOUT

    def _validate_grid(grid) -> bool:
        return (
            isinstance(grid, list) and len(grid) == 2
            and all(isinstance(r, list) and len(r) == 3 for r in grid)
        )

    grid = config.get("layout", {}).get("grid", DEFAULT_LAYOUT)
    if not _validate_grid(grid):
        log.warning("Invalid layout.grid in config — using default layout")
        grid = DEFAULT_LAYOUT

    # Modules that require specific credentials to be configured
    _requires_config: dict[str, tuple[str, str]] = {
        "evaka": ("evaka", "username"),
        "hsl":   ("hsl",   "api_key"),
        "keep":  ("keep",  "username"),
    }

    # Collect unique module names from the grid (skip None/blank cells)
    grid_modules: set[str] = {
        cell for row in grid for cell in row if cell
    }

    # Fetch only the modules that appear in the layout
    log.info("Fetching data...")
    data: dict = {}
    for name in grid_modules:
        req = _requires_config.get(name)
        if req and not config.get(req[0], {}).get(req[1]):
            data[name] = None
            continue
        data[name] = fetch_module(name, config, use_cache)

    # News – always fetched (full-width strip, not part of the configurable grid)
    news = fetch_module("news", config, use_cache)

    # Render image
    log.info("Rendering image...")
    from render import render
    image = render(
        data=data,
        layout=grid,
        news=news,
        width=width,
        height=height,
    )

    # Display image
    display = get_display()
    display.show(image, open_preview=args.preview)
    log.info("Done.")


if __name__ == "__main__":
    main()
