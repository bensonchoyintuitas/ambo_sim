from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import time
from threading import Thread, Lock
import math
from datetime import datetime, timezone
import json
from generate_synthea_patient import generate_fhir_resources  # Update this import
import uuid
import logging
from ai.generate_condition import generate_condition
from ai.generate_encounter import generate_encounter
from ai.generate_encounter_discharge import generate_discharge
from concurrent.futures import ThreadPoolExecutor
import functools

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
GLOBAL_MAX_PATIENTS_PER_HOSPITAL = 4  # Maximum patients that can be treated simultaneously in each hospital
WAITING_TIME = 2  # seconds
TREATING_TIME = 40  # seconds
DEFAULT_LLM_MODEL = 'llama3.1:8b'  # Default LLM model to use
PATIENT_GENERATION_LOWER_BOUND = 0  # Lower bound for patient generation delay
PATIENT_GENERATION_UPPER_BOUND = 1  # Upper bound for patient generation delay

class Condition:
    def __init__(self, id, clinical_status, verification_status, severity, category, 
                 code, subject_reference, onset_datetime, recorded_date, note):
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
        return cls(
            id=fhir_condition.get('id'),
            clinical_status=fhir_condition.get('clinicalStatus', {}).get('coding', [{}])[0],
            verification_status=fhir_condition.get('verificationStatus', {}).get('coding', [{}])[0],
            severity=fhir_condition.get('severity', {}).get('coding', [{}])[0],
            category=fhir_condition.get('category', [{}])[0].get('coding', [{}])[0],
            code=fhir_condition.get('code', {}).get('coding', [{}])[0],
            subject_reference=fhir_condition.get('subject', {}).get('reference'),
            onset_datetime=fhir_condition.get('onsetDateTime'),
            recorded_date=fhir_condition.get('recordedDate'),
            note=fhir_condition.get('note', [{}])[0].get('text')
        )

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

def generate_fallback_patient(house):
    """Generate a basic patient when FHIR generation fails."""
    patient_id = f"pat-{random.randint(1000, 9999)}"
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Create a basic fallback condition
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
        severity={
            "system": "http://snomed.info/sct",
            "code": "24484000",
            "display": "Severe"
        },
        category={
            "system": "http://terminology.hl7.org/CodeSystem/condition-category",
            "code": "encounter-diagnosis",
            "display": "Encounter Diagnosis"
        },
        code={
            "system": "http://snomed.info/sct",
            "code": "427623005",
            "display": "Ambulatory patient"
        },
        subject_reference=f"Patient/{patient_id}",
        onset_datetime=current_time,
        recorded_date=current_time,
        note="Emergency presentation (fallback patient)"
    )
    
    # Create patient with Condition object, not string
    patient = Patient(
        id=patient_id,
        name=f"Patient-{patient_id[-4:]}",
        condition=condition,  # Pass the Condition object here
        fhir_resources={}
    )
    
    patients.append(patient)
    house.add_patient(patient.id)
    
    log_message = (
        f"New fallback patient generated - "
        f"ID: {patient_id}, "
        f"Name: {patient.name}, "
        f"Condition: {condition.code['display']}, "
        f"Severity: {condition.severity['display']}"
    )
    log_event(log_message, event_type='patient')
    socketio.emit('update_state', get_state())
    return patient

# Add thread pool for parallel patient generation
patient_generator_pool = ThreadPoolExecutor(max_workers=8)

def generate_random_patient(llm_model=None):
    """Generate a patient at a random house with FHIR resources."""
    llm_model = llm_model or DEFAULT_LLM_MODEL
    random_house = random.choice(houses)
    
    try:
        logging.info("Generating FHIR resources...")
        fhir_resources = generate_fhir_resources()
        
        if not fhir_resources:
            logging.error("Failed to generate FHIR resources - falling back to basic patient")
            return generate_fallback_patient(random_house)
            
        patient_resource = fhir_resources.get('patient')
        if not patient_resource:
            raise ValueError("No patient resource generated")
            
        patient_id = patient_resource.get('id')
        
        # Track LLM request for condition generation
        request_counter.increment_requests()
        condition_fhir = generate_condition(patient_id, llm_model=llm_model)
        request_counter.increment_completed()
        
        if condition_fhir:
            condition = Condition.from_fhir(condition_fhir)
            
            # Extract patient information
            name_data = patient_resource.get('name', [{}])[0]
            given_name = name_data.get('given', [''])[0] if name_data.get('given') else ''
            family_name = name_data.get('family', '')
            full_name = given_name or "Unknown Patient"  # Use just the given (first) name
            
            # Create patient object
            patient = Patient(
                id=patient_id,
                name=full_name,  # This will now be just the first name
                condition=condition,
                dob=patient_resource.get('birthDate'),
                fhir_resources=fhir_resources
            )
            
            patients.append(patient)
            random_house.add_patient(patient.id)
            
            # Create detailed log message
            log_parts = [
                f"New Patient Generated:",
                f"ID: {patient_id}",
                f"Name: {full_name}",
                f"Condition: {condition.code.get('display', 'Unknown')}",
                f"Severity: {condition.severity.get('display', 'Unknown')}",
                f"Clinical Status: {condition.clinical_status.get('display', 'Unknown')}"
            ]
            
            if condition.note:
                log_parts.append(f"Notes: {condition.note}")
                
            log_event(" | ".join(log_parts), event_type='patient')
            socketio.emit('update_state', get_state())
            return patient
            
        else:
            logging.error("Failed to generate condition - falling back to basic patient")
            return generate_fallback_patient(random_house)
        
    except Exception as e:
        logging.error(f"Error in generate_random_patient: {str(e)}")
        return generate_fallback_patient(random_house)

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
                        log_event(f"Ambulance {ambulance.id} picked up {ambulance.patient.name} from House {patient_house.id} and is heading to Hospital {nearest_hospital.id}", event_type='ambulance')
                    elif ambulance.x == ambulance.target[0] and ambulance.y == ambulance.target[1]:
                        # If ambulance reached the hospital
                        nearest_hospital = find_nearest_hospital(ambulance.x, ambulance.y)
                        patient = next((p for p in patients if p.id == ambulance.patient.id), None)
                        if patient:
                            nearest_hospital.add_patient_to_waiting(patient)
                        ambulance.is_available = True
                        ambulance.state = 'green'
                        ambulance.target = None
                        ambulance.patient = None

        socketio.emit('update_state', get_state())
        time.sleep(0.05)  # Reduce the sleep time to make the simulation feel faster

def find_nearest_hospital(x, y):
    """Find the nearest hospital to the given coordinates."""
    nearest_hospital = min(hospitals, key=lambda h: calculate_distance(x, y, h.x, h.y))
    return nearest_hospital

def get_state():
    """Returns the state of ambulances, houses, and hospitals."""
    return {
        'ambulances': [{'id': a.id, 'x': a.x, 'y': a.y, 'state': a.state, 'patient_id': a.patient.id if a.patient else None} for a in ambulances],
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
        self.requests_made = 0
        self.requests_completed = 0
        self.lock = Lock()
    
    def increment_requests(self):
        with self.lock:
            self.requests_made += 1
            self.emit_counts()
    
    def increment_completed(self):
        with self.lock:
            self.requests_completed += 1
            self.emit_counts()
    
    def emit_counts(self):
        socketio.emit('update_request_counts', {
            'requests_made': self.requests_made,
            'requests_completed': self.requests_completed
        })

request_counter = RequestCounter()

# Modify process_patient_encounter to track requests
def process_patient_encounter(hospital, patient):
    """Process a single patient encounter with the LLM"""
    try:
        condition_description = (
            f"Patient presents with {patient.condition.code.get('display', 'Unknown condition')}. "
            f"Severity: {patient.condition.severity.get('display', 'Unknown severity')}. "
            f"Clinical Status: {patient.condition.clinical_status.get('display', 'Unknown status')}. "
            f"Notes: {patient.condition.note or 'No additional notes'}"
        )

        log_event(f"Encounter commenced - information is being gathered for {patient.name}", event_type='hospital')
        request_counter.increment_requests()  # Increment requests
        
        encounter = generate_encounter(
            patient_id=patient.id,
            condition_id=patient.condition.id,
            practitioner_id=f"pract-{str(uuid.uuid4())[:8]}", 
            organization_id=f"org-{hospital.id}",
            condition_description=condition_description,
            llm_model=DEFAULT_LLM_MODEL
        )
        
        encounter = validate_encounter_data(encounter)
        patient.encounters.append(encounter)
        request_counter.increment_completed()  # Increment completed
        
        # Create summary from encounter data
        diagnosis = encounter['diagnosis'][0]['condition']['display']
        procedure = encounter['procedure'][0]['display']
        encounter_type = encounter['type'][0]['coding'][0]['display']
        
        summary = (
            f"Encounter documented for {patient.name}: "
            f"Diagnosed with {diagnosis}, "
            f"Procedure performed: {procedure}, "
            f"Visit type: {encounter_type}"
        )
        log_event(summary, event_type='hospital')
            
    except Exception as e:
        logging.error(f"Error processing encounter for {patient.name}: {str(e)}")
        log_event(f"Error documenting encounter for {patient.name}", event_type='hospital')

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

        socketio.emit('update_state', get_state())
        time.sleep(1)

# Add this helper function
def generate_discharge_for_patient(hospital, patient):
    """Process discharge for a single patient"""
    try:
        if patient.encounters:
            original_encounter = patient.encounters[-1]
            start_time = original_encounter['period']['start']
            end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            discharge = generate_discharge(
                encounter_id=original_encounter['id'],
                start_time=start_time,
                end_time=end_time
            )
            
            patient.encounters.append(discharge)
            
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
    """Handle creating a patient at a specific house when the house is clicked."""
    house_id = data['house_id']
    house = next((h for h in houses if h.id == house_id), None)

    if house and not house.patient_ids:
        patient_id = f"pat-{random.randint(1000, 9999)}"
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Create a proper Condition object
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
            severity={
                "system": "http://snomed.info/sct",
                "code": "24484000",
                "display": "Severe"
            },
            category={
                "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                "code": "encounter-diagnosis",
                "display": "Encounter Diagnosis"
            },
            code={
                "system": "http://snomed.info/sct",
                "code": "427623005",
                "display": "Manual Entry Patient"
            },
            subject_reference=f"Patient/{patient_id}",
            onset_datetime=current_time,
            recorded_date=current_time,
            note="Manually created patient"
        )
        
        patient = Patient(patient_id, f"Patient-{patient_id[-4:]}", condition)
        patients.append(patient)
        house.add_patient(patient.id)
        log_event(f"Patient {patient.id} created at House {house.id}", event_type='patient')
        socketio.emit('update_state', get_state())

def generate_patients_automatically(llm_model=None):
    """Automatically generate patients at random intervals."""
    while True:
        generate_random_patient(llm_model)
        time.sleep(random.randint(PATIENT_GENERATION_LOWER_BOUND, PATIENT_GENERATION_UPPER_BOUND))  # Random interval between 1 to 5 seconds

# Start background threads for simulation
Thread(target=lambda: generate_patients_automatically(DEFAULT_LLM_MODEL)).start()
Thread(target=move_ambulances).start()
Thread(target=manage_hospital_queues).start()

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

if __name__ == '__main__':
    import argparse
    import atexit
    
    parser = argparse.ArgumentParser(description='Run the ambulance simulation')
    parser.add_argument('--llm-model', type=str, default=DEFAULT_LLM_MODEL,
                       help=f'LLM model to use (default: {DEFAULT_LLM_MODEL})')
    
    args = parser.parse_args()
    
    # Register shutdown handler for thread pool
    atexit.register(lambda: patient_generator_pool.shutdown(wait=True))
    
    # Start background threads with specified model
    Thread(target=lambda: generate_patients_automatically(args.llm_model)).start()
    Thread(target=move_ambulances).start()
    Thread(target=manage_hospital_queues).start()
    
    socketio.run(app)
