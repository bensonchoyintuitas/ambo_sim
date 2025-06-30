# Kafka JSON Producer

A Python utility that produces JSON files to Kafka topics. The script can process single files or entire directories, with support for continuous monitoring of input directories.

## Features

- Processes single JSON files or entire directories
- Maintains a processing log to avoid duplicate processing
- Supports continuous monitoring with configurable intervals
- Force processing option to override log checks
- Configurable broker settings

## Prerequisites

```bash
# Create and activate virtual environment
python3 -m venv .venv

# For Linux/MacOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

Activate the environment:
```bash
source .venv/bin/activate
```

Basic usage for a single file:
```bash
python3 produce_json.py --input input.json --output-topic my-topic
```

Process all JSON files in a directory:
```bash
python3 produce_json.py --input /path/to/json/folder --output-topic my-topic
```

Force processing of all files (ignore log):
```bash
python3 produce_json.py --input /path/to/json/folder --output-topic my-topic --force-all
```

Continuous monitoring (check every 30 seconds):
```bash
python3 produce_json.py --input /path/to/json/folder --output-topic my-topic --continuous 30
```

### Arguments

- `--input`: Path to either a JSON file or directory containing JSON files (required)
- `--output-topic`: Name of the Kafka topic to produce to (required)
- `--broker`: Kafka broker address (optional, default: 'localhost:9092')
- `--force-all`: Process all files even if they've been processed before (optional)
- `--continuous SECONDS`: Run continuously with specified interval in seconds until stopped with Ctrl+C (optional)

### Typical Set of Producers
```bash
# Run continuously, checking for new files every 30 seconds
source .venv/bin/activate 

# In separate terminal windows:
python3 produce_json.py --input ../../fhir_export/session_20250630_134254/patient/ --output-topic patient --continuous 30
python3 produce_json.py --input ../../fhir_export/session_20250630_134254/condition/ --output-topic condition --continuous 30
python3 produce_json.py --input ../../fhir_export/session_20250630_134254/encounter_ed_presentation/ --output-topic encounter_ed_presentation --continuous 30
python3 produce_json.py --input ../../fhir_export/session_20250630_134254/encounter_discharge/ --output-topic encounter_discharge --continuous 30
```

## Logging

The script maintains a log file (`kafka_producer.log`) that tracks:
- Source filename
- Processing timestamp
- Topic name

## Notes

- The script expects valid JSON files as input
- Files are tracked in the log to prevent duplicate processing
- Use `--force-all` to override log checks and reprocess files
- The script can handle both absolute and relative paths
- Ctrl+C gracefully stops continuous processing 