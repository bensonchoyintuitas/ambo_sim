# Session Timestamp Updater

A lightweight Python utility that updates session timestamps in Kafka producer YAML configuration files. It can either use the latest session folder automatically or accept a custom session string.

## Quick Start

```bash
# Use latest session folder automatically
python kafka_producers__update_session_timestamp.py /path/to/kafka_producers.yml

python kafka_producers__update_session_timestamp.py \
    --yaml-file /mnt/d/Work/Intuitas/repo/ambo_sim/tools/orchestrator/kafka_producers.yml \
    --sessions-root /mnt/d/Work/Intuitas/repo/ambo_sim/fhir_export \


# Use custom session string
python kafka_producers__update_session_timestamp.py /path/to/kafka_producers.yml session_20241215_093000
```

## Features

- Automatically finds latest session folder
- Supports custom session string input
- Updates all session timestamps in YAML file
- Can be imported as a module in other scripts

## Usage as Module

```python
from kafka_producers__update_session_timestamp import get_latest_session_folder

# Get latest session
latest_session = get_latest_session_folder("/path/to/fhir_export")
```

## Arguments

- `path_to_yaml_file`: Path to the Kafka producers YAML file (required)
- `new_session_string`: Custom session string (optional)

## Notes

- Session folders must follow pattern: `session_YYYYMMDD_HHMMSS`
- Validates file and directory existence
- Maintains YAML file structure
- Handles both relative and absolute paths
