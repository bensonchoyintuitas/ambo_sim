import json
import argparse
from pathlib import Path
import time
import sys
from kafka import KafkaProducer
from datetime import datetime

def log_processing(input_file, topic_name, log_path):
    """
    Log processing details to a CSV file
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Create log entry
    log_entry = f"{timestamp},{str(input_file)},{topic_name}\n"
    
    # Append to log file
    with open(log_path, 'a') as f:
        f.write(log_entry)

def check_if_processed(input_file, log_path):
    """
    Check if a file has already been processed by looking in the log
    """
    if not log_path.exists():
        return False
        
    with open(log_path, 'r') as f:
        return str(input_file) in f.read()

def produce_json_file(producer, input_file, topic_name):
    """
    Produce a single JSON file to Kafka
    """
    try:
        with open(input_file, 'r') as f:
            json_data = json.load(f)
        
        # Convert to string and encode
        message = json.dumps(json_data).encode('utf-8')
        
        # Send to Kafka
        future = producer.send(topic_name, value=message)
        # Wait for message to be sent
        future.get(timeout=10)
        
        print(f"Successfully produced message from {input_file} to topic {topic_name}")
        return True
    except Exception as e:
        print(f"Error producing message from {input_file}: {str(e)}")
        return False

def process_input_path(input_path, topic_name, producer, force_all=False):
    """
    Process either a single JSON file or all JSON files in a directory
    """
    log_path = Path('kafka_producer.log')
    
    if input_path.is_file():
        if input_path.suffix.lower() == '.json':
            if not force_all and check_if_processed(input_path, log_path):
                print(f"Skipping already processed file: {input_path}")
                return
            if produce_json_file(producer, input_path, topic_name):
                log_processing(input_path, topic_name, log_path)
        else:
            print(f"Skipping non-JSON file: {input_path}")
    
    elif input_path.is_dir():
        json_files = list(input_path.glob('**/*.json'))
        if not json_files:
            print(f"No JSON files found in directory: {input_path}")
            return
        
        print(f"Found {len(json_files)} JSON files to process")
        for json_file in json_files:
            if not force_all and check_if_processed(json_file, log_path):
                print(f"Skipping already processed file: {json_file}")
                continue
            print(f"\nProcessing: {json_file}")
            if produce_json_file(producer, json_file, topic_name):
                log_processing(json_file, topic_name, log_path)
    else:
        print(f"Input path does not exist: {input_path}")

def main():
    parser = argparse.ArgumentParser(description='Produce JSON files to Kafka topic')
    parser.add_argument('--input', required=True, help='Input JSON file or directory containing JSON files')
    parser.add_argument('--output-topic', required=True, help='Kafka topic name')
    parser.add_argument('--broker', default='localhost:9092', help='Kafka broker address')
    parser.add_argument('--force-all', action='store_true', 
                        help='Process all files even if already in log')
    parser.add_argument('--continuous', type=int, metavar='SECONDS',
                        help='Run continuously with specified interval in seconds')
    args = parser.parse_args()
    
    # Get the script's directory
    script_dir = Path(__file__).parent
    
    # Input path - allow for absolute paths or paths relative to current directory
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = script_dir / input_path

    # Create Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=[args.broker],
        max_request_size=40485760,  # Match broker config from docker-compose
        api_version=(3, 5, 1)
    )

    try:
        if args.continuous:
            interval = args.continuous
            print(f"\nRunning in continuous mode with {interval}-second intervals. Press Ctrl+C to stop.")
            counter = 1
            while True:
                print(f"\n=== Run #{counter} ===")
                process_input_path(input_path, args.output_topic, producer, args.force_all)
                print(f"\nCompleted run #{counter}. Waiting {interval} seconds before next run...")
                time.sleep(interval)
                counter += 1
        else:
            process_input_path(input_path, args.output_topic, producer, args.force_all)
    except KeyboardInterrupt:
        print("\nStopping producer...")
    finally:
        producer.close()
        sys.exit(0)

if __name__ == "__main__":
    main() 