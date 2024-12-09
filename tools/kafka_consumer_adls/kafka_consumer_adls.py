from confluent_kafka import Consumer, KafkaException
from azure.storage.filedatalake import DataLakeServiceClient
import yaml
import os
import sys
from datetime import datetime

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


def consume_from_kafka(topic, consumer_group, azure_storage_account_name, azure_storage_account_key, container_name, folder_path, bootstrap_servers, auto_offset_reset):
    """
    Consumes messages from a Kafka topic and writes to Azure Data Lake.
    Added parameters: bootstrap_servers, auto_offset_reset.
    """
    # Kafka consumer configuration with parameterized settings
    consumer_conf = {
        'bootstrap.servers': bootstrap_servers,
        'group.id': consumer_group,
        'auto.offset.reset': auto_offset_reset
    }

    # Create Kafka consumer
    consumer = Consumer(consumer_conf)
    consumer.subscribe([topic])

    # Azure Data Lake client configuration
    try:
        service_client = DataLakeServiceClient(account_url=f"https://{azure_storage_account_name}.dfs.core.windows.net",
                                               credential=azure_storage_account_key)
        file_system_client = service_client.get_file_system_client(file_system=container_name)
    except Exception as e:
        print(f"Error creating Azure Data Lake Service Client: {e}")
        return

    # Consume messages from Kafka and write to Azure Data Lake
    try:
        message_count = 0
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())
            else:
                message_count += 1
                data = msg.value().decode('utf-8')  # Ensure 'data' is defined here
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                file_name = f"{topic}_{timestamp}.json"
                file_path = os.path.join(folder_path, file_name)
                azure_storage_file_writer(data, file_path, file_system_client)  # 'data' is used here
                print(f"Processed message {message_count} from topic '{topic}', written to file '{file_name}'.")
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error in Kafka consumption or Azure writing: {e}")
    finally:
        consumer.close()



if __name__ == "__main__":
    azure_storage_account_name, azure_storage_account_key = read_azure_config()


    # Check if the credentials were read successfully
    if not azure_storage_account_name or not azure_storage_account_key:
        print("Failed to read Azure storage account credentials.")
        exit(1)

    # Check if the topic name is provided as a command-line argument
    if len(sys.argv) < 2:
        print("Usage: python script_name.py <kafka_topic>")
        exit(1)

    # Get the Kafka topic from the command-line argument
    topic = sys.argv[1]

    # Check if a consumer group name is provided as an argument
    consumer_group = sys.argv[2] if len(sys.argv) > 2 else "DefaultConsumerGroup"

    container_name = "landing"
    folder_path = f"kafka/{topic}"

   # Additional command line arguments for bootstrap_servers and auto_offset_reset
    bootstrap_servers = sys.argv[3] if len(sys.argv) > 3 else "localhost:9092"  # Default value as an example
    auto_offset_reset = sys.argv[4] if len(sys.argv) > 4 else "latest"  # Default value

    consume_from_kafka(topic, consumer_group, azure_storage_account_name, azure_storage_account_key, container_name, folder_path, bootstrap_servers, auto_offset_reset)