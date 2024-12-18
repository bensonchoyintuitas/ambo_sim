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

## Note
There is a commented-out section for topic purging that can be uncommented if needed:
