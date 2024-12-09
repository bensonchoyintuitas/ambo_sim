# Status
Working / not yet part of main project

# Introduction 
This application consumes data from a local kafka topic, then pushes the event as a new json file in ADLSgen2


# Getting started
<!-- linux -->
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

# Security
Storage account info is stored in a separate file [azure_config.yml]
Template for this is in [azure_config.yml_template] 
!! Dont commit your actual key


# Running
source .venv/Scripts/activate
python [script_name].py [kafka_topic] [consumer_group] [bootstrap_server] [auto_offset:latest|earliest]
*Examples*
py main.py FHIR__Patient__json 
py main.py FHIR__Encounter__json 
py main.py FHIR__Encounter__json-flattened_epoch DefaultConsumerGroup localhost:9092 latest