# Ambulance simulator
a rectangular map to represent the town. Then some houses on the left. Hospitals on the right. and ambulances travelling between the houses and hospitals. In the houses, patients appear and then are taken from the houses to the hospitals.

See [business_process.md](business_process.md) for the business process.
See [fhir_process.md](fhir_process.md) for the FHIR resources and exchanges.

**What you'll see:**
- A rectangular canvas representing the town.
- Houses on the left, hospitals on the right.
- Ambulances moving from houses (when there’s a patient) to the hospital.
- The system automatically generates patients in random houses, and ambulances respond to them.

# Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate 
pip install -r requirements.txt
```




# Run
1. Run the Synthea API
https://github.com/bensonchoyintuitas/synthea_api
2. Run the ambo sim
```bash
source .venv/bin/activate 
python3 app.py --llm-model llama3.1:8b # better
python3 app.py --llm-model gemma:2b # worse
python3 app.py --llm-model llama2:7b 
```


# How the simulation works

## Data Flow and Components

1. **Patient Generation (Synthea)**
   - The simulation uses Synthea API to generate base patient demographics and medical history
   - Each generated patient serves as a "seed" for further simulation

2. **LLM Enhancement**
   - The LLM (either Llama 3.1 8B or Gemma 2B) processes Synthea patient data using a template prompt that:
     - Generates structured FHIR resources (Conditions, Observations)
     - Includes examples and clinical instructions
     - Creates medically appropriate scenarios based on demographics/history
     - Ensures consistent formatting and required FHIR elements
   - Llama 3.1 follows the template more reliably and produces more accurate medical content than Gemma

3. **Simulation Components**
   - Houses: Generate patients at random intervals. Each house maintains an array of patient IDs currently at that location
   - Ambulances: Transport patients between houses and hospitals. Each ambulance has a single patient ID slot that is filled during transport
   - Hospitals: Receive and process patients with configurable timing parameters:
     - Each hospital maintains an array of patient IDs currently being treated
     - Processing stages include:
       * Initial triage (configurable wait time: default 1 second)
       * Treatment time (fixed time: 240 seconds / 4 minutes)
       * Maximum of 2 patients being treated at once (MAX_TREATING = 2)
     - Hospital capacity:
       * Patients wait in queue until space available in treatment
       * Treatment begins when wait time >= WAITING_TIME and treating < MAX_TREATING
       * Patients are discharged after TREATING_TIME seconds
     - Real-time simulation tracks accumulated wait times per patient
   - Patient Flow:
     1. Patient ID is created and added to house's patient array
     2. Available ambulance is dispatched and removes patient ID from house array
     3. Patient ID is stored in ambulance's single slot during transport
     4. At hospital, patient ID moves from ambulance to hospital's patient array
   - Each component maintains its own event log tracking patient movements

4. **FHIR Resource Flow**
   - Patient resources are created initially from Synthea
   - LLM enhances with additional resources during simulation
   - Resources follow the patient through the care journey
   - See fhir_process.md for detailed FHIR workflows

The simulation combines realistic patient data from Synthea with LLM-enhanced medical scenarios, creating a dynamic emergency response system simulation.


# Todo

# Stage 1
- [x] Create patients as objects
- [x] Make more than one patient in a house
- [x] Display the patient id in an array in either house, ambo or hospital
- [x] Add wait time
- [x] Assign nearest available ambulance
- [x] Separate event logs by class
- [x] Use icons for houses, ambulances and hospitals

# Stage 2 Patients have associated FHIR resources 
- [x] Switch approach and use Synthea as a seed for each patient
- [x] Find a better LLM for generating FHIR resources such as condition based on the seed patient from synthea


# Stage 3 Apply treatment as Encounter resources
- [x] Generate encounter and procedure resources
- [x] Generate discharge event (to update existing encounter)

# Stage 4 Send data to kafka

# Stage 4 Improved ambulance sim
- [ ] Train a custom LLM for generating FHIR resources correctly to a defined template
- [ ] Speed things up (maybe pregen into CSVs and load from there)
- [ ] If an ambulance is wiating with patient - they cannot leave
- [ ] Vary treatment by severity
- [ ] Reflect more accurate patient flow (see [fhir_process.md](fhir_process.md))
- [ ] Have patient-centric view of flow events (filterable)
- [ ] Ambulances cannot leave if waiting
- [ ] Make patient ID more unique and consistent

# Stage 5 Advanced
- [ ] Agent-driven independent ambulances
- [ ] Configurable number of ambulances, hospitals and houses





