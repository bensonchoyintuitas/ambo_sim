import json
import pandas as pd
import duckdb
from pathlib import Path
import argparse
from datetime import datetime

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
    Process a JSON file and merge with existing output file if it exists
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

def main():
    parser = argparse.ArgumentParser(description='Process JSON files and merge into CSV/Parquet')
    parser.add_argument('input_file', help='Input JSON file')
    parser.add_argument('--filename', required=True, help='Output file name')
    parser.add_argument('--format', choices=['csv', 'parquet'], default='csv', 
                        help='Output file format (csv or parquet)')
    parser.add_argument('--path', help='Output directory path (relative to script)', default='')
    args = parser.parse_args()
    
    # Get the script's directory
    script_dir = Path(__file__).parent
    
    # Input path
    input_path = script_dir / args.input_file
    
    # Output path - combine script_dir, provided path, and filename
    output_dir = script_dir / args.path if args.path else script_dir
    output_dir.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist
    output_path = output_dir / args.filename
    
    # Add extension if not provided
    if not output_path.suffix:
        output_path = output_path.with_suffix(f'.{args.format}')
    
    process_json_file(input_path, output_path, args.format)

if __name__ == "__main__":
    main()