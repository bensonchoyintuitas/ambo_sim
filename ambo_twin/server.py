import os
import json
import sqlite3
from datetime import datetime, timezone
from threading import Lock
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit


DEFAULT_HOUSES = 10
DEFAULT_HOSPITALS = 3
DEFAULT_AMBULANCES = 5


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class TwinState:
    def __init__(self, houses: int, hospitals: int, ambulances: int):
        self._lock = Lock()
        self.houses = [{"id": i, "x": 50, "y": 50 + i * 60, "has_patient": False, "ambulance_on_the_way": False, "patient_ids": []} for i in range(houses)]
        self.hospitals = [{"id": i, "x": 450, "y": 50 + i * 200, "waiting": [], "treating": [], "discharged": []} for i in range(hospitals)]
        self.ambulances = []
        for i in range(ambulances):
            hosp = self.hospitals[i % len(self.hospitals)] if self.hospitals else {"x": 0, "y": 0}
            self.ambulances.append({
                "id": i,
                "x": hosp["x"],
                "y": hosp["y"],
                "state": "green",
                "patient_id": None,
                "patient_name": None,
                "patient_condition_display": None,
                "queue_hospital_id": None,
                "ramp_wait_seconds": 0
            })
        self.patient_log = []
        self.ambulance_log = []
        self.hospital_log = []
        self.log_capacity = 50
        # minimal lookup caches
        self.patient_index = {}  # patient_id -> {id, name}
        self.condition_by_patient = {}  # patient_id -> display
        self.last_hospital_by_patient = {}  # patient_id -> last known hospital id
        self.treat_start_by_patient = {}  # patient_id -> datetime when entered treating

    def _log(self, bucket: str, text: str, attachments=None):
        entry = {"text": f"{datetime.now().strftime('%H:%M:%S')} - {text}"}
        if isinstance(attachments, list) and attachments:
            entry["attachments"] = attachments
        # simple de-dupe of consecutive identical lines within same bucket
        if bucket == "patient":
            if self.patient_log and self.patient_log[0].get("text") == entry["text"]:
                return
            self.patient_log.insert(0, entry)
            if len(self.patient_log) > self.log_capacity:
                self.patient_log.pop()
        elif bucket == "ambulance":
            if self.ambulance_log and self.ambulance_log[0].get("text") == entry["text"]:
                return
            self.ambulance_log.insert(0, entry)
            if len(self.ambulance_log) > self.log_capacity:
                self.ambulance_log.pop()
        elif bucket == "hospital":
            if self.hospital_log and self.hospital_log[0].get("text") == entry["text"]:
                return
            self.hospital_log.insert(0, entry)
            if len(self.hospital_log) > self.log_capacity:
                self.hospital_log.pop()

    def _attachment_from_event(self, label_kind: str, payload: dict):
        try:
            label = (str(label_kind or "Event").replace("_", " ").strip().title())
        except Exception:
            label = "Event"
        return [{"label": label, "json": payload}]

    def get_state(self):
        return {
            "ambulances": self.ambulances,
            "houses": self.houses,
            "hospitals": self.hospitals,
        }

    def upsert_patient(self, patient_json: dict):
        try:
            pid = patient_json.get("id")
            name = None
            try:
                name = patient_json.get("name", [{}])[0].get("given", [None])[0]
            except Exception:
                name = None
            if pid:
                self.patient_index[pid] = {"id": pid, "name": name}
                self._log("patient", f"Patient resource received: {pid} {name or ''}", attachments=[{"label": "Patient", "json": patient_json}])
        except Exception:
            pass

    def upsert_condition(self, cond_json: dict):
        try:
            subj = cond_json.get("subject", {}).get("reference")
            if isinstance(subj, str) and "/" in subj:
                pid = subj.split("/")[-1]
                display = (cond_json.get("code", {}).get("coding", [{}])[0].get("display") or "Condition")
                self.condition_by_patient[pid] = display
                self._log("patient", f"Condition for {pid}: {display}", attachments=[{"label": "Condition", "json": cond_json}])
        except Exception:
            pass

    def _house_by_id(self, house_id: int):
        return next((h for h in self.houses if h["id"] == house_id), None)

    def _hospital_by_id(self, hospital_id: int):
        return next((h for h in self.hospitals if h["id"] == hospital_id), None)

    def _ambulance_by_id(self, amb_id: int):
        return next((a for a in self.ambulances if a["id"] == amb_id), None)

    def handle_event(self, topic: str, payload: dict):
        et = payload.get("eventType") or topic.replace("event_", "")
        amb = payload.get("ambulance") or {}
        amb_id = amb.get("id")
        patient_ref = (payload.get("patient") or {}).get("reference")
        patient_id = patient_ref.split("/")[-1] if isinstance(patient_ref, str) and "/" in patient_ref else None
        patient_name = self.patient_index.get(patient_id, {}).get("name") if patient_id else None
        cond_display = self.condition_by_patient.get(patient_id)

        with self._lock:
            if amb_id is not None and self._ambulance_by_id(amb_id) is None:
                # ensure ambulance exists if events reference more than configured default
                self.ambulances.append({
                    "id": amb_id,
                    "x": self.hospitals[0]["x"] if self.hospitals else 0,
                    "y": self.hospitals[0]["y"] if self.hospitals else 0,
                    "state": "green",
                    "patient_id": None,
                    "patient_name": None,
                    "patient_condition_display": None,
                    "queue_hospital_id": None,
                    "ramp_wait_seconds": 0
                })

            if et == "ambulance_heading_to_house":
                house_id = payload.get("houseId")
                if isinstance(house_id, int):
                    house = self._house_by_id(house_id)
                    if house:
                        house["has_patient"] = True
                        house["ambulance_on_the_way"] = True
                if amb_id is not None:
                    a = self._ambulance_by_id(amb_id)
                    if a:
                        a["state"] = "red"
                        a["patient_id"] = patient_id
                        a["patient_name"] = patient_name
                        a["patient_condition_display"] = cond_display
                        # snap toward house for visual; front-end will lerp
                        if isinstance(house_id, int):
                            h = self._house_by_id(house_id)
                            if h:
                                a["x"], a["y"] = h["x"], h["y"]
                self._log(
                    "ambulance",
                    f"Ambulance {amb_id} is heading to House {payload.get('houseId')} to pick up {patient_name or patient_id}",
                    attachments=self._attachment_from_event(et, payload)
                )

            elif et == "pickup_and_depart":
                house_id = payload.get("houseId")
                if isinstance(house_id, int):
                    house = self._house_by_id(house_id)
                    if house:
                        # patient leaves house
                        house["has_patient"] = False
                        house["ambulance_on_the_way"] = False
                        if patient_id and patient_id in house["patient_ids"]:
                            try:
                                house["patient_ids"].remove(patient_id)
                            except ValueError:
                                pass
                if amb_id is not None:
                    a = self._ambulance_by_id(amb_id)
                    if a:
                        a["state"] = "yellow"
                        a["patient_id"] = patient_id
                        a["patient_name"] = patient_name
                        a["patient_condition_display"] = cond_display
                        hosp_id = payload.get("hospitalId")
                        if isinstance(hosp_id, int):
                            a["queue_hospital_id"] = None
                            h = self._hospital_by_id(hosp_id)
                            if h:
                                a["x"], a["y"] = h["x"], h["y"]
                self._log(
                    "ambulance",
                    f"Ambulance {amb_id} picked up {patient_name or patient_id} from House {payload.get('houseId')} and is heading to Hospital {payload.get('hospitalId')}",
                    attachments=self._attachment_from_event(et, payload)
                )

            elif et == "arrive_hospital":
                if amb_id is not None:
                    a = self._ambulance_by_id(amb_id)
                    if a:
                        a["state"] = a.get("state") or "yellow"
                hosp_txt = f" at Hospital {payload.get('hospitalId')}" if isinstance(payload.get("hospitalId"), int) else ""
                self._log("ambulance", f"Ambulance {amb_id} arrived{hosp_txt}", attachments=self._attachment_from_event(et, payload))

            elif et == "offload":
                hosp_id = payload.get("hospitalId")
                if isinstance(hosp_id, int):
                    h = self._hospital_by_id(hosp_id)
                    if h and patient_id:
                        # add to waiting if not present
                        if all(p.get("id") != patient_id for p in h["waiting"]):
                            h["waiting"].append({
                                "id": patient_id,
                                "name": patient_name or patient_id,
                                "condition": {"code": {"display": cond_display or "Unknown"}},
                                "wait_time": 0
                            })
                        self.last_hospital_by_patient[patient_id] = hosp_id
                        # hospital-side log for arrival to waiting
                        self._log("hospital", f"{patient_name or patient_id} has arrived at Hospital {hosp_id} and entered waiting queue", attachments=self._attachment_from_event("location", {**payload, "eventType": "hospital_location", "room": "waiting"}))
                if amb_id is not None:
                    a = self._ambulance_by_id(amb_id)
                    if a:
                        a.update({
                            "state": "green",
                            "patient_id": None,
                            "patient_name": None,
                            "patient_condition_display": None,
                            "queue_hospital_id": None,
                            "ramp_wait_seconds": 0
                        })
                self._log("ambulance", f"Ambulance {amb_id} offload at Hospital {payload.get('hospitalId')}", attachments=self._attachment_from_event(et, payload))

            elif et == "off_stretcher":
                # same visual effect as offload into waiting area
                hosp_id = payload.get("hospitalId")
                if isinstance(hosp_id, int):
                    h = self._hospital_by_id(hosp_id)
                    if h and patient_id:
                        if all(p.get("id") != patient_id for p in h["waiting"]):
                            h["waiting"].append({
                                "id": patient_id,
                                "name": patient_name or patient_id,
                                "condition": {"code": {"display": cond_display or "Unknown"}},
                                "wait_time": 0
                            })
                        self.last_hospital_by_patient[patient_id] = hosp_id
                        self._log("hospital", f"{patient_name or patient_id} has arrived at Hospital {hosp_id} and entered waiting queue", attachments=self._attachment_from_event("location", {**payload, "eventType": "hospital_location", "room": "waiting"}))
                self._log("ambulance", f"Off stretcher at Hospital {payload.get('hospitalId')} for {patient_id}", attachments=self._attachment_from_event(et, payload))

            elif et == "ramping":
                hosp_id = payload.get("hospitalId")
                if amb_id is not None and isinstance(hosp_id, int):
                    a = self._ambulance_by_id(amb_id)
                    if a:
                        a["state"] = "orange"
                        a["queue_hospital_id"] = hosp_id
                        a["ramp_wait_seconds"] = 0
                self._log("ambulance", f"Ambulance {amb_id} ramping at Hospital {payload.get('hospitalId')}", attachments=self._attachment_from_event(et, payload))

            elif et in ("hospital_location", "location"):
                hosp_id = payload.get("hospitalId")
                room = payload.get("room")
                if isinstance(hosp_id, int) and patient_id and room in ("waiting", "treating", "discharged"):
                    h = self._hospital_by_id(hosp_id)
                    if h:
                        # remove from all rooms first
                        for q in ("waiting", "treating", "discharged"):
                            h[q] = [p for p in h[q] if p.get("id") != patient_id]
                        # add to target room
                        meta = {
                            "id": patient_id,
                            "name": patient_name or patient_id,
                            "condition": {"code": {"display": cond_display or "Unknown"}},
                            "wait_time": 0
                        }
                        h[room].append(meta)
                        self.last_hospital_by_patient[patient_id] = hosp_id
                        # hospital log for room movement
                        if room == "waiting":
                            self._log("hospital", f"{patient_name or patient_id} has arrived at Hospital {hosp_id} and entered waiting queue", attachments=self._attachment_from_event("location", payload))
                        elif room == "treating":
                            self.treat_start_by_patient[patient_id] = datetime.now(timezone.utc)
                            cond_txt = cond_display or "Unknown"
                            self._log("hospital", f"{patient_name or patient_id} moved to treating list | Hospital {hosp_id} | Condition: {cond_txt}", attachments=self._attachment_from_event("location", payload))
                        elif room == "discharged":
                            start = self.treat_start_by_patient.pop(patient_id, None)
                            try:
                                dur_sec = int((datetime.now(timezone.utc) - start).total_seconds()) if start else 40
                            except Exception:
                                dur_sec = 40
                            cond_txt = cond_display or "Unknown"
                            self._log("hospital", f"{patient_name or patient_id} moved to discharged list | Hospital {hosp_id} | Condition: {cond_txt} | Treatment duration: {dur_sec} seconds", attachments=self._attachment_from_event("location", payload))
                
            elif et == "discharge":
                # If explicit discharge event arrives, move to discharged in last known hospital if present
                hosp_id = payload.get("hospitalId")
                if isinstance(hosp_id, int) and patient_id:
                    h = self._hospital_by_id(hosp_id)
                    if h:
                        for q in ("waiting", "treating"):
                            h[q] = [p for p in h[q] if p.get("id") != patient_id]
                        if all(p.get("id") != patient_id for p in h["discharged"]):
                            h["discharged"].append({
                                "id": patient_id,
                                "name": patient_name or patient_id,
                                "condition": {"code": {"display": cond_display or "Unknown"}},
                                "wait_time": 0
                            })
                        self.last_hospital_by_patient[patient_id] = hosp_id
                        start = self.treat_start_by_patient.pop(patient_id, None)
                        try:
                            dur_sec = int((datetime.now(timezone.utc) - start).total_seconds()) if start else 40
                        except Exception:
                            dur_sec = 40
                        cond_txt = cond_display or "Unknown"
                        self._log("hospital", f"{patient_name or patient_id} moved to discharged list | Hospital {hosp_id} | Condition: {cond_txt} | Treatment duration: {dur_sec} seconds", attachments=self._attachment_from_event("discharge", payload))

            elif et in ("redirect", "ambulance_redirect"):
                from_h = payload.get("fromHospitalId")
                to_h = payload.get("toHospitalId")
                if amb_id is not None:
                    a = self._ambulance_by_id(amb_id)
                    if a:
                        a["state"] = "yellow"
                        a["queue_hospital_id"] = None
                self._log("ambulance", f"Redirecting ambulance {amb_id} from hospital {from_h} to hospital {to_h} due to ramping", attachments=self._attachment_from_event("redirect", payload))

    def handle_encounter(self, topic: str, encounter_json: dict):
        kind = "ed_presentation" if "encounter_ed_presentation" in (topic or "") else ("discharge" if "encounter_discharge" in (topic or "") else "encounter")
        subj = (encounter_json.get("subject") or {}).get("reference")
        pid = subj.split("/")[-1] if isinstance(subj, str) and "/" in subj else None
        name = self.patient_index.get(pid, {}).get("name") if pid else None
        hosp_id = self.last_hospital_by_patient.get(pid)
        if kind == "ed_presentation":
            tail = f" | Hospital {hosp_id}" if isinstance(hosp_id, int) else ""
            self._log("hospital", f"ED presentation created for {name or pid}{tail}", attachments=[{"label": "ED Presentation", "json": encounter_json}])
        elif kind == "discharge":
            self._log("hospital", f"Encounter discharge for {name or pid}", attachments=[{"label": "Discharge", "json": encounter_json}])


class TwinStorage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                topic TEXT NOT NULL,
                partition INTEGER NOT NULL,
                offset INTEGER NOT NULL,
                ts TEXT,
                event_type TEXT,
                patient_id TEXT,
                ambulance_id INTEGER,
                hospital_id INTEGER,
                house_id INTEGER,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (topic, partition, offset)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                patient_json TEXT,
                last_updated TEXT
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conditions (
                condition_id TEXT PRIMARY KEY,
                patient_id TEXT,
                json TEXT
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS encounters (
                encounter_id TEXT PRIMARY KEY,
                patient_id TEXT,
                kind TEXT,
                json TEXT
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS consumer_offsets (
                topic TEXT,
                partition INTEGER,
                group_id TEXT,
                offset INTEGER,
                updated_at TEXT,
                PRIMARY KEY (topic, partition, group_id)
            );
            """
        )
        conn.commit()
        conn.close()

    def insert_event(self, topic: str, partition: int, offset: int, ts: str, payload: dict):
        et = payload.get("eventType") or topic.replace("event_", "")
        amb = payload.get("ambulance") or {}
        house_id = payload.get("houseId") if isinstance(payload.get("houseId"), int) else None
        hosp_id = payload.get("hospitalId") if isinstance(payload.get("hospitalId"), int) else None
        amb_id = amb.get("id") if isinstance(amb.get("id"), int) else None
        pref = (payload.get("patient") or {}).get("reference")
        pid = pref.split("/")[-1] if isinstance(pref, str) and "/" in pref else None
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO events(topic, partition, offset, ts, event_type, patient_id, ambulance_id, hospital_id, house_id, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (topic, partition, offset, ts, et, pid, amb_id, hosp_id, house_id, json.dumps(payload)),
        )
        conn.commit()
        conn.close()

    def upsert_patient(self, patient_json: dict):
        pid = patient_json.get("id")
        if not pid:
            return
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO patients(patient_id, patient_json, last_updated)
            VALUES (?, ?, ?)
            ON CONFLICT(patient_id) DO UPDATE SET patient_json=excluded.patient_json, last_updated=excluded.last_updated
            """,
            (pid, json.dumps(patient_json), utc_now_iso()),
        )
        conn.commit()
        conn.close()

    def upsert_condition(self, condition_json: dict):
        cid = condition_json.get("id")
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO conditions(condition_id, patient_id, json)
            VALUES (?, ?, ?)
            """,
            (
                cid or f"cond-{utc_now_iso()}",
                (condition_json.get("subject", {}).get("reference", "/").split("/")[-1]),
                json.dumps(condition_json),
            ),
        )
        conn.commit()
        conn.close()

    def upsert_encounter(self, encounter_json: dict, kind_hint: str = "encounter"):
        enc_id = encounter_json.get("id") or f"enc-{utc_now_iso()}"
        subj = (encounter_json.get("subject") or {}).get("reference", "/")
        pid = subj.split("/")[-1]
        kind = "ed_presentation" if "encounter_ed_presentation" in (kind_hint or "") else ("discharge" if "encounter_discharge" in (kind_hint or "") else "encounter")
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO encounters(encounter_id, patient_id, kind, json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(encounter_id) DO UPDATE SET json=excluded.json, kind=excluded.kind
            """,
            (enc_id, pid, kind, json.dumps(encounter_json)),
        )
        conn.commit()
        conn.close()


def create_app():
    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"), static_folder=os.path.join(os.path.dirname(__file__), "static"))
    socketio = SocketIO(app, logger=False, engineio_logger=False, cors_allowed_origins="*", allow_upgrades=False, transports=["polling"]) 

    # config
    app.config.setdefault("TWIN_DB", os.path.join("ambo_twin", "data", "twin.db"))
    app.config.setdefault("HOUSES", DEFAULT_HOUSES)
    app.config.setdefault("HOSPITALS", DEFAULT_HOSPITALS)
    app.config.setdefault("AMBULANCES", DEFAULT_AMBULANCES)

    state = TwinState(app.config["HOUSES"], app.config["HOSPITALS"], app.config["AMBULANCES"])
    storage = TwinStorage(app.config["TWIN_DB"])

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.route("/readyz")
    def readyz():
        return jsonify({"status": "ready"})

    @app.route("/ingest/kafka", methods=["POST"])
    def ingest_kafka():
        try:
            doc = request.get_json(force=True, silent=False)
            topic = doc.get("topic")
            partition = int(doc.get("partition", 0))
            offset = int(doc.get("offset", 0))
            ts = doc.get("timestamp") or utc_now_iso()
            value = doc.get("valueJson")
            if isinstance(value, str):
                value = json.loads(value)
            if not isinstance(value, dict):
                return jsonify({"error": "valueJson must be object or JSON string"}), 400

            # Persist and update state
            storage.insert_event(topic, partition, offset, ts, value)

            # FHIR resources
            if value.get("resourceType") == "Patient":
                storage.upsert_patient(value)
                state.upsert_patient(value)
            elif value.get("resourceType") == "Condition":
                storage.upsert_condition(value)
                state.upsert_condition(value)
            elif value.get("resourceType") == "Encounter":
                storage.upsert_encounter(value, topic or "encounter")
                state.handle_encounter(topic or "encounter", value)
            else:
                # Event
                state.handle_event(topic or value.get("eventType", "event"), value)

            # Emit updates to UI
            socketio.emit("update_patient_log", state.patient_log)
            socketio.emit("update_ambulance_log", state.ambulance_log)
            socketio.emit("update_hospital_log", state.hospital_log)
            socketio.emit("update_state", state.get_state())

            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @socketio.on("connect")
    def handle_connect():
        emit("update_patient_log", state.patient_log)
        emit("update_ambulance_log", state.ambulance_log)
        emit("update_hospital_log", state.hospital_log)
        emit("update_state", state.get_state())

    # expose to runner
    app.socketio = socketio
    app.twin_state = state
    app.twin_storage = storage
    return app


