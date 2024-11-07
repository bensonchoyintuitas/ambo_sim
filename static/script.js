const canvas = document.getElementById('simulationCanvas');
const context = canvas.getContext('2d');

// Set a font for the text
context.font = '16px Arial';
context.fillStyle = '#ffffff'; // Set text color to white

// Ensure the canvas size is set correctly
canvas.width = 800;
canvas.height = 650;

const socket = io();

// Track the state of houses (for clicking)
let housesState = [];

// Handle clicks on the canvas to create a patient at the clicked house if it's green
canvas.addEventListener('click', function(event) {
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Check if the click is on a house
    housesState.forEach(function(house) {
        const houseSize = 20;
        if (
            x >= house.x && x <= house.x + houseSize &&
            y >= house.y && y <= house.y + houseSize &&
            !house.has_patient  // Only allow creating patient if the house is green (no patient)
        ) {
            console.log(`Clicked on House ${house.id}, creating patient.`);
            socket.emit('create_patient_at_house', { house_id: house.id });  // Emit event with house ID
        }
    });
});

// Draw the state of the simulation (houses, ambulances, hospitals)
function drawState(state) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    housesState = state.houses;  // Update housesState for click handling

    // Draw houses
    state.houses.forEach(function(house) {
        if (house.has_patient) {
            context.fillStyle = house.ambulance_on_the_way ? "yellow" : "red"; // Yellow if ambulance is on the way, red otherwise
        } else {
            context.fillStyle = "green"; // Green if no patient
        }
        context.fillRect(house.x, house.y, 20, 20);
        context.fillStyle = "#ffffff"; // Set text color to white
        context.fillText("H" + house.id, house.x + 5, house.y - 5);  // House ID

        // Display patient IDs below the house
        const patientList = house.patient_ids.join(", ");
        context.fillText("Patients: " + patientList, house.x - 20, house.y + 30);
    });

    // Draw hospitals and display patient lists
    state.hospitals.forEach(function(hospital) {
        context.fillStyle = "blue";
        context.fillRect(hospital.x, hospital.y, 40, 40);
        context.fillStyle = "#ffffff"; // Set text color to white
        context.fillText("Hosp" + hospital.id, hospital.x + 5, hospital.y - 5);  // Hospital ID

        // Display patient IDs in the waiting, treating, and discharged lists
        const waitingList = hospital.waiting.map(patient => patient.id).join(", ");
        const treatingList = hospital.treating.map(patient => patient.id).join(", ");
        const dischargedList = hospital.discharged.map(patient => patient.id).join(", ");

        context.fillText("Waiting: " + waitingList, hospital.x - 20, hospital.y + 50);
        context.fillText("Treating: " + treatingList, hospital.x - 20, hospital.y + 70);
        context.fillText("Discharged: " + dischargedList, hospital.x - 20, hospital.y + 90);
    });

    // Draw ambulances
    state.ambulances.forEach(function(ambulance) {
        context.fillStyle = ambulance.state;
        context.fillRect(ambulance.x, ambulance.y, 10, 10);
        context.fillStyle = "#ffffff"; // Set text color to white
        context.fillText("Amb" + ambulance.id, ambulance.x + 5, ambulance.y - 5);  // Ambulance ID

        // Display the patient ID carried by the ambulance
        if (ambulance.patient_id) {
            context.fillText("Patient: " + ambulance.patient_id, ambulance.x - 10, ambulance.y + 20);
        }
    });
}

// Add these functions to handle specific log updates
function updateSpecificLog(logData, containerId) {
    const logContainer = document.getElementById(containerId);
    logContainer.innerHTML = '<h3>' + containerId.split('-')[0].charAt(0).toUpperCase() + 
                            containerId.split('-')[0].slice(1) + ' Events</h3>';
    const ul = document.createElement('ul');
    logData.forEach(event => {
        const li = document.createElement('li');
        li.textContent = event;
        ul.appendChild(li);
    });
    logContainer.appendChild(ul);
}

// Update the socket event handlers
socket.on('update_patient_log', function(log) {
    updateSpecificLog(log, 'patient-events');
});

socket.on('update_ambulance_log', function(log) {
    updateSpecificLog(log, 'ambulance-events');
});

socket.on('update_hospital_log', function(log) {
    updateSpecificLog(log, 'hospital-events');
});

// Remove or comment out the old updateLog function if it's not being used elsewhere

document.getElementById('resetButton').addEventListener('click', () => {
    socket.emit('reset_simulation');
});

socket.on('update_state', (state) => {
    drawState(state);
});

socket.on('update_log', (log) => {
    updateLog(log);
});
