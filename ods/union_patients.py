import duckdb
from pathlib import Path

def union_patient_csvs(csv1, csv2):
    """
    Create a DuckDB view combining two patient CSV files, 
    merging matching columns
    """
    # Connect to DuckDB
    con = duckdb.connect(':memory:')
    
    # Read both CSVs to get their column names
    df1_cols = con.execute(f"SELECT * FROM read_csv_auto('{csv1}') LIMIT 0").df().columns
    df2_cols = con.execute(f"SELECT * FROM read_csv_auto('{csv2}') LIMIT 0").df().columns
    
    # Find common and unique columns
    common_cols = list(set(df1_cols) & set(df2_cols))
    all_cols = list(set(df1_cols) | set(df2_cols))
    
    # Create SELECT statements with COALESCE for all columns
    select_statements = []
    for col in all_cols:
        if col in common_cols:
            select_statements.append(f"COALESCE(t1.{col}, t2.{col}) as {col}")
        elif col in df1_cols:
            select_statements.append(f"t1.{col}")
        else:
            select_statements.append(f"t2.{col}")
    
    # Build and execute the full query
    query = f"""
    WITH t1 AS (SELECT * FROM read_csv_auto('{csv1}')),
         t2 AS (SELECT * FROM read_csv_auto('{csv2}'))
    SELECT {', '.join(select_statements)}
    FROM t1
    FULL OUTER JOIN t2 ON t1.id = t2.id
    """
    
    result = con.execute(query).df()
    print(f"\nCombined data from {Path(csv1).name} and {Path(csv2).name}")
    print(f"Total rows: {len(result)}")
    print("\nSample of combined data:")
    print(result.head())
    
    # Save the combined result
    output_file = 'combined_patients.csv'
    result.to_csv(output_file, index=False)
    print(f"\nSaved combined data to: {output_file}")
    
    return result

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Combine two patient CSV files')
    parser.add_argument('csv1', help='First CSV file')
    parser.add_argument('csv2', help='Second CSV file')
    args = parser.parse_args()
    
    # Get the script's directory
    script_dir = Path(__file__).parent
    
    # Input file paths
    csv1_path = script_dir / args.csv1
    csv2_path = script_dir / args.csv2
    
    result = union_patient_csvs(csv1_path, csv2_path)

if __name__ == "__main__":
    main() 