# Ambulance simulator

This simulator models an emergency medical services (EMS) system to help understand, test, and optimize emergency response workflows. It creates a virtual environment where ambulances respond to medical emergencies, transport patients to hospitals, and hospitals manage patient care through triage and treatment.

**Key purposes:**
- Test and visualize emergency response workflows
- Demonstrate FHIR (Fast Healthcare Interoperability Resources) implementation in healthcare
- Analyze system performance, wait times, and resource allocation
- Generate realistic healthcare datasets for testing and development
- Support training for healthcare administrators and emergency response planners

See [business_process.md](business_process.md) for the idealbusiness process.
See [fhir_process.md](fhir_process.md) for the idealFHIR resources and exchanges.

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
1. Run the Synthea API (optional)
https://github.com/bensonchoyintuitas/synthea_api
2. Run the ambo sim
```bash
source .venv/bin/activate 
python3 app.py --no-llm # no LLM

# output FHIR resources to file
python3 app.py --no-llm --output-fhir

 # llm choices
python3 app.py --llm-model llama3.1:8b # better
python3 app.py --llm-model llama3.2:1b 
python3 app.py --llm-model gemma2:2b 
python3 app.py --llm-model gemma:2b # worse
python3 app.py --llm-model llama2:7b 
```
# Command Line Switches

## Core Switches
`--no-llm`
- Disables LLM integration for faster simulation
- Uses basic patient/condition generation only
- Recommended for testing or when speed is priority

`--output-fhir` 
- Enables saving of FHIR resources as JSON files
- Creates timestamped session directory under output_fhir/
- Organizes resources by type (patient, condition, etc)
- Useful for data analysis and integration testing

## LLM Model Selection
`--llm-model <model>`
Controls which LLM to use for enhancing patient data. Options:

- `llama3.1:8b` (recommended)
  - Best medical content accuracy
  - Most reliable FHIR formatting
  - Slower but highest quality

- `llama3.2:1b`
  - Faster than 8b model
  - Reduced but acceptable accuracy
  - Good for testing/development

- `gemma2:2b` / `gemma:2b`
  - Fastest option with LLM
  - Less consistent medical content
  - May require more validation

- `llama2:7b`
  - Legacy model included for comparison
  - Not recommended for production use

The LLM models trade off between speed and quality of generated content. The llama3.1:8b model is recommended for production use when accuracy is critical.


# How the simulation works

## Patient Flow
   - Patient ID is created and added to house's patient array
   - Available ambulance is dispatched and removes patient ID from house array 
   - Patient ID is stored in ambulance's single slot during transport
   - At hospital, patient ID moves from ambulance to hospital's patient array


## Data Flow and Components

### Patient Generation
   - The simulation has three levels of patient generation - each with different levels of speed and richness:
    1. Random bare minimuum patient and condition (from small list) 
    2. Synthea API to generate base patient demographics and medical history
    3. Synthea API + LLM to generate more comprehensiveFHIR resources
   - Each generated patient serves as a "seed" for further simulation

## LLM Enhancement (optional)
   - The LLM (either Llama 3.1 8B or Gemma 2B) processes Synthea patient data using a template prompt that:
     - Generates structured FHIR resources (Conditions, Observations)
     - Includes examples and clinical instructions
     - Creates medically appropriate scenarios based on demographics/history
     - Ensures consistent formatting and required FHIR elements
   - Llama 3.1 follows the template more reliably and produces more accurate medical content than Gemma
   - added no-llm option for speed


## Simulation Components

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

   - Each component maintains its own event log tracking patient movements

## FHIR Resource Flow
   - Patient resources are created initially from Synthea
   - LLM enhances with additional resources during simulation
   - Resources follow the patient through the care journey
   - See fhir_process.md for detailed FHIR workflows

The simulation combines realistic patient data from Synthea with LLM-enhanced medical scenarios, creating a dynamic emergency response system simulation.


## Kafka Consumer Notes

### FHIR Message Handling

The system generates two distinct types of encounter messages that should be handled differently in the Kafka consumer:

1. **Initial Emergency Encounters**
   - Generated when patient first arrives at hospital
   - Contains full emergency visit details including:
     - Priority (Urgent)
     - Service Type (Emergency Medicine)
     - Initial diagnosis
     - Procedures performed
     - Start time only in period

2. **Discharge Encounters**
   - Generated when patient is discharged
   - References original encounter via `partOf`
   - Contains:
     - End time in period
     - Discharge disposition
     - Final diagnosis/outcomes
   - Links back to original emergency encounter

### Consumer Implementation Considerations
- Need separate message handlers for initial encounters vs discharges
- Track encounter relationships (original -> discharge)
- Consider implementing state tracking to link encounters
- Ensure FHIR references maintain integrity across messages
- May want to update original encounter when discharge occurs


# Development plan

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
- [x] Generate encounter and procedure resources
- [x] Generate discharge event (to update existing encounter)

# fhir_output - Output all FHIR resources to files
- [x] for no-llm no-synthea
- [x] for synthea
- [ ] make ambulance flip
- [ ] for llm
- [ ] for clickable patient
- [ ] validate consistent fhir format for both LLM and NO LLM, and with and without synthea
- [ ] validate consistent fhir format using fallback when using clickable patient
- [ ] conform to synthea as base template for fallback
- [ ] refactor to DRY all fallbacks (clickable, automated)



# kafka_output
- [ ] Send data to kafka


# Stage 3
- [ ] If an ambulance is wiating with patient - they cannot leave
- [ ] Vary treatment time by severity
- [ ] Speed things up (maybe pregen into CSVs and load from there)
- [ ] Reflect more accurate patient flow (see [fhir_process.md](fhir_process.md))
- [ ] Have patient-centric view of flow events (filterable)
- [ ] Make patient ID more unique and consistent

# Stage 5 Advanced
- [ ] Agent-driven independent ambulances
- [ ] Configurable number of ambulances, hospitals and houses





