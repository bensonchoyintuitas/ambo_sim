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

// At the top of the file, add some configuration constants
const EMOJI_FONT_SIZE = '32px'; // 4x larger emojis
const TEXT_FONT_SIZE = '14px';
const HOUSE_SIZE = 10;  // Half of 20
const HOSPITAL_SIZE = 20;  // Half of 40
const AMBULANCE_SIZE = 10;  // Doubled from 5 to 10
const EMOJI_OFFSET_X = 5;
const EMOJI_OFFSET_Y = 15; // Adjusted for larger emoji
const TEXT_OFFSET_X = -20;
const TEXT_OFFSET_Y = 30;
const AMBULANCE_PATIENT_OFFSET_Y = 40;  // New constant for patient text position below ambulance

// Add these to your emoji constants
const PATIENT_LOG_EMOJI = "👤";
const AMBULANCE_LOG_EMOJI = "🚑";
const HOSPITAL_LOG_EMOJI = "🏥";

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
    housesState = state.houses;

    // Draw houses
    state.houses.forEach(function(house) {
        // Draw the square
        if (house.has_patient) {
            context.fillStyle = house.ambulance_on_the_way ? "yellow" : "red";
        } else {
            context.fillStyle = "green";
        }
        context.fillRect(house.x, house.y, HOUSE_SIZE, HOUSE_SIZE);

        // Draw the emoji
        context.fillStyle = "#ffffff";
        context.font = EMOJI_FONT_SIZE + ' Arial';  // Larger font for emoji
        context.fillText("🏠", house.x + EMOJI_OFFSET_X, house.y + EMOJI_OFFSET_Y);

        // Draw the text
        context.font = TEXT_FONT_SIZE + ' Arial';  // Regular font for text
        if (house.patient_ids.length > 0) {
            const patientInfo = house.patient_ids
                .map(id => {
                    const patient = state.patients?.find(p => p.id === id);
                    return patient ? `👤${patient.name.split(' ')[0]}` : id;
                })
                .join(", ");
            context.fillText(patientInfo, house.x + TEXT_OFFSET_X, house.y + TEXT_OFFSET_Y);
        }
    });

    // Draw hospitals
    state.hospitals.forEach(function(hospital) {
        // Draw the square
        context.fillStyle = "blue";
        context.fillRect(hospital.x, hospital.y, HOSPITAL_SIZE, HOSPITAL_SIZE);

        // Draw the emoji
        context.fillStyle = "#ffffff";
        context.font = EMOJI_FONT_SIZE + ' Arial';  // Larger font for emoji
        context.fillText("🏥", hospital.x + EMOJI_OFFSET_X, hospital.y + EMOJI_OFFSET_Y);

        // Draw the text
        context.font = TEXT_FONT_SIZE + ' Arial';  // Regular font for text
        if (hospital.waiting.length > 0) {
            const waitingList = "⌛ " + hospital.waiting.map(p => p.name.split(' ')[0]).join(", ");
            context.fillText(waitingList, hospital.x - 20, hospital.y + 50);
        }
        
        if (hospital.treating.length > 0) {
            const treatingList = "🏥 " + hospital.treating.map(p => p.name.split(' ')[0]).join(", ");
            context.fillText(treatingList, hospital.x - 20, hospital.y + 70);
        }
        
        if (hospital.discharged.length > 0) {
            const dischargedList = "✅ " + hospital.discharged.map(p => p.name.split(' ')[0]).join(", ");
            context.fillText(dischargedList, hospital.x - 20, hospital.y + 90);
        }
    });

    // Draw ambulances
    state.ambulances.forEach(function(ambulance) {
        // Get the ambulance image element
        const ambulanceImg = document.getElementById('ambulance-template');
        
        // Save the current context state
        context.save();
        
        // Set up the transformation
        context.translate(ambulance.x, ambulance.y);
        
        // Default to facing left (flipped)
        // Only face right (unflipped) when heading to hospital (yellow state)
        if (ambulance.state !== 'yellow') {
            context.scale(-1, 1);
        }
        
        // Draw the ambulance image
        context.drawImage(ambulanceImg, -16, -16, 32, 32); // Centered on ambulance position
        
        // Restore the context state
        context.restore();

        // Draw the patient name if present
        if (ambulance.patient_id) {
            context.font = TEXT_FONT_SIZE + ' Arial';
            const patientName = state.patients?.find(p => p.id === ambulance.patient_id)?.name.split(' ')[0];
            if (patientName) {
                context.fillText(`👤${patientName}`, ambulance.x - 10, ambulance.y + AMBULANCE_PATIENT_OFFSET_Y);
            }
        }
    });
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

// Update the updateSpecificLog function
function updateSpecificLog(logData, containerId) {
    const logContainer = document.getElementById(containerId);
    
    // Get the appropriate emoji based on the container ID
    let emoji = "";
    switch(containerId) {
        case 'patient-events':
            emoji = PATIENT_LOG_EMOJI;
            break;
        case 'ambulance-events':
            emoji = AMBULANCE_LOG_EMOJI;
            break;
        case 'hospital-events':
            emoji = HOSPITAL_LOG_EMOJI;
            break;
    }
    
    // Capitalize first letter of the title and add emoji
    const title = containerId.split('-')[0].charAt(0).toUpperCase() + 
                 containerId.split('-')[0].slice(1);
    
    logContainer.innerHTML = `<h3>${emoji} ${title} Events</h3>`;
    const ul = document.createElement('ul');
    logData.forEach(event => {
        const li = document.createElement('li');
        li.textContent = event;
        ul.appendChild(li);
    });
    logContainer.appendChild(ul);
}

document.getElementById('resetButton').addEventListener('click', () => {
    socket.emit('reset_simulation');
});

socket.on('update_state', (state) => {
    context.font = TEXT_FONT_SIZE + ' Arial';  // Reset to default text size
    drawState(state);
});

socket.on('update_log', (log) => {
    updateLog(log);
});

socket.on('update_request_counts', function(data) {
    document.getElementById('requests-made').textContent = data.requests_made;
    document.getElementById('requests-completed').textContent = data.requests_completed;
});
