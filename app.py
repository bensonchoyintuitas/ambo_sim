from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import time
from threading import Thread, Lock
import math
from datetime import datetime
import json
# from ai.generate_patient import generate_fhir_resources  # Add this import at the top
from generate_synthea_patient import generate_fhir_resources  # Add new import
import uuid

app = Flask(__name__)
socketio = SocketIO(app)

# Configurable variables
MAX_TREATING = 2
WAITING_TIME = 1  # seconds
TREATING_TIME = 240  # seconds
PATIENT_GENERATION_LOWER_BOUND = 0  # Lower bound for patient generation delay
PATIENT_GENERATION_UPPER_BOUND = 1  # Upper bound for patient generation delay

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

def generate_random_patient():
    """Generate a patient at a random house with FHIR resources."""
    random_house = random.choice(houses)
    
    try:
        # Get FHIR resources from Synthea API
        fhir_resources = generate_fhir_resources()
        
        # Get the patient resource directly
        patient_resource = fhir_resources['patient']
        
        # Extract patient ID from the resource
        patient_id = patient_resource.get('id')
        print(f"Patient ID: {patient_id}")
        
        # Get name from the resource
        name_data = patient_resource.get('name', [{}])[0]
        given_name = name_data.get('given', [''])[0] if name_data.get('given') else ''
        family_name = name_data.get('family', '')
        full_name = f"{given_name} {family_name}".strip()
        if not full_name:
            full_name = "Unknown Patient"
        print(f"Full name: {full_name}")
        
        # Get birth date
        dob = patient_resource.get('birthDate')
        print(f"DOB: {dob}")
        
        # Get gender
        gender = patient_resource.get('gender', 'unknown')
        
        # Get condition from the condition resource
        condition_resource = fhir_resources['condition']
        condition = condition_resource.get('code', {}).get('text', 'Emergency Condition')
        condition_severity = None
        condition_note = None
        
        # Create patient object with properties from FHIR resource
        patient = Patient(
            id=patient_id,
            name=full_name,
            condition=condition,
            condition_severity=condition_severity,
            dob=dob,
            condition_note=condition_note,
            fhir_resources=fhir_resources
        )
        
        patients.append(patient)
        random_house.add_patient(patient.id)
        
        # Enhanced log message with all available details
        log_parts = [
            f"New patient - ID: {patient_id}",
            f"Name: {full_name}",
            f"Gender: {gender}",
            f"Condition: {condition}"
        ]
        
        if dob:
            log_parts.append(f"DOB: {dob}")
        
        log_event(" | ".join(log_parts), event_type='patient')
        socketio.emit('update_state', get_state())
        return patient
        
    except Exception as e:
        import traceback
        print(f"Detailed error in generate_random_patient: {str(e)}")
        print("Traceback:")
        print(traceback.format_exc())
        
        # Fallback generation
        patient_id = f"pat-{random.randint(1000, 9999)}"
        full_name = "Unknown Patient"
        condition = "Emergency Condition"
        
        patient = Patient(
            id=patient_id,
            name=full_name,
            condition=condition,
            fhir_resources={}
        )
        patients.append(patient)
        random_house.add_patient(patient.id)
        
        log_message = (
            f"New patient (fallback) - "
            f"ID: {patient_id}, "
            f"Name: {full_name}, "
            f"Condition: {condition}"
        )
        log_event(log_message, event_type='patient')
        socketio.emit('update_state', get_state())
        return patient

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
                        log_event(f"Ambulance {closest_ambulance.id} is heading to House {house.id} to pick up Patient {patient.id}", event_type='ambulance')
                    else:
                        log_event(f"No patient found with ID {house.patient_ids[0]} at House {house.id}", event_type='ambulance')

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
                        log_event(f"Ambulance {ambulance.id} picked up Patient {ambulance.patient.id} from House {patient_house.id} and is heading to Hospital {nearest_hospital.id}", event_type='ambulance')
                    elif ambulance.x == ambulance.target[0] and ambulance.y == ambulance.target[1]:
                        # If ambulance reached the hospital, append patient object to that hospital's array
                        nearest_hospital = find_nearest_hospital(ambulance.x, ambulance.y)
                        patient = next((p for p in patients if p.id == ambulance.patient.id), None)  # Find the patient object
                        if patient:
                            nearest_hospital.add_patient_to_waiting(patient)
                            log_event(f"Patient {ambulance.patient.id} arrived at Hospital {nearest_hospital.id}", event_type='hospital')
                            # Add new hospital event for patient arrival
                            log_event(f"Patient {patient.id} has arrived at Hospital {nearest_hospital.id} and entered waiting queue", event_type='hospital')
                        ambulance.is_available = True
                        ambulance.state = 'green'  # Free to pick up another patient
                        ambulance.target = None
                        ambulance.patient = None  # Clear the patient object

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
                'waiting': [{'id': p.id, 'name': p.name, 'condition': p.condition, 'wait_time': p.wait_time} for p in h.waiting],
                'treating': [{'id': p.id, 'name': p.name, 'condition': p.condition, 'wait_time': p.wait_time} for p in h.treating],
                'discharged': [{'id': p.id, 'name': p.name, 'condition': p.condition, 'wait_time': p.wait_time} for p in h.discharged]
            } for h in hospitals
        ],
        'patients': [{'id': p.id, 'name': p.name} for p in patients]
    }

def manage_hospital_queues():
    """Manage the movement of patients between hospital queues."""
    hospital_lock = Lock()

    while True:
        for hospital in hospitals:
            with hospital_lock:
                # Update wait times for patients in the waiting queue
                if hospital.waiting:
                    patient = hospital.waiting[0]
                    patient.wait_time += 1

                    # Move patient to treating if wait time exceeds WAITING_TIME and there's space
                    if patient.wait_time >= WAITING_TIME and len(hospital.treating) < MAX_TREATING:
                        moved_patient = hospital.move_patient_to_treating()
                        if moved_patient:
                            log_event(f"Patient {moved_patient.id} moved to treating at Hospital {hospital.id}", event_type='hospital')

                # Update wait times for patients in the treating queue
                for patient in hospital.treating:
                    patient.wait_time += 1

                    # Discharge patient if wait time exceeds TREATING_TIME
                    if patient.wait_time >= TREATING_TIME:
                        discharged_patient = hospital.discharge_patient()
                        if discharged_patient:
                            log_event(f"Patient {discharged_patient.id} discharged from Hospital {hospital.id}", event_type='hospital')

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
    """Handle creating a patient at a specific house when the house is clicked."""
    house_id = data['house_id']
    house = next((h for h in houses if h.id == house_id), None)

    if house and not house.patient_ids:  # Only create patient if the house has no patients
        patient_id = random.randint(1000, 9999)  # Assign unique patient ID
        condition = "Unknown Condition"  # Default condition
        name = f"{patient_id}"  # Remove "Patient" prefix from name
        patient = Patient(patient_id, name, condition)
        patients.append(patient)  # Add the patient to the global list
        house.add_patient(patient.id)
        log_event(f"Patient {patient.id} with condition {patient.condition} is at House {house.id}", event_type='patient')
        socketio.emit('update_state', get_state())

def generate_patients_automatically():
    """Automatically generate patients at random intervals."""
    while True:
        generate_random_patient()
        time.sleep(random.randint(PATIENT_GENERATION_LOWER_BOUND, PATIENT_GENERATION_UPPER_BOUND))

# Start background threads for simulation
Thread(target=generate_patients_automatically).start()
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
    socketio.run(app)
