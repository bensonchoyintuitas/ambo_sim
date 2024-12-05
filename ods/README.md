# ODS (Operational Data Store)

This is as a stub to rapidly test ods concepts, and should shift to a separate repo
This directory contains patient data in various formats and the tools to process them.

## To improve
- Make a persistent output file (parquet) with schema evolution
- Make a persistent loading mechanism to load the json straight into the persistent store

## Schema Documentation

For detailed information about the patient data schemas used in this system, see [SCHEMA.md](SCHEMA.md).

## Files

- `flatten_patient.py`: Converts FHIR JSON patient data to CSV format
- `union_patients.py`: Combines multiple patient CSV files
- Patient data files in both JSON and CSV formats


## Usage

1. Convert JSON to CSV:
```bash
python flatten_patient.py input.json output.csv
```

2. Combine multiple CSV files:
```bash
python union_patients.py output_dir input1.csv input2.csv [input3.csv ...]
# exampl
python3 union_patients.py patient_pat-2731.csv patient_6462bf29-68f3-36ca-2f78-ff1ce05d1484.csv
```