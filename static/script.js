const canvas = document.getElementById('simulationCanvas');
const context = canvas.getContext('2d');
const socket = io();

function drawState(state) {
    context.clearRect(0, 0, canvas.width, canvas.height);

    // Draw houses
    state.houses.forEach(function(house) {
        context.fillStyle = house.has_patient ? "red" : "green";
        context.fillRect(house.x, house.y, 20, 20);
    });

    // Draw hospital
    const hospital = state.hospital;
    context.fillStyle = "blue";
    context.fillRect(hospital.x, hospital.y, 40, 40);

    // Draw ambulances
    state.ambulances.forEach(function(ambulance) {
        context.fillStyle = ambulance.available ? "yellow" : "orange";
        context.fillRect(ambulance.x, ambulance.y, 10, 10);
    });
}

socket.on('update_state', function(state) {
    drawState(state);
});
