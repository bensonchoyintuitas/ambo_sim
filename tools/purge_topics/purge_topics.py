import sys
from confluent_kafka.admin import AdminClient, NewTopic, ConfigResource
from confluent_kafka import KafkaException

def read_topics_from_file(filename):
    """ Read topics from a text file, taking only the first column before the comma in each line, or the entire line if no comma is present. """
    with open(filename, 'r') as file:
        topics = [line.strip().split(',')[0] if ',' in line else line.strip() for line in file if line.strip()]
    return topics


def delete_topics(admin_client, topics):
    """ Delete topics from the Kafka cluster. """
    futures = admin_client.delete_topics(topics, operation_timeout=30)
    for topic, future in futures.items():
        try:
            future.result()  # Block until the future completes
            print(f"Topic {topic} deleted successfully.")
        except Exception as e:
            print(f"Failed to delete topic {topic}: {e}")

def check_topic_deletion_enabled(admin_client):
    """ Check if topic deletion is enabled on the Kafka broker. """
    try:
        cluster_metadata = admin_client.list_topics(timeout=10)
        if cluster_metadata.brokers:
            broker_id = next(iter(cluster_metadata.brokers))
            broker_resource = ConfigResource(ConfigResource.Type.BROKER, str(broker_id))
            futures = admin_client.describe_configs([broker_resource])

            for res, f in futures.items():
                config = f.result()
                delete_topic_enabled = config['delete.topic.enable'].value
                print(f"Delete topic enabled on broker: {delete_topic_enabled}")
                return delete_topic_enabled.strip('"') == 'true'
        else:
            print("No brokers found in the cluster metadata.")
            return False
    except KafkaException as e:
        print(f"Error retrieving cluster metadata: {e}")
        return False

def main(filename):
    # Kafka configuration: Replace 'localhost:9092' with your Kafka broker's address
    config = {
        'bootstrap.servers': 'localhost:9092'
    }
    admin_client = AdminClient(config)

    # Check if topic deletion is enabled
    if not check_topic_deletion_enabled(admin_client):
        print("Topic deletion is not enabled on your Kafka broker, or broker is not accessible. Please check your broker settings.")
        return

    topics = read_topics_from_file(filename)
    if topics:
        delete_topics(admin_client, topics)
    else:
        print("No topics found to delete.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python main.py <path_to_csv_file>")
        sys.exit(1)
    file_path = sys.argv[1]
    main(file_path)
