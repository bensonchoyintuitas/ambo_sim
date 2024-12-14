# Ambulance simulator

This simulator models an emergency medical services (EMS) system to help understand, test, and optimize emergency response workflows. It creates a virtual environment where ambulances respond to medical emergencies, transport patients to hospitals, and hospitals manage patient care through triage and treatment.

**Key purposes:**
- Test and visualize emergency response workflows
- Demonstrate FHIR (Fast Healthcare Interoperability Resources) implementation in healthcare
- Analyze system performance, wait times, and resource allocation
- Generate realistic healthcare datasets for testing and development
- Support training for healthcare administrators and emergency response planners

See [business_process.md](docs/business_process.md) for the ideal business process.
See [fhir_process.md](docs/fhir_process.md) for the ideal FHIR resources and exchanges.

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
python3 app.py --no-llm --fhir-export

# llm choices
python3 app.py --llm-model llama3.1:8b --fhir-export # better
python3 app.py --llm-model llama3.2:1b --fhir-export # lacking the note field
python3 app.py --llm-model gemma2:2b --fhir-export
python3 app.py --llm-model gemma:2b # worse
```
# Command Line Switches

## Core Switches
`--no-llm`
- Disables LLM integration for faster simulation
- Uses basic patient/condition generation only
- Recommended for testing or when speed is priority

`--fhir-export` 
- Enables saving of FHIR resources as JSON files
- Creates timestamped session directory under fhir_export/
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


# Project Structure

## Core Folders
- `/ambo_sim` - Main project directory containing core simulation code
  - `app.py` - Main simulation application and Flask server
  - `templates/` - HTML templates for web visualization
  - `static/` - CSS, JavaScript and other static assets
  - `fhir_generators/` - Modules for generating FHIR resources
  - `/fhir_export` - Output directory for FHIR JSON files
    - Organized by session timestamp and resource type
    - Contains patient, condition, encounter resources
    - Excluded from git via .gitignore
  - `/tools` - Utility scripts and data processing tools
    - `/append_json_to_ods` - Tool for converting FHIR JSON to CSV/Parquet 
      - Processes output files for analysis
      - Supports continuous monitoring of export directory
      - Configurable output formats and paths
      - See [append_json.md](tools/append_json_to_ods/append_json.md) for usage details
    - `/kafka_producer` - Tool for streaming FHIR JSON files to Kafka topics
      - See [produce_json.md](tools/kafka_producer/produce_json.md) for usage details
    - `/kafka_consumer_adls` - Tool for consuming FHIR JSON files from Kafka  writing to Azure Data Lake Storage (ADLS)
      - See [kafka_consumer_adls.md](tools/kafka_consumer_adls/kafka_consumer_adls.md) for usage details
    - `/purge_topics` - Tool for cleaning up Kafka topics
      - See [purge_topics.md](tools/purge_topics/purge_topics.md) for usage details
  - `/infrastructure` - Docker and configuration files for supporting services
    - `/confluent` - Confluent Platform configuration and setup
      - Provides local Confluent Platform environment
      - Includes Control Center for monitoring and management
      - Configures Schema Registry for AVRO/JSON schemas
      - Sets up Connect workers for data integration
      - Manages topic configurations and ACLs
      - See [confluent/README.md](tools/confluent/README.md) for setup instructions




## Documentation 
- `/docs` - Additional documentation files
  - Schema definitions
  - API documentation
  - Architecture diagrams


# How the simulation works

## Patient Flow
   - Patient ID is created and added to house's patient array
   - Available ambulance is dispatched and removes patient ID from house array 
   - Patient ID is stored in ambulance's single slot during transport
   - At hospital, patient ID moves from ambulance to hospital's patient array

## Schemas
Schemas are compatible, but vary in terms of element coverage depending on NoSynthea, Synthea and LLM usage.
- See [patient_schema.md](docs/patient_schema.md) for detailed patient schema documentation

## Data Flow and Components

### Patient Generation 
   - The simulation has three levels of patient generation - each with different levels of speed and richness:
    1. Random bare minimuum patient and condition (from small list) 
    2. Synthea API to generate base patient demographics and medical history
    3. Synthea API + LLM to generate more comprehensive FHIR resources
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
   - See [fhir_process.md](docs/fhir_process.md) for detailed FHIR workflows

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
- [x] for synthea-patient
- [x] make ambulance flip
- [x] fix llm errors
- [x] force clickable patient to be fallback for speed
- [x] validate consistent fhir format for both LLM and NO LLM, and with and without synthea
- [x] validate consistent fhir format using fallback when using clickable patient
- [-] conform to synthea as base template for fallback

# kafka
- [x] Send data to kafka
- [x] Consume data from kafka to adls
- [x] Consume Include partitioning in the file paths (e.g., /landing/yyyy/MM/dd/HH/

# databricks
- [x] ingest using auto loader


# Automation
- [ ] build one-click runner to 
  - [ ] run synthea
  - [ ] run confluent
  - [ ] run kafka producer
  - [ ] run kafka consumer

# Stage 3
- [ ] refactor to DRY all fallbacks (clickable, automated)
- [ ] If an ambulance is wiating with patient - they cannot leave
- [ ] Vary treatment time by severity
- [ ] Speed things up (maybe pregen into CSVs and load from there)
- [ ] Reflect more accurate patient flow (see [fhir_process.md](docs/fhir_process.md))
- [ ] Have patient-centric view of flow events (filterable)

# Stage 5 Advanced
- [ ] Agent-driven independent ambulances
- [ ] Configurable number of ambulances, hospitals and houses



