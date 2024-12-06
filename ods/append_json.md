# JSON to CSV/Parquet Converter

A Python utility that processes JSON files, flattens nested structures, and merges them into either CSV or Parquet files. The script handles nested JSON objects by flattening them into a single-level structure and can merge new data with existing files.

## Features

- Flattens nested JSON structures
- Supports both CSV and Parquet output formats
- Automatically merges with existing output files
- Handles column mismatches between existing and new data
- Uses DuckDB for efficient data merging

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
python3 append_json.py input.json --filename output --format csv
```

Process all JSON files in a directory:
```bash
python3 append_json.py /path/to/json/folder --filename output --format csv
```

### Arguments

- `input_file`: Path to the input JSON file (required)
- `--filename`: Name of the output file (required)
- `--format`: Output format, either 'csv' or 'parquet' (default: 'csv')
- `--path`: Output directory path relative to script location (optional, default: current directory)

### Examples
Process patient JSON files:
```bash
source .venv/bin/activate 
python3 append_json.py patient_pat-9791.json --path ./output --filename patient --format csv
python3 append_json.py patient_6462bf29-68f3-36ca-2f78-ff1ce05d1484.json --path ./output --filename patient --format csv

# relative path
python append_json.py ../output_fhir/session_20241205_220516/patient/patient_pat-7834.json --path ./output --filename patient --format csv
# process all files in a directory
python append_json.py ../output_fhir/session_20241205_220516/patient/ --path ./output --filename patient --format csv

# absolute path
python append_json.py /full/path/to/output_fhir/session_20241205_220516/patient/patient_pat-7834.json --path ./output --filename patient --format csv

```

Convert a JSON file to CSV:
```bash
python3 append_json.py data.json --filename processed_data --format csv --path ./output

```

Convert a JSON file to Parquet:
```bash
python3 append_json.py data.json --filename processed_data --format parquet --path ./output
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