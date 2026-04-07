import os
import sys

import appdaemon.plugins.hass.hassapi as hass

REPO_DIR  = "/config/eink"
OUTPUT    = "/config/www/dashboard.png"
CACHE_DIR = f"{REPO_DIR}/cache"


class DashboardRenderer(hass.Hass):
    def initialize(self):
        interval = self.args.get("interval_seconds", 600)
        self.run_every(self.render, "now", interval)
        self.log("DashboardRenderer started")

    def render(self, kwargs):
        # chdir so all relative paths (cache/, fonts/, config.yaml) resolve correctly
        os.chdir(REPO_DIR)
        if REPO_DIR not in sys.path:
            sys.path.insert(0, REPO_DIR)

        os.makedirs(CACHE_DIR, exist_ok=True)

        try:
            from main import load_config, fetch_module
            from render import render

            config = load_config("config.yaml")
            use_cache = True

            display_cfg = config.get("display", {})
            width  = display_cfg.get("width",  800)
            height = display_cfg.get("height", 480)

            weather     = fetch_module("weather",     config, use_cache)
            electricity = fetch_module("electricity", config, use_cache)
            waste       = fetch_module("waste",       config, use_cache)
            calendar    = fetch_module("calendar",    config, use_cache)

            daycare = fetch_module("evaka", config, use_cache) \
                      if config.get("evaka", {}).get("username") else None
            hsl     = fetch_module("hsl",   config, use_cache) \
                      if config.get("hsl",  {}).get("api_key")  else None

            news = fetch_module("news", config, use_cache)

            image = render(
                weather=weather, electricity=electricity, waste=waste,
                calendar=calendar, daycare=daycare, hsl=hsl, news=news,
                width=width, height=height,
            )
            image.save(OUTPUT)
            self.log(f"Dashboard saved to {OUTPUT}")

        except Exception as e:
            self.log(f"Render failed: {e}", level="ERROR")
