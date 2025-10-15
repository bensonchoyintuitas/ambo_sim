from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import time
from threading import Thread, Lock
import math
from datetime import datetime, timezone
import json
from fhir_generators.generate_synthea_patient import generate_fallback_patient, generate_fhir_resources  # Import the function
import uuid
import logging
from fhir_generators.generate_condition import generate_condition
from fhir_generators.generate_encounter_ed_presentation import generate_encounter_ed_presentation
from fhir_generators.generate_encounter_discharge import generate_encounter_discharge
from concurrent.futures import ThreadPoolExecutor
import functools
from argparse import ArgumentParser
import atexit  # Add this import
from fhir_generators.generate_synthea_patient import generate_fallback_patient  # Import the function
import os  # Add this if not already present

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simulation.log'),
        logging.StreamHandler()
    ]
)
# Reduce noisy request logs from Werkzeug/Socket.IO long-polling
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('engineio').setLevel(logging.WARNING)
logging.getLogger('socketio').setLevel(logging.WARNING)

app = Flask(__name__)
socketio = SocketIO(app, logger=False, engineio_logger=False)

# Configurable variables
GLOBAL_MAX_PATIENTS_PER_HOSPITAL = 2  # Maximum patients that can be treated simultaneously in each hospital
WAITING_TIME = 2  # seconds (time step in seconds; controls speed of moving from waiting to treating)
TREATING_TIME = 40  # seconds total treatment duration
DEFAULT_LLM_MODEL = 'llama3.1:8b'  # Default LLM model to use
PATIENT_GENERATION_LOWER_BOUND = 5  # Lower bound for patient generation delay
PATIENT_GENERATION_UPPER_BOUND = 10  # Upper bound for patient generation delay
USE_LLM = True  # Default value, will be updated by command line args
OUTPUT_FHIR = False  # Default value, will be updated by command line args
FHIR_OUTPUT_DIR = "fhir_export"  # Base directory for FHIR outputs
SESSION_DIR = None  # Will be set at runtime if OUTPUT_FHIR is True
HOSPITAL_WAITING_CAPACITY = 6  # Maximum patients allowed in a hospital waiting room
LOG_CAPACITY = 50  # Max events to retain in each UI log
RAMP_REDIRECT_ENABLED = True  # Whether to redirect to another hospital instead of ramping (default on)
RAMP_REDIRECT_ENABLED = False  # Whether to redirect instead of ramping when waiting is full

class Condition:
    def __init__(self, id, clinical_status, verification_status, severity, category, 
                 code, subject_reference, onset_datetime, recorded_date, note=None):
        self.id = id
        self.clinical_status = clinical_status
        self.verification_status = verification_status
        self.severity = severity
        self.category = category
        self.code = code
        self.subject_reference = subject_reference
        self.onset_datetime = onset_datetime
        self.recorded_date = recorded_date
        self.note = note

    @classmethod
    def from_fhir(cls, fhir_condition):
        """Create a Condition object from a FHIR Condition resource"""
        try:
            logging.debug(f"Creating Condition from FHIR resource: {json.dumps(fhir_condition, indent=2)}")
            
            # Safely extract note text
            notes = fhir_condition.get('note', [])
            note_text = notes[0].get('text') if notes else None
            logging.debug(f"Extracted note text: {note_text}")
            
            # Create condition object
            condition = cls(
                id=fhir_condition.get('id'),
                clinical_status=fhir_condition.get('clinicalStatus', {}).get('coding', [{}])[0],
                verification_status=fhir_condition.get('verificationStatus', {}).get('coding', [{}])[0],
                severity=fhir_condition.get('severity', {}).get('coding', [{}])[0],
                category=fhir_condition.get('category', [{}])[0].get('coding', [{}])[0],
                code=fhir_condition.get('code', {}).get('coding', [{}])[0],
                subject_reference=fhir_condition.get('subject', {}).get('reference'),
                onset_datetime=fhir_condition.get('onsetDateTime'),
                recorded_date=fhir_condition.get('recordedDate'),
                note=note_text
            )
            logging.debug(f"Successfully created Condition object with ID: {condition.id}")
            return condition
            
        except Exception as e:
            logging.error(f"Error creating Condition from FHIR: {str(e)}")
            logging.error(f"FHIR condition data: {json.dumps(fhir_condition, indent=2)}")
            logging.error(f"Traceback:", exc_info=True)
            raise

    def to_dict(self):
        """Convert Condition object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'clinical_status': self.clinical_status,
            'verification_status': self.verification_status,
            'severity': self.severity,
            'category': self.category,
            'code': self.code,
            'subject_reference': self.subject_reference,
            'onset_datetime': self.onset_datetime,
            'recorded_date': self.recorded_date,
            'note': self.note
        }

class Patient:
    def __init__(self, id, name, condition, condition_severity=None, dob=None, condition_note=None, fhir_resources=None):
        self.id = id
        self.name = name
        self.condition = condition
        self.condition_severity = condition_severity
        self.dob = dob
        self.condition_note = condition_note
        self.wait_time = 0
        self.fhir_resources = fhir_resources or {}
        self.encounters = []  # Add list to store encounters
        self.latest_encounter_id = None  # Track latest ED presentation encounter id

class Ambulance:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y
        self.target = None
        self.is_available = True
        self.state = 'green'  # green means available
        self.patient = None  # Store the entire Patient object
        self.queue_hospital_id = None  # If ramping, which hospital we're queued at
        self.ramp_since = None  # When the ambulance started ramping (epoch seconds)
        self.redirect_attempted = False  # Track if we've already tried redirecting once for current patient

    def move_to(self, target_x, target_y):
        if self.x < target_x:
            self.x += 4  # Move twice as fast
        elif self.x > target_x:
            self.x -= 4  # Move twice as fast
        if self.y < target_y:
            self.y += 4  # Move twice as fast
        elif self.y > target_y:
            self.y -= 4  # Move twice as fast

class House:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y
        self.patient_ids = []  # Store multiple patient IDs
        self.ambulance_on_the_way = False

    def add_patient(self, patient_id):
        self.patient_ids.append(patient_id)

    def remove_patient(self, patient_id):
        self.patient_ids.remove(patient_id)

class Hospital:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y
        self.waiting = []  # Queue for waiting patients
        self.treating = []  # Queue for treating patients
        self.discharged = []  # Queue for discharged patients

    def add_patient_to_waiting(self, patient):
        self.waiting.append(patient)
        log_event(
            f"{patient.name} has arrived at Hospital {self.id} and entered waiting queue",
            event_type='hospital',
            attachments=build_location_attachment(self.id, 'waiting', patient)
        )

    def move_patient_to_treating(self):
        if self.waiting and len(self.treating) < GLOBAL_MAX_PATIENTS_PER_HOSPITAL:
            patient = self.waiting.pop(0)  # Remove the first patient from the waiting queue
            self.treating.append(patient)
            # Log movement to treating queue with context
            try:
                cond = patient.condition.code.get('display', 'Unknown') if patient and patient.condition else 'Unknown'
                log_event(
                    f"{patient.name} moved to treating list | Hospital {self.id} | Condition: {cond}",
                    event_type='hospital',
                    attachments=build_location_attachment(self.id, 'treating', patient)
                )
            except Exception:
                pass
            patient.wait_time = 0  # Reset wait time (used for treatment duration)
            return patient
        return None

    def discharge_patient(self):
        """Move patient from treating to discharged queue."""
        if self.treating:
            patient = self.treating.pop(0)  # Remove from treating queue
            self.discharged.append(patient)  # Add to discharged queue

            # Immediate hospital log for UI feedback (non-FHIR)
            discharge_details = (
                f"{patient.name} moved to discharged list | "
                f"Hospital {self.id} | "
                f"Condition: {patient.condition.code.get('display', 'Unknown')} | "
                f"Treatment duration: {patient.wait_time} seconds"
            )
            try:
                # Minimal JSON payload for discharge signal (consolidated with location reference)
                now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                # Prefer explicitly tracked latest encounter id; fallback to last encounter in list
                last_enc = None
                if getattr(patient, 'latest_encounter_id', None):
                    last_enc = {'id': patient.latest_encounter_id}
                elif getattr(patient, 'encounters', None):
                    last_enc = patient.encounters[-1]
                attachment = {
                    'eventType': 'discharge',
                    'timestamp': now_iso,
                    'location': {
                        'reference': f"Location/hospital{self.id}",
                        'room': 'discharged'
                    },
                    'patient': { 'reference': f"Patient/{patient.id}", 'display': patient.name },
                    'encounter': ({ 'reference': f"Encounter/{last_enc.get('id')}" } if isinstance(last_enc, dict) and last_enc.get('id') else None)
                }
                log_event(
                    discharge_details,
                    event_type='hospital',
                    attachments=([{ 'label': 'Discharge', 'json': attachment }] + (build_location_attachment(self.id, 'discharged', patient) or []))
                )
            except Exception:
                log_event(discharge_details, event_type='hospital')
            return patient
        return None

def calculate_distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

# Default starting counts; may be overridden by client config at runtime
DEFAULT_HOUSES = 10
DEFAULT_HOSPITALS = 3
DEFAULT_AMBULANCES = 5

# Initialize world with defaults
houses = [House(i, 50, 50 + i * 60) for i in range(DEFAULT_HOUSES)]
hospitals = [Hospital(i, 450, 50 + i * 200) for i in range(DEFAULT_HOSPITALS)]

# Initialize ambulances at the hospitals, equally distributed
ambulances = []
for i in range(DEFAULT_AMBULANCES):
    hospital = hospitals[i % len(hospitals)]  # Distribute ambulances evenly across hospitals
    ambulances.append(Ambulance(i, hospital.x, hospital.y))

# Initialize separate event logs
patient_event_log = []
ambulance_event_log = []
hospital_event_log = []

def log_event(message, event_type='general', attachments=None):
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_message = f"{timestamp} - {message}"
    event_obj = {'text': log_message}
    if attachments:
        # Keep attachments small if needed in the future; for now pass through
        event_obj['attachments'] = attachments
    
    if event_type == 'patient':
        patient_event_log.insert(0, event_obj)
        if len(patient_event_log) > LOG_CAPACITY:
            patient_event_log.pop()
        socketio.emit('update_patient_log', patient_event_log)
    elif event_type == 'ambulance':
        ambulance_event_log.insert(0, event_obj)
        if len(ambulance_event_log) > LOG_CAPACITY:
            ambulance_event_log.pop()
        socketio.emit('update_ambulance_log', ambulance_event_log)
    elif event_type == 'hospital':
        hospital_event_log.insert(0, event_obj)
        if len(hospital_event_log) > LOG_CAPACITY:
            hospital_event_log.pop()
        socketio.emit('update_hospital_log', hospital_event_log)
    else:
        # General log or other types can be handled here
        pass

def build_ambulance_event_attachment(event_kind, ambulance=None, patient=None, hospital_id=None, extra=None):
    """Create a minimal JSON payload for ambulance-related events."""
    try:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {
            'eventType': event_kind,
            'timestamp': now_iso
        }
        if ambulance is not None:
            payload['ambulance'] = {
                'id': getattr(ambulance, 'id', None),
                'state': getattr(ambulance, 'state', None)
            }
        if patient is not None:
            try:
                payload['patient'] = { 'reference': f"Patient/{patient.id}", 'display': patient.name }
            except Exception:
                pass
        if hospital_id is not None:
            payload['hospitalId'] = hospital_id
        if isinstance(extra, dict):
            payload.update(extra)
        # Create a more meaningful label from the event kind (e.g., 'pickup_and_depart' -> 'Pickup and Depart')
        try:
            label = (str(event_kind or 'Event').replace('_', ' ').strip().title())
        except Exception:
            label = 'Event'
        return [{ 'label': label, 'json': payload }]
    except Exception:
        return None

def build_redirect_attachment(ambulance=None, patient=None, from_hospital_id=None, to_hospital_id=None, extra=None):
    """Attachment helper for redirect events with a dedicated 'Redirect' label."""
    try:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {
            'eventType': 'redirect',
            'timestamp': now_iso,
            'fromHospitalId': from_hospital_id,
            'toHospitalId': to_hospital_id
        }
        if ambulance is not None:
            payload['ambulance'] = {
                'id': getattr(ambulance, 'id', None),
                'state': getattr(ambulance, 'state', None)
            }
        if patient is not None:
            try:
                payload['patient'] = { 'reference': f"Patient/{patient.id}", 'display': patient.name }
            except Exception:
                pass
        if isinstance(extra, dict):
            payload.update(extra)
        return [{ 'label': 'Redirect', 'json': payload }]
    except Exception:
        return None

def build_location_attachment(hospital_id, room, patient=None):
    """Create a minimal location payload: where in the hospital the patient is (ramp/waiting/treating)."""
    try:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {
            'eventType': 'location',
            'timestamp': now_iso,
            'hospitalId': hospital_id,
            'room': room
        }
        if patient is not None:
            try:
                payload['patient'] = { 'reference': f"Patient/{patient.id}", 'display': patient.name }
            except Exception:
                pass
        return [{ 'label': 'Location', 'json': payload }]
    except Exception:
        return None

def build_redirect_attachment(ambulance, patient, from_hospital_id, to_hospital_id, extra=None):
    """Create a JSON payload describing an ambulance redirect due to ramping."""
    try:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {
            'eventType': 'redirect',
            'timestamp': now_iso,
            'fromHospitalId': from_hospital_id,
            'toHospitalId': to_hospital_id
        }
        if ambulance is not None:
            payload['ambulance'] = {
                'id': getattr(ambulance, 'id', None),
                'state': getattr(ambulance, 'state', None)
            }
        if patient is not None:
            try:
                payload['patient'] = { 'reference': f"Patient/{patient.id}", 'display': patient.name }
            except Exception:
                pass
        if isinstance(extra, dict):
            payload.update(extra)
        return [{ 'label': 'Redirect', 'json': payload }]
    except Exception:
        return None

patients = []  # Global list to store all Patient objects

def generate_fallback_condition(patient_id):
    """Generate a basic condition without using LLM."""
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # List of sample conditions
    conditions = [
        {
            'code': '427623005',
            'display': 'Chest Pain'
        },
        {
            'code': '422400008',
            'display': 'Vomiting'
        },
        {
            'code': '39848009',
            'display': 'Wheezing'
        },
        {
            'code': '62315008',
            'display': 'Dizziness'
        },
        {
            'code': '25064002',
            'display': 'Headache'
        }
    ]
    
    # List of sample severities
    severities = [
        {
            'code': '24484000',
            'display': 'Severe'
        },
        {
            'code': '6736007',
            'display': 'Moderate'
        },
        {
            'code': '255604002',
            'display': 'Mild'
        }
    ]
    
    chosen_condition = random.choice(conditions)
    chosen_severity = random.choice(severities)
    
    condition = Condition(
        id=str(uuid.uuid4()),
        clinical_status={
            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
            "code": "active",
            "display": "Active"
        },
        verification_status={
            "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
            "code": "confirmed",
            "display": "Confirmed"
        },
        severity=chosen_severity,
        category={
            "system": "http://terminology.hl7.org/CodeSystem/condition-category",
            "code": "encounter-diagnosis",
            "display": "Encounter Diagnosis"
        },
        code=chosen_condition,
        subject_reference=f"Patient/{patient_id}",
        onset_datetime=current_time,
        recorded_date=current_time,
        note=f"Patient presents with {chosen_condition['display']}"
    )

    # Add this block to save the condition to file
    if OUTPUT_FHIR and SESSION_DIR:
        try:
            # Convert condition to FHIR format dictionary
            condition_fhir = {
                "resourceType": "Condition",
                "id": condition.id,
                "clinicalStatus": {
                    "coding": [condition.clinical_status]
                },
                "verificationStatus": {
                    "coding": [condition.verification_status]
                },
                "severity": {
                    "coding": [condition.severity]
                },
                "category": [{
                    "coding": [condition.category]
                }],
                "code": {
                    "coding": [condition.code]
                },
                "subject": {
                    "reference": condition.subject_reference
                },
                "onsetDateTime": condition.onset_datetime,
                "recordedDate": condition.recorded_date,
                "note": [{"text": condition.note}]
            }
            save_fhir_resource('condition', condition_fhir)
            logging.info(f"Saved condition FHIR resource for condition {condition.id}")
        except Exception as e:
            logging.error(f"Error saving condition FHIR resource: {str(e)}")
    
    return condition

def condition_to_fhir_dict(condition_obj):
    """Convert a Condition object back to a FHIR Condition resource dict."""
    if condition_obj is None:
        return None
    try:
        return {
            "resourceType": "Condition",
            "id": condition_obj.id,
            "clinicalStatus": {"coding": [condition_obj.clinical_status]},
            "verificationStatus": {"coding": [condition_obj.verification_status]},
            "severity": {"coding": [condition_obj.severity]},
            "category": [{"coding": [condition_obj.category]}],
            "code": {"coding": [condition_obj.code]},
            "subject": {"reference": condition_obj.subject_reference},
            "onsetDateTime": condition_obj.onset_datetime,
            "recordedDate": condition_obj.recorded_date,
            "note": ([{"text": condition_obj.note}] if condition_obj.note else [])
        }
    except Exception:
        return None

def generate_fallback_encounter(patient_id, condition_id, hospital_id):
    """Generate a basic encounter without using LLM."""
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Sample procedures based on condition
    procedures = [
        "Vital signs measurement",
        "Physical examination",
        "Blood test",
        "X-ray examination",
        "ECG monitoring"
    ]
    
    encounter = {
        'id': str(uuid.uuid4()),
        'status': 'finished',
        'type': [{'coding': [{'display': 'Emergency visit'}]}],
        'priority': {'coding': [{'display': 'Urgent'}]},
        'subject': {'reference': f'Patient/{patient_id}'},
        'serviceType': {'coding': [{'display': 'Emergency Medicine'}]},
        'period': {'start': current_time},
        'diagnosis': [{'condition': {'display': 'Acute condition'}}],
        'reasonCode': [{'coding': [{'display': 'Emergency presentation'}]}],
        'procedure': [{'display': random.choice(procedures)}]
    }
    
    return encounter

def generate_discharge_for_patient(hospital, patient):
    """Process discharge for a single patient"""
    try:
        if patient.encounters:
            original_encounter = patient.encounters[-1]
            start_time = original_encounter['period']['start']
            end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            discharge = generate_encounter_discharge(
                encounter_id=original_encounter['id'],
                start_time=start_time,
                end_time=end_time
            )
            
            patient.encounters.append(discharge)
            
            # Save the discharge encounter to file if OUTPUT_FHIR is enabled
            if OUTPUT_FHIR and SESSION_DIR:
                try:
                    save_fhir_resource('encounter_discharge', discharge)
                    logging.info(f"Saved discharge encounter FHIR resource for encounter {discharge['id']}")
                except Exception as e:
                    logging.error(f"Error saving discharge encounter FHIR resource: {str(e)}")
            
            # Add discharge event logging with JSON attachment
            discharge_summary = (
                f"Discharge encounter created for {patient.name} | Hospital {hospital.id} | "
                f"Condition: {patient.condition.code.get('display', 'Unknown')} | "
                f"Total time in hospital: {patient.wait_time} seconds"
            )
            try:
                log_event(
                    discharge_summary,
                    event_type='hospital',
                    attachments=[{'label': 'Discharge', 'json': validate_encounter_data(discharge)}]
                )
            except Exception:
                log_event(discharge_summary, event_type='hospital')
    except Exception as e:
        logging.error(f"Error generating discharge: {str(e)}")
        log_event(f"Error processing discharge for {patient.name}", event_type='hospital')

# Add thread pool for parallel patient generation
patient_generator_pool = ThreadPoolExecutor(max_workers=8)

def create_patient(house, session_dir=None, llm_model=None):
    """Create a patient with either Synthea API or fallback, for both manual and automatic generation."""
    try:
        # Try Synthea API first if available
        logging.info("Attempting to generate patient using Synthea API...")
        patient_data = generate_fhir_resources(session_dir)
        
        if not patient_data or 'error' in patient_data:
            logging.info("Using fallback patient generation")
            patient_data = generate_fallback_patient(session_dir)
            
        patient_resource = patient_data.get('patient', {})
        
        # Generate condition using either API data or basic condition
        if USE_LLM:
            logging.info(f"Generating condition using LLM model: {llm_model or DEFAULT_LLM_MODEL}")
            request_counter.increment_started()
            try:
                condition_dict = generate_condition(
                    patient_id=patient_resource['id'],
                    llm_model=llm_model or DEFAULT_LLM_MODEL
                )
                request_counter.increment_completed()
                logging.info(f"Successfully generated condition: {json.dumps(condition_dict, indent=2)}")
                
                # Save the LLM-generated condition FHIR resource
                if OUTPUT_FHIR and condition_dict:
                    save_fhir_resource('condition', condition_dict)
                    logging.info(f"Saved LLM-generated condition FHIR resource")
                
                # Convert dictionary to Condition object
                condition = Condition.from_fhir(condition_dict)
                logging.info("Successfully converted condition dict to object")
                
            except Exception as e:
                logging.error(f"Error in LLM condition generation: {str(e)}", exc_info=True)
                logging.info("Falling back to basic condition")
                condition = None
        
        if not USE_LLM or condition is None:
            # Use richer fallback generator that picks realistic codes and severities
            condition = generate_fallback_condition(patient_resource['id'])
            logging.info("Created fallback condition (varied) using generate_fallback_condition")
        
        # Create the patient object
        try:
            patient = Patient(
                id=patient_resource['id'],
                name=patient_resource['name'][0]['given'][0],
                condition=condition,
                dob=patient_resource.get('birthDate', 'Unknown'),
                condition_note=condition.note if condition else None,
                fhir_resources=patient_data
            )
            logging.info(f"Successfully created patient: {patient.id}")
        except Exception as e:
            logging.error(f"Error creating Patient object: {str(e)}", exc_info=True)
            logging.error(f"Patient resource: {json.dumps(patient_resource, indent=2)}")
            logging.error(f"Condition object: {vars(condition) if condition else None}")
            raise
        
        # Add patient to simulation
        patients.append(patient)
        house.add_patient(patient.id)
        
        # Log patient creation with request counter stats
        counts = request_counter.get_counts()
        log_parts = [
            f"Patient Generated:",
            f"ID: {patient.id}",
            f"Name: {patient.name}",
            f"DOB: {patient.dob}",
            f"Condition: {condition.code.get('display', 'Unknown')}",
            f"Severity: {condition.severity.get('display', 'Unknown')}",
            f"Clinical Status: {condition.clinical_status.get('display', 'Unknown')}",
            f"LLM Requests: {counts['started']}",
            f"Completed: {counts['completed']}"
        ]
        
        if condition.note:
            log_parts.append(f"Notes: {condition.note}")

        # Attach FHIR JSON for patient and condition
        attachments = []
        try:
            if isinstance(patient_resource, dict) and patient_resource:
                attachments.append({'label': 'Patient', 'json': patient_resource})
        except Exception:
            pass
        try:
            condition_fhir = condition_to_fhir_dict(condition) if isinstance(condition, Condition) else None
            if not condition_fhir and 'condition_dict' in locals():
                condition_fhir = condition_dict
            if condition_fhir:
                attachments.append({'label': 'Condition', 'json': condition_fhir})
        except Exception:
            pass

        log_event(" | ".join(log_parts), event_type='patient', attachments=attachments)
        return patient
        
    except Exception as e:
        logging.error(f"Error creating patient: {str(e)}", exc_info=True)
        return None

def move_ambulances():
    """Move ambulances to pick up patients and take them to the nearest hospital."""
    while True:
        for house in houses:
            if house.patient_ids and not house.ambulance_on_the_way:
                # Find the closest available ambulance
                available_ambulances = [a for a in ambulances if a.is_available]
                if available_ambulances:
                    closest_ambulance = min(
                        available_ambulances,
                        key=lambda a: calculate_distance(a.x, a.y, house.x, house.y)
                    )
                    patient = next((p for p in patients if p.id == house.patient_ids[0]), None)
                    if patient:
                        closest_ambulance.is_available = False
                        closest_ambulance.target = (house.x, house.y)
                        closest_ambulance.state = 'red'  # Heading to pick up a patient
                        house.ambulance_on_the_way = True
                        closest_ambulance.patient = patient
                        closest_ambulance.redirect_attempted = False
                        log_event(
                            f"Ambulance {closest_ambulance.id} is heading to House {house.id} to pick up {patient.name}",
                            event_type='ambulance',
                            attachments=build_ambulance_event_attachment(
                                'ambulance_heading_to_house', ambulance=closest_ambulance, patient=patient, hospital_id=None,
                                extra={'houseId': house.id}
                            )
                        )
                    else:
                        log_event(
                            f"No patient found at House {house.id}",
                            event_type='ambulance',
                            attachments=build_ambulance_event_attachment('ambulance_no_patient', ambulance=closest_ambulance, patient=None, hospital_id=None, extra={'houseId': house.id})
                        )

        for ambulance in ambulances:
            if ambulance.target:
                # Move ambulance to the target (house or hospital)
                target_x, target_y = ambulance.target
                ambulance.move_to(target_x, target_y)

                # If reached house with patient
                if ambulance.x == target_x and ambulance.y == target_y:
                    patient_house = next((house for house in houses if house.x == target_x and house.y == target_y), None)
                    if patient_house and patient_house.patient_ids:
                        patient_house.remove_patient(ambulance.patient.id)
                        if not patient_house.patient_ids:
                            patient_house.ambulance_on_the_way = False  # Reset ambulance flag (no log)
                        else:
                            # Check if another ambulance is needed
                            available_ambulances = [a for a in ambulances if a.is_available]
                            if available_ambulances:
                                # Assign another ambulance to the remaining patients
                                next_ambulance = min(
                                    available_ambulances,
                                    key=lambda a: calculate_distance(a.x, a.y, patient_house.x, patient_house.y)
                                )
                                next_ambulance.is_available = False
                                next_ambulance.target = (patient_house.x, patient_house.y)
                                next_ambulance.state = 'red'
                                next_ambulance.patient = next((p for p in patients if p.id == patient_house.patient_ids[0]), None)
                                next_ambulance.redirect_attempted = False
                                log_event(
                                    f"Ambulance {next_ambulance.id} is heading to House {patient_house.id} to pick up Patient {next_ambulance.patient.id}",
                                    event_type='ambulance',
                                    attachments=build_ambulance_event_attachment('ambulance_heading_to_house', ambulance=next_ambulance, patient=next_ambulance.patient, hospital_id=None, extra={'houseId': patient_house.id})
                                )
                            else:
                                patient_house.ambulance_on_the_way = False  # No available ambulances
                        nearest_hospital = find_nearest_hospital(ambulance.x, ambulance.y)
                        ambulance.target = (nearest_hospital.x, nearest_hospital.y)
                        ambulance.state = 'yellow'  # Has patient, heading to hospital
                        ambulance.ramp_since = None
                        log_event(
                            f"Ambulance {ambulance.id} picked up {ambulance.patient.name} from House {patient_house.id} and is heading to Hospital {nearest_hospital.id}",
                            event_type='ambulance',
                            attachments=build_ambulance_event_attachment('pickup_and_depart', ambulance=ambulance, patient=ambulance.patient, hospital_id=nearest_hospital.id, extra={'houseId': patient_house.id})
                        )
                    elif ambulance.x == ambulance.target[0] and ambulance.y == ambulance.target[1]:
                        # If ambulance reached the hospital
                        nearest_hospital = find_nearest_hospital(ambulance.x, ambulance.y)
                        patient = ambulance.patient  # may be None
                        if patient:
                            # If waiting room has capacity, drop patient; otherwise consider redirect or ramp outside
                            if len(nearest_hospital.waiting) < HOSPITAL_WAITING_CAPACITY:
                                nearest_hospital.add_patient_to_waiting(patient)
                                ambulance.is_available = True
                                ambulance.state = 'green'
                                ambulance.target = None
                                ambulance.patient = None
                                ambulance.queue_hospital_id = None
                                ambulance.redirect_attempted = False
                            else:
                                # Waiting full: optional redirection
                                if RAMP_REDIRECT_ENABLED and len(hospitals) > 1 and not getattr(ambulance, 'redirect_attempted', False):
                                    from_hid = nearest_hospital.id
                                    candidate, ramp_len = choose_best_redirect_hospital(from_hid, ambulance.x, ambulance.y)
                                    if candidate is not None:
                                        ambulance.target = (candidate.x, candidate.y)
                                        ambulance.state = 'yellow'
                                        ambulance.queue_hospital_id = None
                                        ambulance.ramp_since = None
                                        ambulance.redirect_attempted = True
                                        log_event(
                                            f"Redirecting ambulance {ambulance.id} from hospital {from_hid} to hospital {candidate.id} due to ramping",
                                            event_type='ambulance',
                                            attachments=build_redirect_attachment(ambulance=ambulance, patient=ambulance.patient, from_hospital_id=from_hid, to_hospital_id=candidate.id, extra={'toRampQueue': ramp_len})
                                        )
                                    else:
                                        # Fallback to ramp if no candidates (should not happen)
                                        ambulance.is_available = False
                                        ambulance.queue_hospital_id = nearest_hospital.id
                                        if ambulance.state != 'orange' or not ambulance.ramp_since:
                                            ambulance.state = 'orange'
                                            ambulance.ramp_since = time.time()
                                            log_event(
                                                f"Ambulance {ambulance.id} waiting to offload at Hospital {nearest_hospital.id} (waiting full)",
                                                event_type='ambulance',
                                                attachments=build_ambulance_event_attachment('ramping', ambulance=ambulance, patient=ambulance.patient, hospital_id=nearest_hospital.id)
                                            )
                                else:
                                    # Ramp: keep patient on board, mark ambulance waiting outside.
                                    ambulance.is_available = False
                                    ambulance.queue_hospital_id = nearest_hospital.id
                                    if ambulance.state != 'orange' or not ambulance.ramp_since:
                                        ambulance.state = 'orange'
                                        ambulance.ramp_since = time.time()
                                        log_event(
                                            f"Ambulance {ambulance.id} waiting to offload at Hospital {nearest_hospital.id} (waiting full)",
                                            event_type='ambulance',
                                            attachments=build_ambulance_event_attachment('ramping', ambulance=ambulance, patient=ambulance.patient, hospital_id=nearest_hospital.id)
                                        )
                        else:
                            # No patient attached, reset ambulance to available state
                            ambulance.is_available = True
                            ambulance.state = 'green'
                            ambulance.target = None
                            ambulance.queue_hospital_id = None
                            ambulance.redirect_attempted = False

        socketio.emit('update_state', get_state())
        time.sleep(0.05)  # Reduce the sleep time to make the simulation feel faster

def find_nearest_hospital(x, y):
    """Find the nearest hospital to the given coordinates."""
    nearest_hospital = min(hospitals, key=lambda h: calculate_distance(x, y, h.x, h.y))
    return nearest_hospital

def choose_best_redirect_hospital(current_hospital_id, from_x, from_y):
    """Choose the next nearest hospital with the smallest ramping queue.
    Excludes the current hospital. Only returns hospitals with available waiting capacity.
    Returns tuple (hospital, ramp_queue_len) or (None, None).
    """
    if not hospitals or len(hospitals) <= 1:
        return (None, None)
    # Compute ramping queue lengths per hospital
    ramp_counts = {}
    for h in hospitals:
        ramp_counts[h.id] = sum(1 for a in ambulances if a.state == 'orange' and a.queue_hospital_id == h.id and a.patient)
    # Candidate hospitals MUST have capacity in waiting
    candidates = [h for h in hospitals if h.id != current_hospital_id and len(h.waiting) < HOSPITAL_WAITING_CAPACITY]
    if not candidates:
        return (None, None)
    # Rank by: ramp queue len, then distance (all have space)
    def rank(h):
        distance = calculate_distance(from_x, from_y, h.x, h.y)
        return (ramp_counts.get(h.id, 0), distance)
    best = min(candidates, key=rank)
    return (best, ramp_counts.get(best.id, 0))

def get_state():
    """Returns the state of ambulances, houses, and hospitals."""
    return {
        'ambulances': [{
            'id': a.id,
            'x': a.x,
            'y': a.y,
            'state': a.state,
            'patient_id': a.patient.id if a.patient else None,
            'patient_name': a.patient.name if a.patient else None,
            'patient_condition_display': (a.patient.condition.code.get('display', 'Unknown') if a.patient and a.patient.condition else None),
            'queue_hospital_id': a.queue_hospital_id,
            'ramp_wait_seconds': int(time.time() - a.ramp_since) if a.state == 'orange' and a.ramp_since else 0
        } for a in ambulances],
        'houses': [
            {
                'id': h.id,
                'x': h.x,
                'y': h.y,
                'has_patient': len(h.patient_ids) > 0,
                'ambulance_on_the_way': h.ambulance_on_the_way,
                'patient_ids': h.patient_ids
            } for h in houses
        ],
        'hospitals': [
            {
                'id': h.id,
                'x': h.x,
                'y': h.y,
                'waiting': [{
                    'id': p.id,
                    'name': p.name,
                    'condition': p.condition.to_dict() if p.condition else None,  # Convert Condition to dict
                    'wait_time': p.wait_time
                } for p in h.waiting],
                'treating': [{
                    'id': p.id,
                    'name': p.name,
                    'condition': p.condition.to_dict() if p.condition else None,  # Convert Condition to dict
                    'wait_time': p.wait_time
                } for p in h.treating],
                'discharged': [{
                    'id': p.id,
                    'name': p.name,
                    'condition': p.condition.to_dict() if p.condition else None,  # Convert Condition to dict
                    'wait_time': p.wait_time
                } for p in h.discharged]
            } for h in hospitals
        ]
    }

def validate_encounter_data(encounter):
    """Validate the encounter data structure and ensure required fields exist."""
    required_structure = {
        'type': [{'coding': [{'display': 'Unknown'}]}],
        'status': 'Unknown',
        'priority': {'coding': [{'display': 'Unknown'}]},
        'serviceType': {'coding': [{'display': 'Unknown'}]},
        'diagnosis': [{'condition': {'display': 'Unknown'}}],
        'reasonCode': [{'coding': [{'display': 'Unknown'}]}],
        'procedure': [{'display': 'Unknown'}]
    }
    
    # If encounter is None, return default structure
    if not encounter:
        logging.warning("Received null encounter data, using default structure")
        return required_structure
    
    # Ensure all required fields exist with proper structure
    validated = {}
    try:
        validated['type'] = encounter.get('type', required_structure['type'])
        validated['status'] = encounter.get('status', required_structure['status'])
        validated['priority'] = encounter.get('priority', required_structure['priority'])
        validated['serviceType'] = encounter.get('serviceType', required_structure['serviceType'])
        validated['diagnosis'] = encounter.get('diagnosis', required_structure['diagnosis'])
        validated['reasonCode'] = encounter.get('reasonCode', required_structure['reasonCode'])
        validated['procedure'] = encounter.get('procedure', required_structure['procedure'])
        
        # Copy any additional fields that might exist
        for key in encounter:
            if key not in validated:
                validated[key] = encounter[key]
                
        return validated
        
    except Exception as e:
        logging.error(f"Error validating encounter data: {str(e)}")
        logging.debug(f"Raw encounter data: {encounter}")
        return required_structure


def add_simple_location_to_encounter(encounter, hospital_id):
    """Ensure Encounter.location includes a simple hospital location entry.
    Reference format: Location/hospital{hospital_id}
    """
    try:
        if not isinstance(encounter, dict):
            return encounter
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        location_entry = {
            'location': {
                'reference': f"Location/hospital{hospital_id}",
                'display': f"Hospital {hospital_id} Emergency Department"
            },
            'status': 'active',
            'period': {
                'start': current_time
            }
        }
        # Overwrite or set location to the simple entry to keep consistent
        encounter['location'] = [location_entry]
        return encounter
    except Exception:
        return encounter

class RequestCounter:
    def __init__(self):
        self._count = 0
        self._lock = Lock()
        self._completed = 0

    def increment_started(self):
        with self._lock:
            self._count += 1
            return self._count

    def increment_completed(self):
        with self._lock:
            self._completed += 1
            return self._completed

    def get_counts(self):
        with self._lock:
            return {
                'started': self._count,
                'completed': self._completed
            }

# Add after other global variables
request_counter = RequestCounter()

# Modify process_patient_encounter to track requests
def process_patient_encounter(hospital, patient):
    """Process a patient encounter with LLM if enabled."""
    try:
        if USE_LLM:
            request_counter.increment_started()
            # Get condition description for context
            condition_desc = (f"{patient.condition.code.get('display', 'Unknown condition')} - "
                            f"Severity: {patient.condition.severity.get('display', 'Unknown severity')}")
            
            encounter_dict = generate_encounter_ed_presentation(
                patient_id=patient.id,
                condition_id=patient.condition.id,
                practitioner_id=str(uuid.uuid4()),
                organization_id=f"org-{hospital.id}",
                condition_description=condition_desc,
                llm_model=DEFAULT_LLM_MODEL
            )
            request_counter.increment_completed()
            
            # Save the LLM-generated encounter if FHIR output is enabled
            if OUTPUT_FHIR and SESSION_DIR and encounter_dict:
                try:
                    save_fhir_resource('encounter_ed_presentation', add_simple_location_to_encounter(encounter_dict, hospital.id))
                    logging.info(f"Saved encounter FHIR resource for encounter {encounter_dict.get('id', 'unknown')}")
                except Exception as e:
                    logging.error(f"Error saving encounter FHIR resource: {str(e)}")
            
            if encounter_dict:
                patient.encounters.append(add_simple_location_to_encounter(encounter_dict, hospital.id))
                try:
                    if isinstance(encounter_dict, dict) and encounter_dict.get('id'):
                        patient.latest_encounter_id = encounter_dict.get('id')
                except Exception:
                    pass
                try:
                    log_event(
                        f"ED presentation created for {patient.name} | Hospital {hospital.id}",
                        event_type='hospital',
                        attachments=[{'label': 'ED Presentation', 'json': validate_encounter_data(add_simple_location_to_encounter(encounter_dict, hospital.id))}]
                    )
                except Exception:
                    pass
                return encounter_dict
            
        # Use existing fallback logic if LLM fails or is disabled
        fallback_encounter = generate_fallback_encounter(
            patient_id=patient.id,
            condition_id=patient.condition.id,
            hospital_id=hospital.id
        )
        
        # Save the fallback encounter if FHIR output is enabled
        if OUTPUT_FHIR and SESSION_DIR and fallback_encounter:
            try:
                save_fhir_resource('encounter_ed_presentation', add_simple_location_to_encounter(fallback_encounter, hospital.id))
                logging.info(f"Saved encounter FHIR resource for encounter {fallback_encounter.get('id', 'unknown')}")
            except Exception as e:
                logging.error(f"Error saving encounter FHIR resource: {str(e)}")
            
        if fallback_encounter:
            try:
                try:
                    if isinstance(fallback_encounter, dict) and fallback_encounter.get('id'):
                        patient.latest_encounter_id = fallback_encounter.get('id')
                except Exception:
                    pass
                log_event(
                    f"ED presentation created for {patient.name} | Hospital {hospital.id}",
                    event_type='hospital',
                    attachments=[{'label': 'ED Presentation', 'json': validate_encounter_data(add_simple_location_to_encounter(fallback_encounter, hospital.id))}]
                )
            except Exception:
                pass
        return fallback_encounter
            
    except Exception as e:
        logging.error(f"Error in process_patient_encounter: {str(e)}", exc_info=True)
        return None

def process_patient_discharge(hospital, patient, encounter):
    """Process a patient discharge with LLM if enabled."""
    try:
        if encounter and 'period' in encounter and 'start' in encounter['period']:
            start_time = encounter['period']['start']
            end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            discharge_dict = generate_encounter_discharge(
                encounter_id=encounter['id'],
                start_time=start_time,
                end_time=end_time
            )
            
            if OUTPUT_FHIR:
                save_fhir_resource('encounter_discharge', discharge_dict)
                logging.info(f"Saved encounter discharge FHIR resource")
            
            return discharge_dict
            
    except Exception as e:
        logging.error(f"Error in process_patient_discharge: {str(e)}", exc_info=True)
        return None

def manage_hospital_queues():
    """Manage the movement of patients between hospital queues."""
    # Maintain locks per hospital id, and keep them in sync with the dynamic hospitals list
    hospital_locks = {}
    
    while True:
        # Sync locks with current hospitals (add new, remove stale)
        current_ids = {h.id for h in hospitals}
        for hid in list(hospital_locks.keys()):
            if hid not in current_ids:
                del hospital_locks[hid]
        for h in hospitals:
            if h.id not in hospital_locks:
                hospital_locks[h.id] = Lock()

        for hospital in hospitals:
            lock = hospital_locks.get(hospital.id)
            if lock is None:
                # If races occur during reset, skip this iteration; lock will be available next loop
                continue
            with lock:
                # Process waiting patients
                if hospital.waiting:
                    for patient in hospital.waiting:
                        patient.wait_time += 1
                        
                        if patient.wait_time >= WAITING_TIME and len(hospital.treating) < GLOBAL_MAX_PATIENTS_PER_HOSPITAL:
                            moved_patient = hospital.move_patient_to_treating()
                            if moved_patient:
                                # Use ThreadPoolExecutor to process encounters concurrently
                                patient_generator_pool.submit(process_patient_encounter, hospital, moved_patient)

                # Process treating patients
                for patient in list(hospital.treating):
                    patient.wait_time += 1
                    if patient.wait_time >= TREATING_TIME:
                        discharged_patient = hospital.discharge_patient()
                        if discharged_patient:
                            # Process discharge in thread pool as well
                            patient_generator_pool.submit(
                                generate_discharge_for_patient, 
                                hospital, 
                                discharged_patient
                            )

                # After moving queues, try to offload any ramped ambulances if capacity is available
                ramped = [a for a in ambulances if a.state == 'orange' and a.queue_hospital_id == hospital.id and a.patient]
                while len(hospital.waiting) < HOSPITAL_WAITING_CAPACITY and ramped:
                    amb = ramped.pop(0)
                    hospital.add_patient_to_waiting(amb.patient)
                    log_event(
                        f"Ambulance {amb.id} offloaded patient {amb.patient.name} at Hospital {hospital.id}",
                        event_type='ambulance',
                        attachments=(build_ambulance_event_attachment('offload', ambulance=amb, patient=amb.patient, hospital_id=hospital.id) or []) + (build_location_attachment(hospital.id, 'waiting', amb.patient) or [])
                    )
                    amb.is_available = True
                    amb.state = 'green'
                    amb.patient = None
                    amb.queue_hospital_id = None
                    amb.ramp_since = None
                    amb.redirect_attempted = False

        socketio.emit('update_state', get_state())
        time.sleep(1)

def log_hospital_event(message):
    """Log events specific to hospital operations."""
    log_event(message, event_type='hospital')

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    emit('update_patient_log', patient_event_log)
    emit('update_ambulance_log', ambulance_event_log)
    emit('update_hospital_log', hospital_event_log)
    emit('update_state', get_state())

@socketio.on('create_patient')
def handle_create_patient():
    """Handle button click to create a patient."""
    print('Create Patient event received')  # Debugging output
    generate_random_patient()

@socketio.on('create_patient_at_house')
def handle_create_patient_at_house(data):
    """Handle creating a patient at a specific house when clicked."""
    house_id = data['house_id']
    house = next((h for h in houses if h.id == house_id), None)
    
    if house and not house.patient_ids:
        # Force fallback generation for clicked patients (no Synthea, no LLM)
        patient_data = generate_fallback_patient(SESSION_DIR)
        patient_resource = patient_data.get('patient', {})
        
        # Generate basic condition without LLM
        condition = generate_fallback_condition(patient_resource['id'])
        
        # Create patient object with fallback data
        patient = Patient(
            id=patient_resource['id'],
            name=patient_resource['name'][0]['given'][0],
            condition=condition,
            dob=patient_resource.get('birthDate', 'Unknown'),
            condition_note=condition.note if condition else None,
            fhir_resources=patient_data
        )
        
        # Add patient to simulation
        patients.append(patient)
        house.add_patient(patient.id)
        
        # Log patient creation with attachments
        attachments = []
        try:
            if isinstance(patient_resource, dict) and patient_resource:
                attachments.append({'label': 'Patient', 'json': patient_resource})
        except Exception:
            pass
        try:
            cond_fhir = condition_to_fhir_dict(condition)
            if cond_fhir:
                attachments.append({'label': 'Condition', 'json': cond_fhir})
        except Exception:
            pass

        log_event(
            f"Patient Generated (Fallback): "
            f"ID: {patient.id} | "
            f"Name: {patient.name} | "
            f"Condition: {condition.code.get('display', 'Unknown')} | "
            f"Severity: {condition.severity.get('display', 'Unknown')}",
            event_type='patient',
            attachments=attachments
        )
        
        socketio.emit('update_state', get_state())

def generate_random_patient(llm_model=None):
    """Generate a patient at a random house."""
    random_house = random.choice(houses)
    patient = create_patient(random_house, SESSION_DIR, llm_model)
    if patient:
        socketio.emit('update_state', get_state())

def generate_patients_automatically(llm_model=None):
    """Automatically generate patients at random intervals."""
    while True:
        generate_random_patient(llm_model)
        time.sleep(random.randint(PATIENT_GENERATION_LOWER_BOUND, PATIENT_GENERATION_UPPER_BOUND))  # Random interval between 1 to 5 seconds

def reset_simulation(house_count=None, hospital_count=None, ambulance_count=None, waiting_time=None, treating_time=None, gen_min=None, gen_max=None):
    """Reset the simulation to the provided configuration (or defaults)."""
    global houses, hospitals, ambulances, WAITING_TIME, TREATING_TIME, PATIENT_GENERATION_LOWER_BOUND, PATIENT_GENERATION_UPPER_BOUND

    # Update timings if provided
    if isinstance(waiting_time, int) and waiting_time >= 0:
        WAITING_TIME = waiting_time
    if isinstance(treating_time, int) and treating_time >= 0:
        TREATING_TIME = treating_time
    if isinstance(gen_min, int) and gen_min >= 0:
        PATIENT_GENERATION_LOWER_BOUND = gen_min
    if isinstance(gen_max, int) and gen_max >= 0:
        PATIENT_GENERATION_UPPER_BOUND = gen_max
    if PATIENT_GENERATION_UPPER_BOUND < PATIENT_GENERATION_LOWER_BOUND:
        PATIENT_GENERATION_UPPER_BOUND = PATIENT_GENERATION_LOWER_BOUND

    hc = int(house_count) if house_count is not None else DEFAULT_HOUSES
    hospc = int(hospital_count) if hospital_count is not None else DEFAULT_HOSPITALS
    ambc = int(ambulance_count) if ambulance_count is not None else DEFAULT_AMBULANCES

    # Reinitialize houses
    houses = [House(i, 50, 50 + i * 60) for i in range(max(0, hc))]

    # Reinitialize hospitals
    hospitals = [Hospital(i, 450, 50 + i * 200) for i in range(max(0, hospc))]

    # Reinitialize ambulances
    ambulances = []
    for i in range(max(0, ambc)):
        if not hospitals:
            # place at origin if no hospitals configured
            ambulances.append(Ambulance(i, 0, 0))
        else:
            hospital = hospitals[i % len(hospitals)]
            ambulances.append(Ambulance(i, hospital.x, hospital.y))

    # Clear event logs and notify clients
    try:
        patient_event_log.clear()
        ambulance_event_log.clear()
        hospital_event_log.clear()
        socketio.emit('update_patient_log', patient_event_log)
        socketio.emit('update_ambulance_log', ambulance_event_log)
        socketio.emit('update_hospital_log', hospital_event_log)
    except Exception:
        pass

    # Emit the updated state to all clients
    socketio.emit('update_state', get_state())

@socketio.on('reset_simulation')
def handle_reset_simulation():
    """Handle the reset simulation event from the client."""
    reset_simulation()

@socketio.on('apply_config')
def handle_apply_config(data):
    """Apply runtime configuration from the client splash screen and restart world."""
    try:
        global RAMP_REDIRECT_ENABLED
        house_count = int(data.get('houses', DEFAULT_HOUSES))
        hospital_count = int(data.get('hospitals', DEFAULT_HOSPITALS))
        ambulance_count = int(data.get('ambulances', DEFAULT_AMBULANCES))
        waiting_time = int(data.get('waiting_time', WAITING_TIME))
        treating_time = int(data.get('treating_time', TREATING_TIME))
        gen_min = int(data.get('gen_min', PATIENT_GENERATION_LOWER_BOUND))
        gen_max = int(data.get('gen_max', PATIENT_GENERATION_UPPER_BOUND))
        RAMP_REDIRECT_ENABLED = bool(data.get('ramp_redirect', False))
    except Exception:
        house_count = DEFAULT_HOUSES
        hospital_count = DEFAULT_HOSPITALS
        ambulance_count = DEFAULT_AMBULANCES
        waiting_time = WAITING_TIME
        treating_time = TREATING_TIME
        gen_min = PATIENT_GENERATION_LOWER_BOUND
        gen_max = PATIENT_GENERATION_UPPER_BOUND
        RAMP_REDIRECT_ENABLED = False

    reset_simulation(house_count=house_count,
                     hospital_count=hospital_count,
                     ambulance_count=ambulance_count,
                     waiting_time=waiting_time,
                     treating_time=treating_time,
                     gen_min=gen_min,
                     gen_max=gen_max)

def initialize_fhir_session():
    """Initialize a new session directory for FHIR outputs."""
    global SESSION_DIR
    if not OUTPUT_FHIR:
        return

    try:
        # Create base directory if it doesn't exist
        os.makedirs(FHIR_OUTPUT_DIR, exist_ok=True)
        
        # Create session directory with timestamp
        session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        SESSION_DIR = os.path.join(FHIR_OUTPUT_DIR, f"session_{session_timestamp}")
        os.makedirs(SESSION_DIR, exist_ok=True)
        # Remove this line that creates the 'fhir' subdirectory
        # os.makedirs(os.path.join(SESSION_DIR, 'fhir'), exist_ok=True)
        
        logging.info(f"Initialized FHIR output session at {SESSION_DIR}")
    except Exception as e:
        logging.error(f"Error initializing FHIR session directory: {str(e)}")
        SESSION_DIR = None

def save_fhir_resource(resource_type, resource):
    """Save a FHIR resource to a JSON file if OUTPUT_FHIR is enabled."""
    if not OUTPUT_FHIR or SESSION_DIR is None:
        return

    try:
        # Create resource type directory within session directory
        resource_dir = os.path.join(SESSION_DIR, resource_type.lower())
        os.makedirs(resource_dir, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        resource_id = resource.get('id', 'unknown')
        filename = f"{resource_type.lower()}_{resource_id}_{timestamp}.json"
        
        # Save the resource
        filepath = os.path.join(resource_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(resource, f, indent=2)
            
        logging.debug(f"Saved FHIR resource to {filepath}")
    except Exception as e:
        logging.error(f"Error saving FHIR resource: {str(e)}")

# Add at the top of the file with other imports
file_operation_lock = Lock()

def log_llm_stats():
    """Log LLM request statistics periodically and emit to frontend."""
    while True:
        counts = request_counter.get_counts()
        logging.info(f"LLM Requests - Started: {counts['started']}, Completed: {counts['completed']}")
        
        # Emit stats to frontend using the correct IDs
        socketio.emit('update_request_counts', {
            'requests_made': counts['started'],
            'requests_completed': counts['completed']
        })
        
        time.sleep(1)  # Update every second

if __name__ == '__main__':
    parser = ArgumentParser(description='Run the ambulance simulation')
    parser.add_argument('--llm-model', type=str, default=DEFAULT_LLM_MODEL,
                       help=f'LLM model to use (default: {DEFAULT_LLM_MODEL})')
    parser.add_argument('--no-llm', action='store_true',
                       help='Run simulation without LLM integration')
    parser.add_argument('--output-fhir', '--fhir-export', action='store_true',
                       help='Output FHIR resources as JSON files')
    
    args = parser.parse_args()
    
    # Update global flags
    USE_LLM = not args.no_llm
    OUTPUT_FHIR = args.output_fhir
    
    if OUTPUT_FHIR:
        initialize_fhir_session()  # Initialize the global session directory
        logging.info(f"FHIR resources will be saved to {SESSION_DIR}/")
    
    if USE_LLM:
        logging.info(f"Running simulation with LLM")
    
    # Register shutdown handler for thread pool
    atexit.register(lambda: patient_generator_pool.shutdown(wait=True))
    
    # Start background threads with specified model
    Thread(target=lambda: generate_patients_automatically(args.llm_model)).start()
    Thread(target=move_ambulances).start()
    Thread(target=manage_hospital_queues).start()
    
    if USE_LLM:
        Thread(target=log_llm_stats, daemon=True).start()
    
    socketio.run(app)
