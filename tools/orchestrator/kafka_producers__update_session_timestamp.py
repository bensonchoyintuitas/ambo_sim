import yaml
import sys
from datetime import datetime
import re
import os
import argparse

def get_latest_session_folder(root_path):
    # Verify directory exists
    if not os.path.exists(root_path):
        raise FileNotFoundError(f"Directory not found: {root_path}")
    
    # Get all directories that match the session pattern
    session_dirs = [
        d for d in os.listdir(root_path)
        if os.path.isdir(os.path.join(root_path, d))
        and re.match(r'session_\d{8}_\d{6}$', d)
    ]
    
    if not session_dirs:
        raise ValueError(f"No session directories found in {root_path}")
    
    # Sort by timestamp (the directory name itself is sortable in YYYYMMDD_HHMMSS format)
    latest_session = sorted(session_dirs)[-1]
    
    return latest_session

def update_session_timestamp(file_path, new_session=None):
    # Verify file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    # Read the YAML file
    with open(file_path, 'r') as file:
        content = file.read()
    
    # If no new session provided, generate current timestamp
    if not new_session:
        new_session = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Find and replace all occurrences of session_YYYYMMDD_HHMMSS pattern
    updated_content = re.sub(
        r'session_\d{8}_\d{6}',
        new_session,
        content
    )
    
    # Write back to file
    with open(file_path, 'w') as file:
        file.write(updated_content)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Update session timestamps in YAML file')
    parser.add_argument('--yaml-file', required=True, help='Path to the kafka_producers.yml file')
    parser.add_argument('--sessions-root', required=True, help='Root path containing session folders')
    parser.add_argument('--session-name', help='Optional specific session name to use')
    
    args = parser.parse_args()
    
    try:
        # If no session_name provided, try to get the latest session folder
        new_session = args.session_name
        if not new_session:
            new_session = get_latest_session_folder(args.sessions_root)
        
        update_session_timestamp(args.yaml_file, new_session)
        print(f"Successfully updated session timestamp in {args.yaml_file}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)