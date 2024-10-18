from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import time
from threading import Thread

app = Flask(__name__)
socketio = SocketIO(app)

# Simple classes for Ambulance, House (with patient), and Hospital
class Ambulance:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y
        self.target = None
        self.is_available = True

    def move_to(self, target_x, target_y):
        # Simple movement logic, moving one step at a time
        if self.x < target_x:
            self.x += 1
        elif self.x > target_x:
            self.x -= 1
        if self.y < target_y:
            self.y += 1
        elif self.y > target_y:
            self.y -= 1

class House:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y
        self.has_patient = False

class Hospital:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y

# Setup: 3 ambulances, 5 houses, and 1 hospital
ambulances = [Ambulance(i, random.randint(50, 100), random.randint(50, 300)) for i in range(3)]
houses = [House(i, 50, 50 + i * 100) for i in range(5)]
hospital = Hospital(1, 450, 200)

def generate_patients():
    """Randomly assigns patients to houses."""
    while True:
        random_house = random.choice(houses)
        if not random_house.has_patient:
            random_house.has_patient = True
        socketio.emit('update_state', get_state())
        time.sleep(5)

def move_ambulances():
    """Move ambulances to pick up patients and take them to the hospital."""
    while True:
        for ambulance in ambulances:
            if ambulance.is_available:
                # Check if there's a house with a patient
                patient_house = next((house for house in houses if house.has_patient), None)
                if patient_house:
                    ambulance.is_available = False
                    ambulance.target = (patient_house.x, patient_house.y)
            elif ambulance.target:
                # Move ambulance to the target
                target_x, target_y = ambulance.target
                ambulance.move_to(target_x, target_y)

                # If reached house with patient
                if ambulance.x == target_x and ambulance.y == target_y:
                    patient_house = next((house for house in houses if house.x == target_x and house.y == target_y), None)
                    if patient_house and patient_house.has_patient:
                        # Pick up patient and head to hospital
                        patient_house.has_patient = False
                        ambulance.target = (hospital.x, hospital.y)
                    elif ambulance.x == hospital.x and ambulance.y == hospital.y:
                        # Drop off patient at hospital
                        ambulance.is_available = True
                        ambulance.target = None

        socketio.emit('update_state', get_state())
        time.sleep(0.1)

def get_state():
    """Returns the state of ambulances, houses, and hospital."""
    return {
        'ambulances': [{'id': a.id, 'x': a.x, 'y': a.y, 'available': a.is_available} for a in ambulances],
        'houses': [{'id': h.id, 'x': h.x, 'y': h.y, 'has_patient': h.has_patient} for h in houses],
        'hospital': {'id': hospital.id, 'x': hospital.x, 'y': hospital.y}
    }

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    emit('update_state', get_state())

# Start background threads for simulation
Thread(target=generate_patients).start()
Thread(target=move_ambulances).start()

if __name__ == '__main__':
    socketio.run(app)
