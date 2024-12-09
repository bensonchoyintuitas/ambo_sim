import json
import pandas as pd
import duckdb
from pathlib import Path
import argparse
from datetime import datetime
import os
import time
import sys

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

def merge_dataframes(existing_df, new_df):
    """
    Merge two dataframes, combining columns and handling duplicates
    """
    # Convert all columns to string type to avoid type mismatches
    existing_df = existing_df.astype(str)
    new_df = new_df.astype(str)
    
    con = duckdb.connect(':memory:')
    
    # Convert dataframes to DuckDB tables
    con.execute("CREATE TABLE existing AS SELECT * FROM existing_df")
    con.execute("CREATE TABLE new AS SELECT * FROM new_df")
    
    # Get column information
    existing_cols = existing_df.columns
    new_cols = new_df.columns
    all_cols = list(set(existing_cols) | set(new_cols))
    common_cols = list(set(existing_cols) & set(new_cols))
    
    # Create SELECT statements with COALESCE for all columns
    select_statements = []
    for col in all_cols:
        if col in common_cols:
            select_statements.append(f"COALESCE(t1.{col}, t2.{col}) as {col}")
        elif col in existing_cols:
            select_statements.append(f"t1.{col}")
        else:
            select_statements.append(f"t2.{col}")
    
    # Build and execute the full query
    query = f"""
    SELECT {', '.join(select_statements)}
    FROM existing t1
    FULL OUTER JOIN new t2 ON t1.id = t2.id
    """
    
    result = con.execute(query).df()
    return result

def log_processing(input_file, output_path, num_columns):
    """
    Log processing details to a CSV log file
    """
    # Create log filename with same path but .log extension
    log_path = output_path.with_suffix('.log')
    
    # Prepare log entry
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = {
        'source_filename': str(input_file),
        'processed_timestamp': timestamp,
        'number_of_columns': num_columns
    }
    
    # Convert to DataFrame
    log_df = pd.DataFrame([log_entry])
    
    # Append or create log file
    if log_path.exists():
        existing_log = pd.read_csv(log_path)
        updated_log = pd.concat([existing_log, log_df], ignore_index=True)
    else:
        updated_log = log_df
    
    # Save log
    updated_log.to_csv(log_path, index=False)

def process_json_file(input_file, output_file, output_format='csv'):
    """
    Process a single JSON file and merge with existing output file if it exists
    """
    # Read and flatten JSON
    with open(input_file, 'r') as f:
        json_data = json.load(f)
    flat_data = flatten_json(json_data)
    new_df = pd.DataFrame([flat_data])
    
    output_path = Path(output_file)
    
    # Check if output file exists
    if output_path.exists():
        # Read existing file
        if output_format == 'csv':
            existing_df = pd.read_csv(output_path)
        else:  # parquet
            existing_df = pd.read_parquet(output_path)
            
        # Merge dataframes
        result_df = merge_dataframes(existing_df, new_df)
    else:
        result_df = new_df
    
    # Save the result
    if output_format == 'csv':
        result_df.to_csv(output_path, index=False)
    else:  # parquet
        result_df.to_parquet(output_path, index=False)
    
    # Log the processing
    log_processing(input_file, output_path, len(result_df.columns))
    
    print(f"Processed {input_file} and saved to {output_file}")
    print(f"Total rows: {len(result_df)}")
    print("\nSample of data:")
    print(result_df.head())

def check_if_processed(input_file, log_path):
    """
    Check if a file has already been processed by looking in the log
    """
    if not log_path.exists():
        return False
        
    log_df = pd.read_csv(log_path)
    return str(input_file) in log_df['source_filename'].values

def process_input_path(input_path, output_path, output_format='csv', force_all=False):
    """
    Process either a single JSON file or all JSON files in a directory
    """
    if input_path.is_file():
        if input_path.suffix.lower() == '.json':
            log_path = output_path.with_suffix('.log')
            if not force_all and check_if_processed(input_path, log_path):
                print(f"Skipping already processed file: {input_path}")
                return
            process_json_file(input_path, output_path, output_format)
        else:
            print(f"Skipping non-JSON file: {input_path}")
    elif input_path.is_dir():
        json_files = list(input_path.glob('**/*.json'))
        if not json_files:
            print(f"No JSON files found in directory: {input_path}")
            return
        
        log_path = output_path.with_suffix('.log')
        print(f"Found {len(json_files)} JSON files to process")
        for json_file in json_files:
            if not force_all and check_if_processed(json_file, log_path):
                print(f"Skipping already processed file: {json_file}")
                continue
            print(f"\nProcessing: {json_file}")
            process_json_file(json_file, output_path, output_format)
    else:
        print(f"Input path does not exist: {input_path}")

def main():
    parser = argparse.ArgumentParser(description='Process JSON files and merge into CSV/Parquet')
    parser.add_argument('--input', required=True, help='Input JSON file or directory containing JSON files')
    parser.add_argument('--filename', required=True, help='Output file name')
    parser.add_argument('--format', choices=['csv', 'parquet'], default='csv', 
                        help='Output file format (csv or parquet)')
    parser.add_argument('--path', help='Output directory path (relative to script)', default='')
    parser.add_argument('--force-all', action='store_true', 
                        help='Process all files even if already in log')
    parser.add_argument('--continuous', type=int, metavar='SECONDS',
                        help='Run continuously with specified interval in seconds until Ctrl+C is pressed')
    args = parser.parse_args()
    
    # Get the script's directory
    script_dir = Path(__file__).parent
    
    # Input path - allow for absolute paths or paths relative to current directory
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = script_dir / input_path
    
    # Output path - combine script_dir, provided path, and filename
    output_dir = script_dir / args.path if args.path else script_dir
    output_dir.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist
    output_path = output_dir / args.filename
    
    # Add extension if not provided
    if not output_path.suffix:
        output_path = output_path.with_suffix(f'.{args.format}')

    if args.continuous:
        interval = args.continuous
        print(f"\nRunning in continuous mode with {interval}-second intervals. Press Ctrl+C to stop.")
        counter = 1
        try:
            while True:
                print(f"\n=== Run #{counter} ===")
                process_input_path(input_path, output_path, args.format, args.force_all)
                print(f"\nCompleted run #{counter}. Waiting {interval} seconds before next run...")
                time.sleep(interval)
                counter += 1
        except KeyboardInterrupt:
            print("\nContinuous mode stopped by user.")
            sys.exit(0)
    else:
        process_input_path(input_path, output_path, args.format, args.force_all)

if __name__ == "__main__":
    main()