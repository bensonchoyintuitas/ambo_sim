from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import time
from threading import Thread
import math
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app)

class Patient:
    def __init__(self, id, name, condition):
        self.id = id
        self.name = name
        self.condition = condition

class Ambulance:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y
        self.target = None
        self.is_available = True
        self.state = 'green'  # green means available
        self.patient_id = None

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
        self.has_patient = False
        self.ambulance_on_the_way = False
        self.patient_id = None

class Hospital:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y
        self.patients = []  # List of patient IDs

    def add_patient(self, patient_id):
        self.patients.append(patient_id)

def calculate_distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

# Sample lists of first and last names
first_names = ["John", "Jane", "Alex", "Emily", "Chris", "Katie", "Michael", "Sarah"]
last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]

# Define a list of possible patient conditions
conditions = ["Fell down stairs", "Critical burn", "Can't breathe", "Majorly bad breath"]

# Set the number of houses to 10 and hospitals to 3
houses = [House(i, 50, 50 + i * 60) for i in range(10)]
hospitals = [Hospital(i, 450, 50 + i * 200) for i in range(3)]

# Initialize ambulances at the hospitals, equally distributed
ambulances = []
for i in range(5):
    hospital = hospitals[i % len(hospitals)]  # Distribute ambulances evenly across hospitals
    ambulances.append(Ambulance(i, hospital.x, hospital.y))

event_log = []

def log_event(message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    event_log.insert(0, f"{timestamp} - {message}")
    if len(event_log) > 10:  # Keep only the last 10 events
        event_log.pop()
    socketio.emit('update_log', event_log)


def generate_random_patient():
    """Generate a patient at a random house."""
    random_house = random.choice(houses)
    if not random_house.has_patient and not random_house.ambulance_on_the_way:
        patient_id = random.randint(1000, 9999)  # Assign unique patient ID
        condition = random.choice(conditions)  # Randomly select a condition
        name = f"{random.choice(first_names)} {random.choice(last_names)}"  # Generate random name
        patient = Patient(patient_id, name, condition)
        random_house.has_patient = True
        random_house.patient_id = patient.id
        log_event(f"Patient {patient.name} (ID: {patient.id}) with condition {patient.condition} is at House {random_house.id}")
    socketio.emit('update_state', get_state())

def move_ambulances():
    """Move ambulances to pick up patients and take them to the nearest hospital."""
    while True:
        for ambulance in ambulances:
            if ambulance.is_available:
                # Check if there's a house with a patient and no ambulance on the way
                patient_house = next((house for house in houses if house.has_patient and not house.ambulance_on_the_way), None)
                if patient_house:
                    ambulance.is_available = False
                    ambulance.target = (patient_house.x, patient_house.y)
                    ambulance.state = 'red'  # Heading to pick up a patient
                    patient_house.ambulance_on_the_way = True
                    ambulance.patient_id = patient_house.patient_id  # Assign patient ID to ambulance
                    log_event(f"Ambulance {ambulance.id} is heading to House {patient_house.id} to pick up Patient {patient_house.patient_id}")
            elif ambulance.target:
                # Move ambulance to the target (house or hospital)
                target_x, target_y = ambulance.target
                ambulance.move_to(target_x, target_y)

                # If reached house with patient
                if ambulance.x == target_x and ambulance.y == target_y:
                    patient_house = next((house for house in houses if house.x == target_x and house.y == target_y), None)
                    if patient_house and patient_house.has_patient:
                        patient_house.has_patient = False
                        nearest_hospital = find_nearest_hospital(ambulance.x, ambulance.y)
                        ambulance.target = (nearest_hospital.x, nearest_hospital.y)
                        ambulance.state = 'yellow'  # Has patient, heading to hospital
                        log_event(f"Ambulance {ambulance.id} picked up Patient {ambulance.patient_id} from House {patient_house.id} and is heading to Hospital {nearest_hospital.id}")
                    elif ambulance.x == ambulance.target[0] and ambulance.y == ambulance.target[1]:
                        # If ambulance reached the hospital, append patient ID to that hospital's array
                        nearest_hospital = find_nearest_hospital(ambulance.x, ambulance.y)
                        nearest_hospital.add_patient(ambulance.patient_id)
                        log_event(f"Ambulance {ambulance.id} has delivered Patient {ambulance.patient_id} to Hospital {nearest_hospital.id}")
                        ambulance.is_available = True
                        ambulance.state = 'green'  # Free to pick up another patient
                        ambulance.target = None
                        ambulance.patient_id = None

        socketio.emit('update_state', get_state())
        time.sleep(0.05)  # Reduce the sleep time to make the simulation feel faster

def find_nearest_hospital(x, y):
    """Find the nearest hospital to the given coordinates."""
    nearest_hospital = min(hospitals, key=lambda h: calculate_distance(x, y, h.x, h.y))
    return nearest_hospital

def get_state():
    """Returns the state of ambulances, houses, and hospitals."""
    return {
        'ambulances': [{'id': a.id, 'x': a.x, 'y': a.y, 'state': a.state} for a in ambulances],
        'houses': [{'id': h.id, 'x': h.x, 'y': h.y, 'has_patient': h.has_patient, 'ambulance_on_the_way': h.ambulance_on_the_way} for h in houses],
        'hospitals': [{'id': h.id, 'x': h.x, 'y': h.y, 'patients': h.patients} for h in hospitals]
    }

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    emit('update_log', event_log)  # Send the log when a client connects
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

    if house and not house.has_patient:  # Only create patient if the house is green (no patient)
        patient_id = random.randint(1000, 9999)  # Assign unique patient ID
        condition = random.choice(conditions)  # Randomly select a condition
        name = f"{random.choice(first_names)} {random.choice(last_names)}"  # Generate random name
        patient = Patient(patient_id, name, condition)
        house.has_patient = True
        house.patient_id = patient.id
        log_event(f"Patient {patient.name} (ID: {patient.id}) with condition {patient.condition} is at House {house.id}")
        socketio.emit('update_state', get_state())

def generate_patients_automatically():
    """Automatically generate patients at random intervals."""
    while True:
        generate_random_patient()
        time.sleep(random.randint(5, 15))  # Random interval between 5 to 15 seconds

# Start background threads for simulation
Thread(target=generate_patients_automatically).start()
Thread(target=move_ambulances).start()

if __name__ == '__main__':
    socketio.run(app)
