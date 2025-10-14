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

app = Flask(__name__)
socketio = SocketIO(app)

# Configurable variables
GLOBAL_MAX_PATIENTS_PER_HOSPITAL = 2  # Maximum patients that can be treated simultaneously in each hospital
WAITING_TIME = 2  # seconds
TREATING_TIME = 40  # seconds
DEFAULT_LLM_MODEL = 'llama3.1:8b'  # Default LLM model to use
PATIENT_GENERATION_LOWER_BOUND = 5  # Lower bound for patient generation delay
PATIENT_GENERATION_UPPER_BOUND = 10  # Upper bound for patient generation delay
USE_LLM = True  # Default value, will be updated by command line args
OUTPUT_FHIR = False  # Default value, will be updated by command line args
FHIR_OUTPUT_DIR = "fhir_export"  # Base directory for FHIR outputs
SESSION_DIR = None  # Will be set at runtime if OUTPUT_FHIR is True
HOSPITAL_WAITING_CAPACITY = 6  # Maximum patients allowed in a hospital waiting room

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
        log_event(f"{patient.name} has arrived at Hospital {self.id} and entered waiting queue", event_type='hospital')

    def move_patient_to_treating(self):
        if self.waiting and len(self.treating) < GLOBAL_MAX_PATIENTS_PER_HOSPITAL:
            patient = self.waiting.pop(0)  # Remove the first patient from the waiting queue
            self.treating.append(patient)
            patient.wait_time = 0  # Reset wait time
            return patient
        return None

    def discharge_patient(self):
        """Move patient from treating to discharged queue."""
        if self.treating:
            patient = self.treating.pop(0)  # Remove from treating queue
            self.discharged.append(patient)  # Add to discharged queue
            
            # Add log event for patient moving to discharged list
            discharge_details = (
                f"{patient.name} moved to discharged list | "
                f"Hospital {self.id} | "
                f"Condition: {patient.condition.code.get('display', 'Unknown')} | "
                f"Treatment duration: {patient.wait_time} seconds"
            )
            log_event(discharge_details, event_type='hospital')
            
            return patient
        return None

def calculate_distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

# Set the number of houses to 10 and hospitals to 3
houses = [House(i, 50, 50 + i * 60) for i in range(10)]
hospitals = [Hospital(i, 450, 50 + i * 200) for i in range(3)]

# Initialize ambulances at the hospitals, equally distributed
ambulances = []
for i in range(5):
    hospital = hospitals[i % len(hospitals)]  # Distribute ambulances evenly across hospitals
    ambulances.append(Ambulance(i, hospital.x, hospital.y))

# Initialize separate event logs
patient_event_log = []
ambulance_event_log = []
hospital_event_log = []

def log_event(message, event_type='general'):
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_message = f"{timestamp} - {message}"
    
    if event_type == 'patient':
        patient_event_log.insert(0, log_message)
        if len(patient_event_log) > 10:
            patient_event_log.pop()
        socketio.emit('update_patient_log', patient_event_log)
    elif event_type == 'ambulance':
        ambulance_event_log.insert(0, log_message)
        if len(ambulance_event_log) > 10:
            ambulance_event_log.pop()
        socketio.emit('update_ambulance_log', ambulance_event_log)
    elif event_type == 'hospital':
        hospital_event_log.insert(0, log_message)
        if len(hospital_event_log) > 10:
            hospital_event_log.pop()
        socketio.emit('update_hospital_log', hospital_event_log)
    else:
        # General log or other types can be handled here
        pass

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
            
            # Add discharge event logging
            discharge_summary = (
                f"{patient.name} discharged from Hospital {hospital.id} | "
                f"Condition: {patient.condition.code.get('display', 'Unknown')} | "
                f"Total time in hospital: {patient.wait_time} seconds"
            )
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
            condition = Condition(
                id=str(uuid.uuid4()),
                clinical_status={'code': 'active', 'display': 'Active'},
                verification_status={'code': 'confirmed', 'display': 'Confirmed'},
                severity={'code': 'moderate', 'display': 'Moderate'},
                category={'code': 'problem-list-item', 'display': 'Problem List Item'},
                code={'code': 'generic', 'display': 'Generic Condition'},
                subject_reference=f"Patient/{patient_resource['id']}",
                onset_datetime=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                recorded_date=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                note="Basic fallback condition"
            )
            logging.info("Created basic fallback condition")
        
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
        
        log_event(" | ".join(log_parts), event_type='patient')
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
                        log_event(f"Ambulance {closest_ambulance.id} is heading to House {house.id} to pick up {patient.name}", event_type='ambulance')
                    else:
                        log_event(f"No patient found at House {house.id}", event_type='ambulance')

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
                            patient_house.ambulance_on_the_way = False  # Reset ambulance flag
                            log_event(f"House {patient_house.id} is now empty and reverts to green.", event_type='ambulance')
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
                                log_event(f"Ambulance {next_ambulance.id} is heading to House {patient_house.id} to pick up Patient {next_ambulance.patient.id}", event_type='ambulance')
                            else:
                                patient_house.ambulance_on_the_way = False  # No available ambulances
                        nearest_hospital = find_nearest_hospital(ambulance.x, ambulance.y)
                        ambulance.target = (nearest_hospital.x, nearest_hospital.y)
                        ambulance.state = 'yellow'  # Has patient, heading to hospital
                        ambulance.ramp_since = None
                        log_event(f"Ambulance {ambulance.id} picked up {ambulance.patient.name} from House {patient_house.id} and is heading to Hospital {nearest_hospital.id}", event_type='ambulance')
                    elif ambulance.x == ambulance.target[0] and ambulance.y == ambulance.target[1]:
                        # If ambulance reached the hospital
                        nearest_hospital = find_nearest_hospital(ambulance.x, ambulance.y)
                        patient = next((p for p in patients if p.id == ambulance.patient.id), None)
                        if patient:
                            # If waiting room has capacity, drop patient; otherwise ramp outside
                            if len(nearest_hospital.waiting) < HOSPITAL_WAITING_CAPACITY:
                                nearest_hospital.add_patient_to_waiting(patient)
                                ambulance.is_available = True
                                ambulance.state = 'green'
                                ambulance.target = None
                                ambulance.patient = None
                                ambulance.queue_hospital_id = None
                            else:
                                # Ramp: keep patient on board, mark ambulance waiting outside
                                ambulance.is_available = False
                                ambulance.state = 'orange'
                                ambulance.queue_hospital_id = nearest_hospital.id
                                ambulance.ramp_since = time.time()
                                log_event(
                                    f"Ambulance {ambulance.id} waiting to offload at Hospital {nearest_hospital.id} (waiting full)",
                                    event_type='ambulance'
                                )

        socketio.emit('update_state', get_state())
        time.sleep(0.05)  # Reduce the sleep time to make the simulation feel faster

def find_nearest_hospital(x, y):
    """Find the nearest hospital to the given coordinates."""
    nearest_hospital = min(hospitals, key=lambda h: calculate_distance(x, y, h.x, h.y))
    return nearest_hospital

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
                    save_fhir_resource('encounter_ed_presentation', encounter_dict)
                    logging.info(f"Saved encounter FHIR resource for encounter {encounter_dict.get('id', 'unknown')}")
                except Exception as e:
                    logging.error(f"Error saving encounter FHIR resource: {str(e)}")
            
            if encounter_dict:
                patient.encounters.append(encounter_dict)
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
                save_fhir_resource('encounter_ed_presentation', fallback_encounter)
                logging.info(f"Saved encounter FHIR resource for encounter {fallback_encounter.get('id', 'unknown')}")
            except Exception as e:
                logging.error(f"Error saving encounter FHIR resource: {str(e)}")
            
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
    hospital_locks = {hospital.id: Lock() for hospital in hospitals}  # Individual locks per hospital
    
    while True:
        for hospital in hospitals:
            with hospital_locks[hospital.id]:
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
                    log_event(f"Ambulance {amb.id} offloaded patient {amb.patient.name} at Hospital {hospital.id}", event_type='ambulance')
                    amb.is_available = True
                    amb.state = 'green'
                    amb.patient = None
                    amb.queue_hospital_id = None
                    amb.ramp_since = None

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
        
        # Log patient creation
        log_event(
            f"Patient Generated (Fallback): "
            f"ID: {patient.id} | "
            f"Name: {patient.name} | "
            f"Condition: {condition.code.get('display', 'Unknown')} | "
            f"Severity: {condition.severity.get('display', 'Unknown')}",
            event_type='patient'
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

def reset_simulation():
    """Reset the simulation to its initial state."""
    global houses, hospitals, ambulances, event_log

    # Reinitialize houses
    houses = [House(i, 50, 50 + i * 60) for i in range(10)]

    # Reinitialize hospitals
    hospitals = [Hospital(i, 450, 50 + i * 200) for i in range(3)]

    # Reinitialize ambulances
    ambulances = []
    for i in range(5):
        hospital = hospitals[i % len(hospitals)]
        ambulances.append(Ambulance(i, hospital.x, hospital.y))

    # Clear event log
    event_log = []

    # Emit the updated state to all clients
    socketio.emit('update_state', get_state())
    socketio.emit('update_log', event_log)

@socketio.on('reset_simulation')
def handle_reset_simulation():
    """Handle the reset simulation event from the client."""
    reset_simulation()

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
