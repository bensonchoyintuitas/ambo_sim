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
        context.fillStyle = house.has_patient ? "red" : "green";
        context.fillRect(house.x, house.y, 20, 20);
        context.fillStyle = "#ffffff"; // Set text color to white
        context.fillText("H" + house.id, house.x + 5, house.y - 5);  // House ID
    });

    // Draw hospitals and display patient lists
    state.hospitals.forEach(function(hospital) {
        context.fillStyle = "blue";
        context.fillRect(hospital.x, hospital.y, 40, 40);
        context.fillStyle = "#ffffff"; // Set text color to white
        context.fillText("Hosp" + hospital.id, hospital.x + 5, hospital.y - 5);  // Hospital ID
        context.fillText("Patients: " + hospital.patients.join(", "), hospital.x - 20, hospital.y + 50);  // Patient list
    });

    // Draw ambulances
    state.ambulances.forEach(function(ambulance) {
        context.fillStyle = ambulance.state;
        context.fillRect(ambulance.x, ambulance.y, 10, 10);
        context.fillStyle = "#ffffff"; // Set text color to white
        context.fillText("Amb" + ambulance.id, ambulance.x + 5, ambulance.y - 5);  // Ambulance ID
    });
}

// Update the event log in the text box
function updateLog(log) {
    const logContainer = document.getElementById('eventLog');
    logContainer.innerHTML = '';
    log.forEach(event => {
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

function renderHouses(houses) {
    houses.forEach(house => {
        // Determine the color based on the house state
        if (house.ambulance_on_the_way) {
            context.fillStyle = 'yellow'; // Color when an ambulance is on the way
        } else if (house.patient_ids.length > 0) {
            context.fillStyle = 'red'; // Color when there are patients
        } else {
            context.fillStyle = 'green'; // Color when the house is empty
        }

        // Draw the house as a smaller square
        const houseSize = 20; // Size of the square
        context.fillRect(house.x, house.y, houseSize, houseSize);

        // Draw the house label
        context.fillStyle = '#ffffff'; // Set text color to white
        const houseLabel = `H${house.id}`;
        context.fillText(houseLabel, house.x, house.y - 5); // Position label above the house

        // Draw the patient IDs below the house if there are any
        if (house.patient_ids.length > 0) {
            context.fillStyle = '#ffffff'; // Set text color to white
            const patientLabel = `Patients: [${house.patient_ids.join(', ')}]`;
            context.fillText(patientLabel, house.x, house.y + houseSize + 15); // Position label below the house
        }
    });
}

function renderHospitals(hospitals) {
    hospitals.forEach(hospital => {
        // Draw the hospital
        context.fillStyle = 'blue'; // Color for hospitals
        const hospitalSize = 30; // Size of the square
        context.fillRect(hospital.x, hospital.y, hospitalSize, hospitalSize);

        // Draw the hospital label
        context.fillStyle = '#ffffff'; // Set text color to white
        const hospitalLabel = `Hospital ${hospital.id}`;
        context.fillText(hospitalLabel, hospital.x, hospital.y - 5); // Position label above the hospital

        // Optionally, draw patient IDs or other info related to the hospital
        context.fillStyle = '#ffffff'; // Set text color to white
        const patientsLabel = `Patients: [${hospital.patients.join(', ')}]`;
        context.fillText(patientsLabel, hospital.x, hospital.y + hospitalSize + 15); // Position label below the hospital
    });
}

function renderAmbulances(ambulances) {
    ambulances.forEach(ambulance => {
        // Log the state for debugging
        console.log(`Ambulance ${ambulance.id} state: ${ambulance.state}`);

        // Determine the color based on the ambulance state
        switch (ambulance.state) {
            case 'green':
                context.fillStyle = 'green'; // Available
                break;
            case 'red':
                context.fillStyle = 'red'; // En route to pick up a patient
                break;
            case 'yellow':
                context.fillStyle = 'yellow'; // Transporting a patient
                break;
            default:
                context.fillStyle = 'gray'; // Default color for unknown state
        }

        // Draw the ambulance
        const ambulanceSize = 15; // Size of the square
        context.fillRect(ambulance.x, ambulance.y, ambulanceSize, ambulanceSize);

        // Draw the ambulance label
        context.fillStyle = '#ffffff'; // Set text color to white
        const ambulanceLabel = `A${ambulance.id}`;
        context.fillText(ambulanceLabel, ambulance.x, ambulance.y - 5); // Position label above the ambulance
    });
}

function updateState(state) {
    context.clearRect(0, 0, canvas.width, canvas.height); // Clear the canvas
    renderHouses(state.houses);
    renderHospitals(state.hospitals);
    renderAmbulances(state.ambulances);
}

document.getElementById('resetButton').addEventListener('click', () => {
    socket.emit('reset_simulation');
});

socket.on('update_state', (state) => {
    updateState(state);
});

socket.on('update_log', (log) => {
    updateLog(log);
});
