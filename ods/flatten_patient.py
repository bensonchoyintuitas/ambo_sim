import json
import csv
import pandas as pd
from pathlib import Path
import argparse

def flatten_json(nested_json, prefix=''):
    """
    Flatten a nested JSON object into a single level dictionary.
    """
    flattened = {}
    
    def flatten(obj, name=''):
        if isinstance(obj, dict):
            for key, value in obj.items():
                flatten(value, f"{name}_{key}" if name else key)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                flatten(item, f"{name}_{i}")
        else:
            flattened[name] = obj
            
    flatten(nested_json)
    return flattened

def process_patient_json(input_file, output_file):
    """
    Process a FHIR Patient JSON file and convert it to CSV.
    """
    # Read JSON file
    with open(input_file, 'r') as f:
        patient_data = json.load(f)
    
    # Flatten the JSON
    flat_patient = flatten_json(patient_data)
    
    # Convert to DataFrame and save as CSV
    df = pd.DataFrame([flat_patient])
    df.to_csv(output_file, index=False)
    
    print(f"CSV file created successfully: {output_file}")

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Convert FHIR Patient JSON to CSV')
    parser.add_argument('input_file', help='Input JSON file name')
    args = parser.parse_args()
    
    # Get the script's directory
    script_dir = Path(__file__).parent
    
    # Input and output file paths
    input_path = script_dir / args.input_file
    output_path = input_path.with_suffix('.csv')
    
    # Process the file
    process_patient_json(input_path, output_path)

if __name__ == "__main__":
    main() 