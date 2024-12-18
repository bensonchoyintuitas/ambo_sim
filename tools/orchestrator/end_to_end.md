# End-to-End Orchestration Process

This document outlines the sequential steps for running the complete ambulance simulation system.

## Environment Setup
- Working Directory Root: `/mnt/d/Work/Intuitas/repo/ambo_sim/`
- Environment Activation: `source .venv/bin/activate`

## Prerequisites
- Ensure Docker is running
- Ensure Python environment is activated
- all Working directories are hard coded in the yaml files
- Ensure all programs have their venvs initialised

## To improve
- [ ] Add helper to update all working directories in yaml files


## Process Steps

1. **Infrastructure Setup**
   - Ensure Docker is running
   - Initializes the core infrastructure components
   - Waits 60 seconds for services to stabilize

2. **Synthea API Initialization**
   - Starts the Synthea API producer service
   - Waits 30 seconds for initialization

3. **Ambulance Simulation Launch**
   - Initiates the main ambulance simulation
   - Waits 30 seconds for startup

4. **Kafka Session Management**
   - Updates session timestamp in kafka_producers.yml
   - Configuration path: `/mnt/d/Work/Intuitas/repo/ambo_sim/tools/orchestrator/kafka_producers.yml`
   - Sessions root: `/mnt/d/Work/Intuitas/repo/ambo_sim/fhir_export`
   - Waits 30 seconds for updates to take effect

5. **Kafka Producers**
   - Starts Kafka producer services
   - Waits 60 seconds for producer initialization

6. **Kafka Consumers**
   - Launches Kafka consumer services
   - Waits 60 seconds for consumer initialization
   - Default is --auto-offset earliest --reset-offset for the default consumer group which means it will start from the earliest offset and reset the offset to the earliest offset everytime this is run (risk of dupes downstream if not combined with a purge).

At this point, data is being produced and consumed into the nominated ADLS location:

1. **Verify Data Flow**
   - Check ADLS container 'dev' under path 'bronze/landing/kafka__local/'
   - Confirm new files are being created for each topic:
     - patient
     - condition 
     - encounter_discharge
     - encounter_ed_presentation

2. **Start Databricks Processing**
   - Log into Databricks workspace
   - Navigate to Workflows section
   - Locate and start the data processing workflow:
     - Navigate to "Workflows" > "Jobs"
     - Find workflow: `health_lakehouse__engineering__databricks__bronze_landing_to_ods`
     - Click "Run Now" to start the job
   
   - Monitor workflow execution:
     - Watch the job progress in the "Runs" tab
     - Check for any errors or failures
     - Verify all tasks complete successfully
   
   - View and validate results in Bronze Dashboard:
     - Open [Ambo-sim BRONZE.ODS Summary Dashboard](https://adb-1006248599320535.15.azuredatabricks.net/sql/dashboardsv3/01efba111f9b12bca1b432ad4a09bf20?o=1006248599320535)




## Note
There is a commented-out section for topic purging that can be uncommented if needed:
