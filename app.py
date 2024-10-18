from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import time
from threading import Thread

app = Flask(__name__)
socketio = SocketIO(app)

class Ambulance:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y
        self.target = None
        self.is_available = True
        self.state = 'green'  # green means available

    def move_to(self, target_x, target_y):
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
        self.ambulance_on_the_way = False

class Hospital:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y

ambulances = [Ambulance(i, random.randint(50, 100), random.randint(50, 300)) for i in range(3)]
houses = [House(i, 50, 50 + i * 100) for i in range(5)]
hospital = Hospital(1, 450, 200)

def generate_patients():
    """Randomly assigns patients to houses."""
    while True:
        random_house = random.choice(houses)
        if not random_house.has_patient and not random_house.ambulance_on_the_way:
            random_house.has_patient = True
            random_house.ambulance_on_the_way = False
        socketio.emit('update_state', get_state())
        time.sleep(5)

def move_ambulances():
    """Move ambulances to pick up patients and take them to the hospital."""
    while True:
        for ambulance in ambulances:
            if ambulance.is_available:
                patient_house = next((house for house in houses if house.has_patient and not house.ambulance_on_the_way), None)
                if patient_house:
                    ambulance.is_available = False
                    ambulance.target = (patient_house.x, patient_house.y)
                    ambulance.state = 'red'  # Heading to pick up a patient
                    patient_house.ambulance_on_the_way = True
            elif ambulance.target:
                # Move ambulance to the target (house or hospital)
                target_x, target_y = ambulance.target
                ambulance.move_to(target_x, target_y)

                # If reached house with patient
                if ambulance.x == target_x and ambulance.y == target_y:
                    patient_house = next((house for house in houses if house.x == target_x and house.y == target_y), None)
                    if patient_house and patient_house.has_patient:
                        patient_house.has_patient = False
                        ambulance.target = (hospital.x, hospital.y)
                        ambulance.state = 'yellow'  # Has patient, heading to hospital
                    elif ambulance.x == hospital.x and ambulance.y == hospital.y:
                        ambulance.is_available = True
                        ambulance.state = 'green'  # Free to pick up another patient
                        ambulance.target = None

        socketio.emit('update_state', get_state())
        time.sleep(0.1)

def get_state():
    """Returns the state of ambulances, houses, and hospital."""
    return {
        'ambulances': [{'id': a.id, 'x': a.x, 'y': a.y, 'state': a.state} for a in ambulances],
        'houses': [{'id': h.id, 'x': h.x, 'y': h.y, 'has_patient': h.has_patient, 'ambulance_on_the_way': h.ambulance_on_the_way} for h in houses],
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
