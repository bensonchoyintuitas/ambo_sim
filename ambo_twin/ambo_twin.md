## Ambo Twin - Runbook

### Overview
Ambo Twin is a Kafka-driven digital twin of Ambo Sim. It:
- Listens to Kafka topics for patient/ambulance/hospital events and FHIR resources
- Persists events/resources in SQLite
- Reanimates the simulation state in a UI matching Ambo Sim

### Prerequisites
- Python 3.10+
- Kafka reachable at `localhost:9092` (or provide your own bootstrap)
- Node not required (UI runs in-browser via CDN)

### 1) Start the Ambo Twin app (server + UI)
From repo root:

Linux/macOS
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m ambo_twin.app
# serves on http://localhost:5001 (set AMBO_TWIN_PORT or PORT to override)
```

Windows PowerShell
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m ambo_twin.app
# serves on http://localhost:5001 (set AMBO_TWIN_PORT or PORT to override)
```

The app serves the UI at `http://localhost:5001/` by default and exposes:
- POST `/ingest/kafka` – consumer POST target
- GET `/healthz` and `/readyz`

Data directory: `ambo_twin/data/twin.db` (auto-created)

### 2) Start the Kafka consumer (recommended in its own venv)
From `tools/kafka_consumer_twin`:

Linux/macOS
```bash

cd tools/orchestrator
python3 orchestrator.py kafka_consumers__twin.yml



python consumer.py --bootstrap-server localhost:9092 --twin-url http://localhost:5001 --auto-offset latest
```

Windows PowerShell
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python consumer.py --bootstrap-server localhost:9092 --twin-url http://localhost:5001 --auto-offset latest
```

Defaults (topics):
`patient condition encounter_ed_presentation encounter_discharge event_ambulance_heading_to_house event_ambulance_redirect event_arrive_hospital event_discharge event_hospital_location event_off_stretcher event_offload event_pickup_and_depart event_ramping`

Use `--auto-offset earliest` for backfill imports into SQLite.

### 3) Provide data (choose one)
- Use existing producers to republish recorded session JSON files (see `tools/orchestrator/kafka_producers.yml`).
- Or manually POST a recorded JSON to Twin (bypasses Kafka) for quick UI checks:
```bash
curl -X POST http://localhost:5001/ingest/kafka \
  -H "Content-Type: application/json" \
  -d '{
        "topic": "event_pickup_and_depart",
        "partition": 0,
        "offset": 1,
        "timestamp": null,
        "valueJson": {
          "eventType": "pickup_and_depart",
          "timestamp": "2025-10-15T22:01:00Z",
          "ambulance": {"id": 0, "state": "yellow"},
          "patient": {"reference": "Patient/pat-123", "display": "Pat"},
          "houseId": 0, "hospitalId": 0
        }
      }'
```

### 4) Run with orchestrator (optional)
You can launch pre-wired consumers via the orchestrator using:
```bash
python tools/orchestrator/orchestrator.py tools/orchestrator/kafka_consumers__twin.yml
```
This spawns xterm windows for each job (WSL-friendly). Jobs include:
- Live (latest offsets)
- Backfill (earliest offsets)

### UI parity with Ambo Sim
- Camera framing, fog, grid, and zoom behavior match the Ambo Sim scene.
- Double-click the canvas to refit/framing.

### Troubleshooting
- Module import error running the app directly:
  - Use `python -m ambo_twin.app` from repo root.
- No events appearing:
  - Confirm producers are publishing and consumer is running.
  - Check `/healthz` and app logs in your terminal.
- SQLite locked/permission issues:
  - Stop processes, delete `ambo_twin/data/twin.db*`, restart app and consumer.

### Configuration
App (defaults):
- `TWIN_DB`: `ambo_twin/data/twin.db`
- Houses/Hospitals/Ambulances: 10/3/5 (mirrors Ambo Sim layout)

Consumer flags:
- `--bootstrap-server`, `--group`, `--topics ...`, `--twin-url`, `--auto-offset {latest|earliest}`

### What’s next
- Replay controls (play/pause, speed, seek, session picker)
- Metrics endpoint for ingest rates and handler errors


