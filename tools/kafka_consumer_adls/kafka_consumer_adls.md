# Status
Working / not yet part of main project

# Introduction 
This application consumes data from a local Kafka topic, then pushes the event as a new JSON file in Azure Data Lake Storage Gen2 (ADLS Gen2).

# Getting Started

## Prerequisites
- Python 3.x
- Access to an Azure Storage Account
- Local Kafka instance or Kafka cluster

## Installation
```bash
# Create and activate virtual environment
python3 -m venv .venv

# For Linux/MacOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

# Configuration
Storage account credentials should be configured in `azure_config.yml`. A template is provided in `azure_config.yml_template`.

> ⚠️ **Important**: Do not commit your actual credentials to version control.

# Usage
```bash
python kafka_consumer_adls.py --topic TOPIC --container CONTAINER --path PATH 
                            [--consumer-group GROUP] [--bootstrap-server SERVER] 
                            [--auto-offset {latest,earliest}] [--reset-offset]

# Parameters:
# --topic            Name of the Kafka topic to consume from
# --container        Azure Storage container name
# --path             Base folder path in the container
# --consumer-group   Consumer group ID (optional, default: DefaultConsumerGroup)
# --bootstrap-server Kafka bootstrap server (optional, default: localhost:9092)
# --auto-offset      Auto offset reset behavior (optional, default: latest)
#                    Values: latest | earliest
# --reset-offset     Reset consumer group offset before starting (optional)
```

## Scenario consumption
```bash
# patient
source .venv/bin/activate
python3 kafka_consumer_adls.py --topic patient \
                            --container dev \
                            --path bronze/landing/kafka__local/ \
                            --consumer-group DefaultConsumerGroup \
                            --bootstrap-server localhost:9092 \
                            --auto-offset earliest \
                            --reset-offset

# encounter_ed_presentation
source .venv/bin/activate
python3 kafka_consumer_adls.py --topic encounter_ed_presentation \
                            --container dev \
                            --path bronze/landing/kafka__local/ \
                            --consumer-group DefaultConsumerGroup \
                            --bootstrap-server localhost:9092 \
                            --auto-offset earliest \
                            --reset-offset

# encounter_discharge
source .venv/bin/activate
python3 kafka_consumer_adls.py --topic encounter_discharge \
                            --container dev \
                            --path bronze/landing/kafka__local/ \
                            --consumer-group DefaultConsumerGroup \
                            --bootstrap-server localhost:9092 \
                            --auto-offset earliest \
                            --reset-offset

# condition
source .venv/bin/activate
python3 kafka_consumer_adls.py --topic condition \
                            --container dev \
                            --path bronze/landing/kafka__local/ \
                            --consumer-group DefaultConsumerGroup \
                            --bootstrap-server localhost:9092 \
                            --auto-offset earliest \
                            --reset-offset
```

## Examples
```bash
# Basic usage with required parameters
python3 kafka_consumer_adls.py --topic FHIR__Patient__json --container dev --path bronze/landing/kafka__local/

# With consumer group
python3 kafka_consumer_adls.py --topic patient --container dev \
                            --path landing/kafka/aero16/ --consumer-group DefaultConsumerGroup

# Full parameter specification - latest
python3 kafka_consumer_adls.py --topic patient \
                            --container dev \
                            --path bronze/landing/kafka__local/ \
                            --consumer-group DefaultConsumerGroup \
                            --bootstrap-server localhost:9092 \
                            --auto-offset latest

# Full parameter specification - earliest with reset
python3 kafka_consumer_adls.py --topic patient \
                            --container dev \
                            --path bronze/landing/kafka__local/ \
                            --consumer-group DefaultConsumerGroup \
                            --bootstrap-server localhost:9092 \
                            --auto-offset earliest \
                            --reset-offset
```