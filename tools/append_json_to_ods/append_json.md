# JSON to CSV/Parquet Converter

A Python utility that processes JSON files, flattens nested structures, and merges them into either CSV or Parquet files. The script handles nested JSON objects by flattening them into a single-level structure and can merge new data with existing files.


## Features

- Flattens nested JSON structures
- Supports both CSV and Parquet output formats
- Automatically merges with existing output files
- Handles column mismatches between existing and new data
- Uses DuckDB for efficient data merging
- Default behaviour is to skip files that have already been processed
- Optional force processing of all files

## Logging

The script maintains a log file (with .log extension) in the same directory as the output file. The log tracks:

- Source filename
- Processing timestamp 
- Number of columns in the processed data

Example log file (output/patient.log):


## Prerequisites

```bash
source .venv/bin/activate 
pip install -r requirements.txt
```

## Usage
Active the environment:
```bash
source .venv/bin/activate 
```
Basic usage for a single file:
```bash
python3 append_json.py --input input.json --filename output --path ./output--format csv
```
Convert a JSON file to Parquet:
```bash
python3 append_json.py --input input.json --filename output --path ./output --format parquet 
```

Process all JSON files in a directory:
```bash
python3 append_json.py --input /path/to/json/folder --filename output --path ./output --format csv
```

Force processing of all files (ignore log):
```bash
python3 append_json.py --input /path/to/json/folder --filename output --path ./output --format csv --force-all
```

### Arguments

- `--input`: Path to either a JSON file or directory containing JSON files (required)
- `--filename`: Name of the output file (required)
- `--format`: Output format, either 'csv' or 'parquet' (default: 'csv')
- `--path`: Output directory path relative to script location (optional, default: current directory)
- `--force-all`: Process all files even if they've been processed before (optional)
- `--continuous SECONDS`: Run continuously with specified interval in seconds until stopped with Ctrl+C (optional)

### Typical set of consumers
```bash
# Run continuously, checking for new files every 30 seconds
source .venv/bin/activate 
python3 append_json.py --input ../../fhir_export/session_20241209_210827/patient/ --path ./output --filename patient --format csv --continuous 30

# In a new window
source .venv/bin/activate 
python3 append_json.py --input ../../fhir_export/session_20241209_210827/condition/ --path ./output --filename condition --format csv --continuous 30

# In a new window
source .venv/bin/activate 
python3 append_json.py --input ../../fhir_export/session_20241209_210827/encounter_ed_presentation/ --path ./output --filename encounter_ed_presentation --format csv --continuous 30

# In a new window
source .venv/bin/activate 
python3 append_json.py --input ../../fhir_export/session_20241209_210827/encounter_discharge/ --path ./output --filename encounter_discharge --format csv --continuous 30
```




### Examples
Process patient JSON files:
```bash
source .venv/bin/activate 
python3 append_json.py --input patient_pat-9791.json --path ./output --filename patient --format csv
python3 append_json.py --input patient_6462bf29-68f3-36ca-2f78-ff1ce05d1484.json --path ./output --filename patient --format csv

# relative path
python append_json.py --input ../output_fhir/session_20241205_220516/patient/patient_pat-7834.json --path ./output --filename patient --format csv

# process all files in a directory
python3 append_json.py --input ../fhir_export/session_20241205_220516/patient/ --path ./output --filename patient --format csv
python3 append_json.py --input ../fhir_export/session_20241205_220516/encounter_ed_presentation/ --path ./output --filename encounter_ed_presentation --format csv
python3 append_json.py --input ../fhir_export/session_20241205_220516/encounter_discharge/ --path ./output --filename encounter_discharge --format csv
python3 append_json.py --input ../fhir_export/session_20241205_220516/condition/ --path ./output --filename condition --format csv

# absolute path
python append_json.py --input /full/path/to/fhir_export/session_20241205_220516/patient/patient_pat-7834.json --path ./output --filename patient --format csv
```





### Input JSON Format

The script can handle nested JSON structures of any depth. For example:

```json
{
    "id": 1,
    "name": "John",
    "address": {
        "street": "123 Main St",
        "city": "Springfield"
    },
    "phones": [
        "555-0123",
        "555-0124"
    ]
}
```

Will be flattened to:
```csv
id,name,address_street,address_city,phones_0,phones_1
1,John,123 Main St,Springfield,555-0123,555-0124
```

## Notes

- The script expects each JSON file to contain a single object
- When merging with existing files, records are matched based on the 'id' field
- The script will create the output file if it doesn't exist
- If the output file exists, the new data will be merged with the existing data

# To improve
- output to tables within a duckdb database
- output to deltalake / iceberg tables
