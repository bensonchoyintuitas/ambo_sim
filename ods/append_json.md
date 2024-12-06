# JSON to CSV/Parquet Converter

A Python utility that processes JSON files, flattens nested structures, and merges them into either CSV or Parquet files. The script handles nested JSON objects by flattening them into a single-level structure and can merge new data with existing files.

## Features

- Flattens nested JSON structures
- Supports both CSV and Parquet output formats
- Automatically merges with existing output files
- Handles column mismatches between existing and new data
- Uses DuckDB for efficient data merging

## Prerequisites

```bash
source .venv/bin/activate 
pip install -r requirements.txt
```

## Usage

Basic usage:
```bash
source .venv/bin/activate 
python3 append_json.py input.json --filename output --format csv
```
```bash
source .venv/bin/activate 
python3 append_json.py patient_pat-9791.json --path ./output --filename patient --format csv
python3 append_json.py patient_6462bf29-68f3-36ca-2f78-ff1ce05d1484.json --path ./output --filename patient --format csv
```

### Arguments

- `input_file`: Path to the input JSON file (required)
- `--filename`: Name of the output file (required)
- `--format`: Output format, either 'csv' or 'parquet' (default: 'csv')

### Examples

Convert a JSON file to CSV:
```bash
python3 append_json.py data.json --filename processed_data --format csv
```

Convert a JSON file to Parquet:
```bash
python3 append_json.py data.json --filename processed_data --format parquet
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