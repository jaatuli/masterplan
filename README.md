# E-ink Dashboard

A home dashboard for a Waveshare 7.5" e-ink display (800×480), running on a Raspberry Pi. Displays weather, calendar events, news headlines, waste collection schedule, daycare events, and public transit departures.

## Layout

```
┌──────────────────┬──────────────────┬──────────────────┐
│  PÄIVÄKOTI       │  KALENTERI       │  SÄÄ + PVM/KELLO │
│  Daycare events  │  Calendar events │  Weather         │
├──────────────────┼──────────────────┼──────────────────┤
│  SÄHKÖ           │  HSL             │  JÄTEHUOLTO      │
│  Electricity     │  Transit         │  Waste schedule  │
├──────────────────┴──────────────────┴──────────────────┤
│  UUTISET  (full width, 2 headlines)                    │
└────────────────────────────────────────────────────────┘
```

## Hardware

| Part | Model | Notes |
|---|---|---|
| Display | Waveshare 7.5" e-Paper HAT V2 (800×480) | Black/white |
| Computer | Raspberry Pi Zero 2 W (or any Pi with 40-pin GPIO) | Needs pre-soldered headers |
| Power | 5V micro-USB charger, ≥1A | Standard phone charger works |

> **Important:** The Raspberry Pi Zero 2 W is sold both with and without GPIO headers.
> The Waveshare HAT has a female connector and requires **male pins** on the Pi.
> Make sure to buy the **"with headers" (WH) version**, or solder a 2×20 male header yourself.

## Data sources

| Module | Source | Auth |
|---|---|---|
| Weather | [Open-Meteo](https://open-meteo.com/) | None |
| Calendar | Google Calendar iCal | Secret URL token |
| News | YLE Uutiset RSS | None |
| Waste | Manual schedule in config | None |
| Daycare | Espoo eVaka (`/api/citizen/auth/weak-login`) | Username + password |
| Transit | [HSL Digitransit v2 GraphQL](https://portal-api.digitransit.fi/) | API key |

## Development setup

Runs on macOS and Windows. Both use PNG simulation — no Raspberry Pi needed for development.

### 1. Clone and create virtualenv

**macOS / Linux:**
```bash
git clone <repo>
cd eInk
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows (Git Bash or similar):**
```bash
git clone <repo>
cd eInk
python -m venv venv
venv/Scripts/pip install -r requirements.txt
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your credentials and location. The file contains passwords and API keys — do not commit it.

Key settings:

```yaml
location:
  latitude: 60.1699
  longitude: 24.9384
  name: "Helsinki"

hsl:
  api_key: "your-key-from-portal-api.digitransit.fi"
  to_name: "Pasila"
  to_lat: 60.1985
  to_lon: 24.9323
  min_walk_bus: 3       # minutes to nearest bus stop
  min_walk_rail: 15     # minutes to nearest train station

waste:
  collections:
    - type: "Sekajäte"
      interval_weeks: 2
      next_date: "2026-03-25"
    - type: "Biojäte"
      interval_weeks: 4
      next_date: "2026-03-16"
```

### 3. Google Calendar iCal link

In Google Calendar: *Calendar settings → "Private address in iCal format"*. Add the URL to `config.yaml`:

```yaml
calendars:
  - name: "Oma"
    ical_url: "https://calendar.google.com/calendar/ical/.../basic.ics"
```

### 4. HSL API key

Register at [portal-api.digitransit.fi](https://portal-api.digitransit.fi/) and create a subscription for the Routing API. Add the key to `config.yaml`.

### 5. Run

**macOS:**
```bash
python main.py --preview           # full run, opens PNG in Preview
python main.py --no-cache --preview
python main.py --only weather      # test single module
```

**Windows:**
```bash
venv/Scripts/python main.py --preview           # full run, opens PNG in default viewer
venv/Scripts/python main.py --no-cache --preview
venv/Scripts/python main.py --only weather      # test single module

# Optional: suppress Unicode log noise in cp1252 terminals
PYTHONIOENCODING=utf-8 venv/Scripts/python main.py --no-cache
```

> **Windows note:** Windows terminals using cp1252 encoding show `--- Logging error ---` for the
> ✓/✗ log characters — this is cosmetic only. The PNG is generated correctly regardless.
> Set `PYTHONIOENCODING=utf-8` to suppress it.

## Alternative deployment: ESP32 + Home Assistant

The dashboard can also run on a **Waveshare ESP32-S3-Touch-LCD-7** (800×480 color LCD) using ESPHome and Home Assistant as the data broker. This removes the Pi entirely.

### Architecture

Two approaches are available:

**Option A — Image server (recommended, reuses existing code):**
```
External APIs → AppDaemon (runs render.py) → /homeassistant/www/dashboard.png
                                                         ↓
                                 ESPHome online_image → Waveshare 7" LCD
```
AppDaemon (HA add-on) runs the existing Python renderer on a schedule and saves the PNG to HA's `www/` folder. ESPHome fetches and displays it via the `online_image` component.

**Option B — LVGL (full color, touch-capable):**
```
External APIs → Home Assistant sensors → ESPHome LVGL UI → Waveshare 7" LCD
```
All data lives in HA as sensors; ESPHome renders the layout natively using LVGL widgets.

### Hardware

| Part | Model |
|---|---|
| Display | Waveshare ESP32-S3-Touch-LCD-7 (800×480, RGB, touch) |
| Power | USB-C |

### Option A setup: AppDaemon image server

#### 1. Install AppDaemon add-on

**Settings → Add-ons → Add-on Store → AppDaemon** → Install, enable Start on boot.

#### 2. Add Python packages

**AppDaemon → Configuration tab**, add under `python_packages`:
```
Pillow, requests, pycaruna, icalendar, recurring_ical_events, aiohttp
```

#### 3. Clone the repo into AppDaemon's config directory

From the HA Terminal add-on (the host path `/addon_configs/a0d7b954_appdaemon/` is `/config/` inside AppDaemon's container):

```bash
cd /addon_configs/a0d7b954_appdaemon
git clone https://github.com/jaatuli/masterplan eink
cp eink/config.example.yaml eink/config.yaml
nano eink/config.yaml   # fill in credentials
```

#### 4. Install the AppDaemon app

Copy `ha/appdaemon/apps/dashboard_renderer.py` and `ha/appdaemon/apps/apps.yaml` to `/config/apps/` (the shared HA apps directory).

#### 5. Restart AppDaemon

The app runs immediately on startup and every 10 minutes after. The PNG is served at:
```
http://<your-ha-ip>:8123/local/dashboard.png
```

#### Path notes (AppDaemon container vs host)

| Location | Host path (Terminal add-on) | AppDaemon container path |
|---|---|---|
| AppDaemon config | `/addon_configs/a0d7b954_appdaemon/` | `/config/` |
| HA config / www | `/config/` | `/homeassistant/` |
| eink repo | `/addon_configs/a0d7b954_appdaemon/eink/` | `/config/eink/` |
| Output PNG | `/config/www/dashboard.png` | `/homeassistant/www/dashboard.png` |

#### 6. ESPHome config

```yaml
online_image:
  - url: http://192.168.1.x:8123/local/dashboard.png
    id: dashboard_img
    format: PNG
    update_interval: 600s
    on_download_finished:
      - component.update: my_display

display:
  - platform: rpi_dpi_rgb
    id: my_display
    lambda: |-
      it.image(0, 0, id(dashboard_img));
```

### ESPHome board support

Use the community package [`inytar/waveshare-esp32-s3-touch-lcd-7-esphome`](https://github.com/inytar/waveshare-esp32-s3-touch-lcd-7-esphome) (requires ESPHome 2025.4.2+). PSRAM must be enabled (8MB available on this board — required for 800×480 frame buffer).

---

## Raspberry Pi deployment

### 1. Flash SD card

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
- OS: Raspberry Pi OS Lite (64-bit)
- Enable SSH, set username/password, configure WiFi (country: FI)

### 2. Connect display

Attach the Waveshare HAT to the 40-pin GPIO header with the Pi powered off.

### 3. Enable SPI

```bash
ssh pi@eink.local
sudo raspi-config   # Interface Options → SPI → Enable
sudo reboot
```

### 4. Install dependencies

```bash
# Waveshare e-Paper library
git clone https://github.com/waveshare/e-Paper.git

# Project
git clone <repo> eInk
cd eInk
python3 -m venv venv
venv/bin/pip install ~/e-Paper/RaspberryPi_JetsonNano/python
venv/bin/pip install -r requirements.txt

# System libraries required by the GPIO stack
sudo apt install -y swig liblgpio-dev
venv/bin/pip install spidev gpiozero lgpio
```

### 5. Copy config

```bash
# From Mac:
scp config.yaml pi@eink.local:~/eInk/
```

### 6. Test

```bash
venv/bin/python main.py
```

### 7. Set up cron

```bash
crontab -e
```

Add:
```
@reboot cd /home/pi/eInk && venv/bin/python main.py >> /tmp/eink.log 2>&1
*/10 * * * * cd /home/pi/eInk && venv/bin/python main.py >> /tmp/eink.log 2>&1
```

### Sync changes from Mac to Pi

```bash
rsync -av --exclude venv --exclude cache --exclude output \
  /path/to/eInk/ pi@eink.local:~/eInk/
```

## Project structure

```
eInk/
├── main.py              # Entry point, CLI args, module orchestration
├── render.py            # Pillow-based image renderer (800×480, grayscale)
├── config.yaml          # Your config (not committed)
├── config.example.yaml  # Template
├── data/
│   ├── weather.py       # Open-Meteo
│   ├── calendar.py      # iCal / Google Calendar
│   ├── news.py          # YLE RSS feed
│   ├── electricity.py   # Caruna / pycaruna
│   ├── waste.py         # Manual waste schedule
│   ├── evaka.py         # Espoo daycare (eVaka)
│   └── hsl.py           # HSL Digitransit transit
├── display/
│   ├── simulator.py     # PNG output for macOS/Windows development
│   └── epaper.py        # Waveshare 7.5" v2 driver (Raspberry Pi)
├── fonts/               # Optional: place Inter-Regular.ttf + Inter-Bold.ttf here
├── cache/               # JSON cache files (auto-generated)
└── output/              # Output PNG (auto-generated, macOS only)
```

## Caching

Each module writes a JSON cache file under `cache/`. TTLs are configurable per module in `config.yaml`. Stale cache is used as a fallback when an API call fails — the dashboard always shows something even when offline.

```yaml
cache:
  ttl_minutes: 55           # weather, calendar
  hsl_ttl_minutes: 10       # real-time transit
  hsl_active_hours: [6, 22] # no HSL fetches outside these hours
  evaka_ttl_minutes: 1440   # daycare: once per day
  electricity_ttl_minutes: 720
```
