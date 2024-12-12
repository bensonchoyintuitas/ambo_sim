from azure.storage.filedatalake import DataLakeServiceClient
import yaml
import os
import sys
from datetime import datetime
import argparse
from kafka import KafkaConsumer, KafkaAdminClient
import json

def read_azure_config(config_file='azure_config.yml'):
    """
    Reads Azure storage configuration from a YAML file.
    """
    try:
        with open(config_file, 'r') as file:
            config = yaml.safe_load(file)
        return config['azure_storage_account_name'], config['azure_storage_account_key']
    except Exception as e:
        print(f"Error reading Azure config: {e}")
        return None, None


def azure_storage_file_writer(data, file_path, file_system_client):
    """
    Writes data to Azure Data Lake file, creating the directory and file if they don't exist.
    """
    try:
        # Split the file path to get the directory and file name
        directory_path, file_name = os.path.split(file_path)
        
        # Get the directory client
        directory_client = file_system_client.get_directory_client(directory_path)
        
        # Check if the directory exists, create if not
        if not directory_client.exists():
            directory_client.create_directory()

        # Get the file client
        file_client = directory_client.get_file_client(file_name)

        # Create the file if it doesn't exist and append data
        if not file_client.exists():
            file_client.create_file()
        file_client.append_data(data, offset=0, length=len(data))
        file_client.flush_data(len(data))
    except Exception as e:
        print(f"Error writing to Azure Data Lake: {e}")


def consume_from_kafka(topic, consumer_group, azure_storage_account_name, azure_storage_account_key, 
                      container_name, folder_path, bootstrap_servers, auto_offset_reset, reset_offset):
    """
    Consumes messages from a Kafka topic and writes to Azure Data Lake using kafka-python.
    """
    # Reset offsets if requested
    if reset_offset:
        try:
            admin_client = KafkaAdminClient(bootstrap_servers=bootstrap_servers)
            admin_client.delete_consumer_groups([consumer_group])
            print(f"Reset offset for consumer group: {consumer_group}")
        except Exception as e:
            print(f"Warning: Could not reset consumer group: {e}")
    
    # Create consumer
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=consumer_group,
        auto_offset_reset=auto_offset_reset,
        value_deserializer=lambda x: x.decode('utf-8')
    )

    # Azure Data Lake client configuration
    try:
        service_client = DataLakeServiceClient(
            account_url=f"https://{azure_storage_account_name}.dfs.core.windows.net",
            credential=azure_storage_account_key
        )
        file_system_client = service_client.get_file_system_client(file_system=container_name)
    except Exception as e:
        print(f"Error creating Azure Data Lake Service Client: {e}")
        return

    # Add topic to folder path
    topic_folder_path = os.path.join(folder_path, topic)

    # Consume messages from Kafka and write to Azure Data Lake
    try:
        message_count = 0
        start_time = datetime.now()
        
        for message in consumer:
            message_count += 1
            data = message.value  # Already decoded due to value_deserializer
            
            # Get current timestamp and create date-based partition folders
            current_time = datetime.now()
            date_partition = os.path.join(
                str(current_time.year),
                f"{current_time.month:02d}",
                f"{current_time.day:02d}"
            )
            
            # Create file name with timestamp
            timestamp = current_time.strftime("%Y%m%d%H%M%S%f")
            file_name = f"{topic}_{timestamp}.json"
            
            # Combine all path components
            file_path = os.path.join(topic_folder_path, date_partition, file_name)
            
            # Convert data to bytes if it isn't already
            if isinstance(data, str):
                data = data.encode('utf-8')
                
            azure_storage_file_writer(data, file_path, file_system_client)
            
            # Calculate and display processing rate every 10 messages
            if message_count % 10 == 0:
                elapsed_time = (datetime.now() - start_time).total_seconds()
                rate = message_count / elapsed_time if elapsed_time > 0 else 0
                print(f"Processed {message_count} messages from topic '{topic}'. Rate: {rate:.2f} msgs/sec")
            
    except KeyboardInterrupt:
        print("Shutting down consumer...")
    except Exception as e:
        print(f"Error in Kafka consumption or Azure writing: {e}")
    finally:
        consumer.close()



if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Kafka consumer that writes to Azure Data Lake Storage.')
    
    # Required arguments
    parser.add_argument('--topic', required=True,
                      help='Name of the Kafka topic to consume from')
    parser.add_argument('--container', required=True,
                      help='Azure Storage container name')
    parser.add_argument('--path', required=True,
                      help='Base folder path in the container')
    
    # Optional arguments
    parser.add_argument('--consumer-group', default="DefaultConsumerGroup",
                      help='Consumer group ID (default: DefaultConsumerGroup)')
    parser.add_argument('--bootstrap-server', default="localhost:9092",
                      help='Kafka bootstrap server (default: localhost:9092)')
    parser.add_argument('--auto-offset', default="latest", choices=['latest', 'earliest'],
                      help='Auto offset reset behavior (default: latest)')
    parser.add_argument('--reset-offset', action='store_true',
                      help='Reset consumer group offset before starting')

    args = parser.parse_args()

    # Read Azure configuration
    azure_storage_account_name, azure_storage_account_key = read_azure_config()

    # Check if the credentials were read successfully
    if not azure_storage_account_name or not azure_storage_account_key:
        print("Failed to read Azure storage account credentials.")
        exit(1)

    # Call the main function with parsed arguments
    consume_from_kafka(
        topic=args.topic,
        consumer_group=args.consumer_group,
        azure_storage_account_name=azure_storage_account_name,
        azure_storage_account_key=azure_storage_account_key,
        container_name=args.container,
        folder_path=args.path,
        bootstrap_servers=args.bootstrap_server,
        auto_offset_reset=args.auto_offset,
        reset_offset=args.reset_offset
    )