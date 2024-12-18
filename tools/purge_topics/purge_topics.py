import sys
from kafka.admin import KafkaAdminClient
from kafka.errors import KafkaError
import argparse

def read_topics_from_file(filename):
    """ Read topics from a text file, taking only the first column before the comma in each line, or the entire line if no comma is present. """
    with open(filename, 'r') as file:
        topics = [line.strip().split(',')[0] if ',' in line else line.strip() for line in file if line.strip()]
    return topics

def delete_topics(admin_client, topics):
    """ Delete topics from the Kafka cluster. """
    try:
        admin_client.delete_topics(topics)
        print(f"Topics deleted successfully: {', '.join(topics)}")
    except KafkaError as e:
        print(f"Failed to delete topics: {e}")

def check_topic_deletion_enabled(admin_client):
    """ Check if topic deletion is enabled on the Kafka broker. """
    try:
        # kafka-python doesn't provide direct access to broker configs
        # We'll assume topic deletion is enabled if we can connect to the broker
        admin_client.list_topics()
        return True
    except KafkaError as e:
        print(f"Error connecting to Kafka broker: {e}")
        return False

def main(filename, bootstrap_servers='localhost:9092'):
    # Kafka configuration
    try:
        admin_client = KafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            client_id='topic-deletion-client'
        )

        # Check if we can connect to the broker
        if not check_topic_deletion_enabled(admin_client):
            print("Cannot connect to Kafka broker. Please check your broker settings.")
            return

        topics = read_topics_from_file(filename)
        if topics:
            delete_topics(admin_client, topics)
        else:
            print("No topics found to delete.")

    finally:
        if 'admin_client' in locals():
            admin_client.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Purge Kafka topics listed in a file')
    parser.add_argument('--file-path', required=True,
                        help='Path to the CSV file containing topics')
    parser.add_argument('--bootstrap-servers', default='localhost:9092',
                        help='Kafka bootstrap servers (default: localhost:9092)')
    
    args = parser.parse_args()
    main(args.file_path, args.bootstrap_servers)
