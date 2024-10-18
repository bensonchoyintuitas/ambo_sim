const canvas = document.getElementById('simulationCanvas');
const context = canvas.getContext('2d');
const socket = io();

// Draw the state of the simulation (houses, ambulances, hospitals)
function drawState(state) {
    context.clearRect(0, 0, canvas.width, canvas.height);

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
    drawState(state);
});

socket.on('update_log', function(log) {
    updateLog(log);
});
