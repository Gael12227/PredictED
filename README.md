# PredictED v2 — Hospital ED Overcrowding Dashboard

A professional, **light-theme** web dashboard for a hospital Emergency
Department that fuses **three data sources** into one live overcrowding-risk
view with **plain-language explanations** and **what-if analysis**:

| Source | What it provides | Path |
|---|---|---|
| 📁 CSV archives | `Delhi_urban.csv` / `delhi_Rural.csv` — historical NEDOCS, occupancy, AQI, weather, chief complaints | `backend/core/csv_loader.py` |
| 🌐 Public REST API | Live Delhi weather + air quality (Open-Meteo, keyless) | `backend/ingestion/web_fetcher.py` |
| 📡 MQTT telemetry | Edge sensors (`ultrasound_inflow`, `imu_variance`, `mic_decibels`) + EMR census snapshots | `backend/ingestion/mqtt_listener.py` |

The existing assets stay untouched and still run: the two Streamlit apps
(`streamlit run Upgraded_App.py` / `app.py`), the Random Forest model
(`predictED_rf_model.joblib`), `Data.py`, `predictED_live.db`, and the CSVs.

> **Demo/simulation scope — not for clinical use.** This project works on
> simulated data, contains no PHI, and must not drive real clinical decisions
> without validation.

## Architecture

```
React UI  (Vite + TS + react-router)
  /  /urban  /rural            REST /api/*  +  WS /ws/dashboard
                                      │
                        FastAPI (uvicorn, :8000)
   ┌──────────────┬───────────────────┴──────────────────────────┐
   │ csv_loader   │ state.py (per-archetype live store + trends) │
   │ (baselines,  │ core/ (nedocs · predictor · explainer ·      │
   │  history)    │        whatif)                               │
   │              │ ingestion/ (mqtt · web_fetcher · simulator)  │
   └──────────────┴──────────────────────────────────────────────┘
                     │ sqlite: hardware_logs + emr_snapshots
                     │ Open-Meteo (weather + AQI, Delhi)
                     │ MQTT broker: predictED/state, predictED/sensor
```

**Two context pages** — `/urban` and `/rural` — each reads its own Delhi CSV
and lets you switch the archetype (Big/Small). Metrics, baselines, seasonal
framing, and explanations are per-context (tourist season for urban,
agricultural season for rural).

## Quickstart

### 1. Backend

```bash
python -m venv --system-site-packages .venv          # Windows: .venv\Scripts\...
.venv/Scripts/pip install -r backend/requirements.txt
.venv/Scripts/python -m uvicorn backend.main:app --port 8000
```

No MQTT broker? The backend falls back to a built-in **simulator** that
streams realistic census + sensor telemetry for all four Delhi archetypes
(`predictED_live.db` fills up live). API docs at http://127.0.0.1:8000/docs.

### 2. Frontend (needs Node.js ≥ 18)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api + /ws to :8000)
npm run build      # type-checks + production build
```

### 3. Real MQTT path (optional)

```bash
docker compose up -d mosquitto                       # or your own broker
PREDICTED_MQTT_HOST=127.0.0.1 PREDICTED_DEMO_MODE=never \
  .venv/Scripts/python -m uvicorn backend.main:app --port 8000
.venv/Scripts/python -m backend.ingestion.simulator --mqtt   # publishes streams
```

Devices publish JSON to:

- `predictED/state` — EMR census: `{"hospital_type": "Big Urban (Delhi)",
  "ed_pts": 46, "ed_beds": 60, "admits": 9, "hosp_beds": 850, "vents": 2,
  "longest_wait": 4.2, "last_wait": 1.1}`
- `predictED/sensor` — telemetry: `{"hospital_type": "Big Urban (Delhi)",
  "sensor_type": "ultrasound_inflow" | "imu_variance" | "mic_decibels",
  "value": 1.0}`

No MQTT client? `POST /api/telemetry` is an HTTP fallback.

## What the dashboard explains

- **Risk level** — NEDOCS score with the PredictED bands (<60 not busy,
  60–100 busy, 100–140 overcrowded, ≥140 critical), plus the **T+2h Random
  Forest forecast**.
- **Why** — deterministic rules: NEDOCS term contributions (exact points),
  threshold flags (occupancy >100%, boarding time >4 h, arrival velocity,
  IMU chaos, noise, AQI), forecast drivers from model importances × deviation,
  recommended actions per level.
- **Context** — historical baselines from the CSVs (“typical NEDOCS for month
  9 ≈ 87 — current 109 is above”), chief-complaint mixes, live Delhi weather/AQI.
- **What-if** — step a value and see *exactly* how the score and forecast
  move (linear coefficient for NEDOCS, local sensitivity for the forecast),
  level-band crossings, and scenario presets. Apply to live persists an
  override through the same pipeline (shown in trends + DB); Reset restores
  the EMR-fed values.

## Configuration

Environment variables (prefix `PREDICTED_`):

| Variable | Default | Meaning |
|---|---|---|
| `PREDICTED_MQTT_HOST` / `_PORT` | `127.0.0.1` / `1883` | Broker address |
| `PREDICTED_MQTT_ENABLED` | `true` | Try to connect to a broker |
| `PREDICTED_DEMO_MODE` | `auto` | `auto` → simulator when broker absent; `always` → simulator even with broker; `never` → no simulator |
| `PREDICTED_WEB_ENABLED` | `true` | Poll Open-Meteo |
| `PREDICTED_WEB_INTERVAL` | `300` | Seconds between web fetches |
| `PREDICTED_CENSUS_INTERVAL` / `PREDICTED_SENSOR_INTERVAL` | `6` / `2` | Simulator cadence (s) |
| `PREDICTED_BROADCAST_INTERVAL` | `2` | WebSocket push cadence (s) |

## Repository layout

```
backend/            FastAPI app (config, state, core/, ingestion/, routers/)
frontend/           React + Vite + TS dashboard (pages Urban/Rural/Home)
Data.py             legacy NEDOCS formula + synthetic generator
app.py / Upgraded_App.py   legacy Streamlit dashboards (still runnable)
database.py         legacy sqlite layer used by the Streamlit apps
predictED_rf_model.joblib  trained T+2h forecast model (9 features)
predictED_live.db   sqlite: hardware_logs + emr_snapshots
Delhi_urban.csv / delhi_Rural.csv   historical ED context data
docker-compose.yml  optional local mosquitto broker
```

## Main API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/state?context=urban\|rural` | Full dashboard state (score, forecast, explanation, drivers, trends, sources) |
| `GET /api/contexts` | Contexts + hospital archetypes found in the CSVs |
| `GET /api/context/{urban\|rural}/summary?hospital_type=…` | Historical baselines for one archetype |
| `GET /api/context/{urban\|rural}/history?hospital_type=…` | Monthly NEDOCS/occupancy series |
| `POST /api/whatif` | What-if: `{hospital_type, features}` → score, forecast, sensitivity, level crossings |
| `POST /api/state/override` / `DELETE /api/state/override` | Apply / clear a manual override |
| `POST /api/telemetry` | HTTP telemetry fallback for sensors |
| `WS /ws/dashboard` | Live push of both contexts every ~2 s |
