from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import time
from threading import Thread, Lock
import math
from datetime import datetime, timezone
import json
from generate_synthea_patient import generate_fhir_resources
import uuid
from ai.generate_encounter import generate_encounter
from ai.generate_encounter_discharge import generate_discharge
import logging
from ai.generate_condition import generate_condition
from concurrent.futures import ThreadPoolExecutor
import functools

app = Flask(__name__)
socketio = SocketIO(app)

# Add thread pool for parallel patient generation
patient_generator_pool = ThreadPoolExecutor(max_workers=8)  # Adjust workers based on your Ollama capacity

# Configurable variables
MAX_TREATING = 2
WAITING_TIME = 1  # seconds
TREATING_TIME = 30  # seconds
PATIENT_GENERATION_LOWER_BOUND = 0  # Lower bound for patient generation delay
PATIENT_GENERATION_UPPER_BOUND = 1  # Upper bound for patient generation delay
DEFAULT_LLM_MODEL = 'llama3.1:8b'  # Default LLM model to use

# Setup logging at the top of your file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simulation.log'),
        logging.StreamHandler()  # This will print to console too
    ]
)

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

class Patient:
    def __init__(self, id, name, condition=None, dob=None, fhir_resources=None):
        self.id = id
        self.name = name
        self.condition = condition  # This will now be a Condition object
        self.dob = dob
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
        self.patient = None
        self.speed = 2  # Reduced speed for smoother movement

    def move_to(self, target_x, target_y):
        # Calculate direction vector
        dx = target_x - self.x
        dy = target_y - self.y
        
        # Calculate distance to target
        distance = math.sqrt(dx**2 + dy**2)
        
        if distance > 0:
            # Normalize direction vector and multiply by speed
            dx = (dx / distance) * self.speed
            dy = (dy / distance) * self.speed
            
            # Update position
            self.x += dx
            self.y += dy

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
        self.waiting.append(patient)  # Ensure patient object is added

    def move_patient_to_treating(self):
        if self.waiting and len(self.treating) < MAX_TREATING:
            patient = self.waiting.pop(0)  # Remove the first patient from the waiting queue
            self.treating.append(patient)
            patient.wait_time = 0  # Reset wait time
            return patient
        return None

    def discharge_patient(self):
        if self.treating:
            patient = self.treating.pop(0)  # Remove the first patient from the treating queue
            self.discharged.append(patient)
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
        
        # Extract detailed patient information
        name_data = patient_resource.get('name', [{}])[0]
        given_name = name_data.get('given', [''])[0] if name_data.get('given') else ''
        family_name = name_data.get('family', '')
        full_name = f"{given_name} {family_name}".strip() or "Unknown Patient"
        
        # Extract additional demographics
        gender = patient_resource.get('gender', 'unknown')
        birth_date = patient_resource.get('birthDate', 'unknown')
        marital_status = patient_resource.get('maritalStatus', {}).get('text', 'unknown')
        
        # Get contact details if available
        telecom = patient_resource.get('telecom', [])
        phone = next((t.get('value') for t in telecom if t.get('system') == 'phone'), 'unknown')
        
        # Get address if available
        address = patient_resource.get('address', [{}])[0]
        address_str = ', '.join(filter(None, [
            address.get('line', [''])[0],
            address.get('city', ''),
            address.get('state', ''),
            address.get('postalCode', '')
        ])) or 'unknown'

        # Generate condition with more detail
        condition_fhir = generate_condition(patient_id, llm_model=llm_model)
        
        if condition_fhir:
            condition = Condition.from_fhir(condition_fhir)
            
            # Create detailed log message
            log_parts = [
                f"New Patient Generated:",
                f"ID: {patient_id}",
                f"Name: {full_name}",
                f"Gender: {gender.capitalize()}",
                f"DOB: {birth_date}",
                f"Marital Status: {marital_status}",
                f"Phone: {phone}",
                f"Address: {address_str}",
                f"Condition: {condition.code.get('display', 'Unknown')}",
                f"Severity: {condition.severity.get('display', 'Unknown')}",
                f"Clinical Status: {condition.clinical_status.get('display', 'Unknown')}",
                f"Category: {condition.category.get('display', 'Unknown')}"
            ]
            
            if condition.note:
                log_parts.append(f"Notes: {condition.note}")
                
            log_event(" | ".join(log_parts), event_type='patient')
            
            # Create and store patient object
            patient = Patient(
                id=patient_id,
                name=full_name,
                condition=condition,
                dob=birth_date,
                fhir_resources=fhir_resources
            )
            
            patients.append(patient)
            random_house.add_patient(patient.id)
            socketio.emit('update_state', get_state())
            return patient
            
        else:
            logging.error("Failed to generate condition - falling back to basic patient")
            return generate_fallback_patient(random_house)
        
    except Exception as e:
        logging.error(f"Error in generate_random_patient: {str(e)}")
        return generate_fallback_patient(random_house)

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
    
    patient = Patient(
        id=patient_id,
        name=f"Patient-{patient_id[-4:]}",
        condition=condition,
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

def move_ambulances():
    """Update ambulance positions and handle pickups/dropoffs."""
    while True:
        for ambulance in ambulances:
            if ambulance.target:
                # Calculate target coordinates based on target type
                target_x = ambulance.target.x
                target_y = ambulance.target.y
                
                # Move ambulance towards target
                ambulance.move_to(target_x, target_y)
                
                # Check if ambulance has reached target (within small distance)
                distance = calculate_distance(ambulance.x, ambulance.y, target_x, target_y)
                
                if distance < 2:  # Reduced threshold for smoother stops
                    if isinstance(ambulance.target, House) and ambulance.is_available:
                        # Handle pickup
                        if ambulance.target.patient_ids:
                            patient_id = ambulance.target.patient_ids[0]
                            patient = next((p for p in patients if p.id == patient_id), None)
                            if patient:
                                ambulance.patient = patient
                                ambulance.is_available = False
                                ambulance.state = 'red'  # red means carrying patient
                                ambulance.target.patient_ids.remove(patient_id)
                                ambulance.target.ambulance_on_the_way = False
                                
                                # Find nearest hospital
                                nearest_hospital = min(hospitals, 
                                    key=lambda h: calculate_distance(ambulance.x, ambulance.y, h.x, h.y))
                                ambulance.target = nearest_hospital
                                
                                log_event(f"Ambulance {ambulance.id} picked up {patient.name} from House {ambulance.target.id}", 
                                        event_type='ambulance')
                    
                    elif isinstance(ambulance.target, Hospital) and not ambulance.is_available:
                        # Handle dropoff
                        if ambulance.patient:
                            hospital = ambulance.target
                            patient = ambulance.patient
                            
                            hospital.add_patient_to_waiting(patient)
                            
                            # Log to both ambulance and hospital logs
                            log_event(f"Ambulance {ambulance.id} dropped off {patient.name} at Hospital {hospital.id}", 
                                    event_type='ambulance')
                            log_event(f"{patient.name} has arrived and is waiting at Hospital {hospital.id}", 
                                    event_type='hospital')
                            
                            ambulance.patient = None
                            ambulance.is_available = True
                            ambulance.state = 'green'
                            ambulance.target = None
                            
                            # Reset ambulance position to hospital
                            ambulance.x = hospital.x
                            ambulance.y = hospital.y

        socketio.emit('update_state', get_state())
        time.sleep(0.016)  # Approximately 60 FPS for smoother animation

def assign_ambulance():
    """Assign available ambulances to houses with patients."""
    while True:
        # Find houses with patients and no ambulance assigned
        for house in houses:
            if house.patient_ids and not house.ambulance_on_the_way:
                # Find nearest available ambulance
                available_ambulances = [a for a in ambulances if a.is_available and not a.target]
                if available_ambulances:
                    nearest_ambulance = min(available_ambulances,
                        key=lambda a: calculate_distance(a.x, a.y, house.x, house.y))
                    
                    # Assign ambulance to house
                    nearest_ambulance.target = house
                    house.ambulance_on_the_way = True
                    
                    # Get patient for logging
                    patient = next((p for p in patients if p.id in house.patient_ids), None)
                    if patient:
                        log_event(f"Ambulance {nearest_ambulance.id} assigned to pick up {patient.name} from House {house.id}", 
                                event_type='ambulance')
        
        time.sleep(1)

def find_nearest_hospital(x, y):
    """Find the nearest hospital to the given coordinates."""
    nearest_hospital = min(hospitals, key=lambda h: calculate_distance(x, y, h.x, h.y))
    return nearest_hospital

def get_state():
    """Returns the state of ambulances, houses, and hospitals."""
    return {
        'ambulances': [{'id': a.id, 'x': a.x, 'y': a.y, 'state': a.state, 
                       'patient_id': a.patient.id if a.patient else None} for a in ambulances],
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
                    'condition': p.condition.code.get('display') if p.condition else 'Unknown',
                    'severity': p.condition.severity.get('display') if p.condition else 'Unknown',
                    'wait_time': p.wait_time
                } for p in h.waiting],
                'treating': [{
                    'id': p.id,
                    'name': p.name,
                    'condition': p.condition.code.get('display') if p.condition else 'Unknown',
                    'severity': p.condition.severity.get('display') if p.condition else 'Unknown',
                    'wait_time': p.wait_time
                } for p in h.treating],
                'discharged': [{
                    'id': p.id,
                    'name': p.name,
                    'condition': p.condition.code.get('display') if p.condition else 'Unknown',
                    'severity': p.condition.severity.get('display') if p.condition else 'Unknown',
                    'wait_time': p.wait_time
                } for p in h.discharged]
            } for h in hospitals
        ],
        'patients': [{
            'id': p.id,
            'name': p.name,
            'condition': p.condition.code.get('display') if p.condition else 'Unknown',
            'severity': p.condition.severity.get('display') if p.condition else 'Unknown'
        } for p in patients]
    }

def manage_hospital_queues():
    """Manage the movement of patients between hospital queues."""
    hospital_lock = Lock()

    while True:
        for hospital in hospitals:
            with hospital_lock:
                # Update wait times for patients in the waiting queue
                if hospital.waiting:
                    hospital.waiting[0].wait_time += 1

                # Move patient to treating if wait time exceeds WAITING_TIME and there's space
                if hospital.waiting and hospital.waiting[0].wait_time >= WAITING_TIME and len(hospital.treating) < MAX_TREATING:
                    moved_patient = hospital.move_patient_to_treating()
                    if moved_patient:
                        try:
                            # Extract condition details for the prompt
                            condition_description = (
                                f"Patient presents with {moved_patient.condition.code.get('display', 'Unknown condition')}. "
                                f"Severity: {moved_patient.condition.severity.get('display', 'Unknown severity')}. "
                                f"Clinical Status: {moved_patient.condition.clinical_status.get('display', 'Unknown status')}. "
                                f"Notes: {moved_patient.condition.note or 'No additional notes'}"
                            )

                            condition_display = moved_patient.condition.code.get('display', 'Unknown condition')
                            
                            encounter = generate_encounter(
                                patient_id=moved_patient.id,
                                condition_id=condition_display,
                                practitioner_id=f"pract-{str(uuid.uuid4())[:8]}", 
                                organization_id=f"org-{hospital.id}",
                                condition_description=condition_description,
                                llm_model=DEFAULT_LLM_MODEL
                            )
                            
                            if encounter:
                                moved_patient.encounters.append(encounter)
                                
                                # Create detailed encounter log
                                encounter_details = [
                                    f"New Encounter for {moved_patient.name} at Hospital {hospital.id}",
                                    f"Encounter Type: {encounter['type'][0]['coding'][0]['display']}",
                                    f"Status: {encounter['status']}",
                                    f"Priority: {encounter.get('priority', {}).get('coding', [{}])[0].get('display', 'Unknown')}",
                                    f"Service Type: {encounter.get('serviceType', {}).get('coding', [{}])[0].get('display', 'Unknown')}",
                                    f"Diagnosis: {encounter.get('diagnosis', [{}])[0].get('condition', {}).get('display', 'Unknown')}",
                                    f"Reason: {encounter['reasonCode'][0]['coding'][0]['display']}",
                                    f"Procedure: {encounter['procedure'][0]['display']}"
                                ]
                                
                                # Add any additional notes if present
                                if 'note' in encounter:
                                    encounter_details.append(f"Notes: {encounter['note'][0]['text']}")
                                    
                                log_event(" | ".join(encounter_details), event_type='hospital')
                                
                            log_event(f"{moved_patient.name} moved to treating at Hospital {hospital.id}", event_type='hospital')
                            
                        except Exception as e:
                            print(f"Error generating encounter: {str(e)}")
                            log_event(f"Failed to generate encounter for {moved_patient.name}", event_type='hospital')

                # Update treating times and handle discharges
                for patient in list(hospital.treating):  # Create a copy of the list to safely modify it
                    patient.wait_time += 1
                    if patient.wait_time >= TREATING_TIME:
                        discharged_patient = hospital.discharge_patient()
                        if discharged_patient:
                            try:
                                if discharged_patient.encounters:
                                    original_encounter = discharged_patient.encounters[-1]
                                    start_time = original_encounter['period']['start']
                                    end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                                    
                                    discharge = generate_discharge(
                                        encounter_id=original_encounter['id'],
                                        start_time=start_time,
                                        end_time=end_time
                                    )
                                    
                                    discharged_patient.encounters.append(discharge)
                                    
                                    discharge_details = [
                                        f"{discharged_patient.name} discharged from Hospital {hospital.id}",
                                        f"Encounter ID: {original_encounter['id']}",
                                        f"Duration: {start_time} to {end_time}",
                                        f"Disposition: {discharge['hospitalization']['dischargeDisposition']['coding'][0]['display']}",
                                        f"Discharge Status: {discharge.get('status', 'unknown')}",
                                        f"Length of Stay: {(datetime.fromisoformat(end_time.replace('Z', '+00:00')) - datetime.fromisoformat(start_time.replace('Z', '+00:00'))).total_seconds() / 3600:.1f} hours"
                                    ]
                                    
                                    # Add discharge diagnosis if present
                                    if 'diagnosis' in discharge:
                                        discharge_details.append(f"Discharge Diagnosis: {discharge['diagnosis'][0]['condition']['display']}")
                                        
                                    # Add discharge instructions if present
                                    if 'instruction' in discharge:
                                        discharge_details.append(f"Instructions: {discharge['instruction'][0]['text']}")
                                        
                                    log_event(" | ".join(discharge_details), event_type='hospital')
                                    
                                else:
                                    log_event(f"{discharged_patient.name} discharged from Hospital {hospital.id} (no prior encounter found)", event_type='hospital')
                                    
                            except Exception as e:
                                print(f"Error generating discharge: {str(e)}")
                                log_event(f"Error processing discharge for {discharged_patient.name}", event_type='hospital')

        socketio.emit('update_state', get_state())
        time.sleep(1)

def log_hospital_event(message):
    """Log events specific to hospital operations."""
    log_event(message, event_type='hospital')

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
def handle_create_patient(data=None):
    """Handle button click to create a patient."""
    llm_model = data.get('llm_model') if data else None
    print(f'Create Patient event received, using model: {llm_model or DEFAULT_LLM_MODEL}')
    
    # Submit to thread pool instead of direct call
    future = patient_generator_pool.submit(generate_random_patient_async, llm_model)
    
    def handle_generated_patient(future):
        try:
            patient = future.result()
            if patient:
                socketio.emit('update_state', get_state())
        except Exception as e:
            logging.error(f"Error handling generated patient: {str(e)}")
    
    future.add_done_callback(handle_generated_patient)

@socketio.on('create_patient_at_house')
def handle_create_patient_at_house(data):
    """Handle creating a patient at a specific house when the house is clicked."""
    house_id = data['house_id']
    house = next((h for h in houses if h.id == house_id), None)

    if house and not house.patient_ids:
        patient_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Create a proper Condition object instead of a string
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
            note="Emergency presentation with undetermined specific condition"
        )
        
        patient = Patient(patient_id, f"Patient-{patient_id[:8]}", condition)
        patients.append(patient)
        house.add_patient(patient.id)
        log_event(
            f"Patient {patient.id} at House {house.id} | "
            f"Condition: {condition.code.get('display', 'Unknown')} (Code: {condition.code.get('code', 'Unknown')}) | "
            f"Severity: {condition.severity.get('display', 'Unknown')} (Code: {condition.severity.get('code', 'Unknown')})",
            event_type='patient'
        )
        socketio.emit('update_state', get_state())

def generate_random_patient_async(llm_model=None):
    """Async version of generate_random_patient for parallel processing."""
    try:
        logging.info(f"Starting async patient generation with model: {llm_model}")
        patient = generate_random_patient(llm_model)
        if patient:
            socketio.emit('update_state', get_state())
        return patient
    except Exception as e:
        logging.error(f"Error in async patient generation: {str(e)}")
        return None

def generate_patients_automatically(llm_model=None):
    """Automatically generate patients at random intervals using thread pool."""
    while True:
        try:
            # Submit patient generation task to thread pool
            future = patient_generator_pool.submit(generate_random_patient_async, llm_model)
            
            # Add callback to handle the generated patient
            def handle_generated_patient(future):
                try:
                    patient = future.result()
                    if patient:
                        socketio.emit('update_state', get_state())
                except Exception as e:
                    logging.error(f"Error handling generated patient: {str(e)}")
            
            future.add_done_callback(handle_generated_patient)
            
            # Wait before generating next patient
            time.sleep(random.randint(PATIENT_GENERATION_LOWER_BOUND, PATIENT_GENERATION_UPPER_BOUND))
            
        except Exception as e:
            logging.error(f"Error in automatic patient generation: {str(e)}")
            time.sleep(1)  # Wait before retrying

# Modify the thread creation to accept command line arguments
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
    Thread(target=assign_ambulance).start()
    
    socketio.run(app)

