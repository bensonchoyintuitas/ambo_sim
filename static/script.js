const canvas = document.getElementById('simulationCanvas');
const context = canvas.getContext('2d');

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
        context.fillStyle = house.has_patient ? "red" : "green";
        context.fillRect(house.x, house.y, 20, 20);
        context.fillStyle = "black";
        context.fillText("H" + house.id, house.x + 5, house.y - 5);  // House ID
    });

    // Draw hospitals and display patient lists
    state.hospitals.forEach(function(hospital) {
        context.fillStyle = "blue";
        context.fillRect(hospital.x, hospital.y, 40, 40);
        context.fillStyle = "black";
        context.fillText("Hosp" + hospital.id, hospital.x + 5, hospital.y - 5);  // Hospital ID
        context.fillText("Patients: " + hospital.patients.join(", "), hospital.x - 20, hospital.y + 50);  // Patient list
    });

    // Draw ambulances
    state.ambulances.forEach(function(ambulance) {
        context.fillStyle = ambulance.state;
        context.fillRect(ambulance.x, ambulance.y, 10, 10);
        context.fillStyle = "black";
        context.fillText("Amb" + ambulance.id, ambulance.x + 5, ambulance.y - 5);  // Ambulance ID
    });
}

// Update the event log in the text box
function updateLog(log) {
    const logContainer = document.getElementById('eventLog');
    logContainer.innerHTML = '';  // Clear the log
    log.forEach(function(event) {
        const li = document.createElement('li');
        li.textContent = event;
        logContainer.appendChild(li);
    });
}

// Handle socket events for state updates and log updates
socket.on('update_state', function(state) {
    console.log('State updated');  // Debugging output
    drawState(state);
});

socket.on('update_log', function(log) {
    console.log('Log updated');  // Debugging output
    updateLog(log);
});
