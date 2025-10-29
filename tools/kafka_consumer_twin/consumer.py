import argparse
import json
import time
import sys
from typing import List
from kafka import KafkaConsumer
import requests


def run(bootstrap: str, group: str, topics: List[str], twin_base_url: str, auto_offset: str):
    consumer = KafkaConsumer(
        *topics,
        bootstrap_servers=[bootstrap],
        group_id=group,
        auto_offset_reset=auto_offset,
        enable_auto_commit=True,
        max_partition_fetch_bytes=8 * 1024 * 1024,
        api_version=(3, 5, 1),
        value_deserializer=lambda v: v.decode('utf-8', errors='ignore')
    )
    ingest_url = twin_base_url.rstrip('/') + '/ingest/kafka'

    backoff = 1.0
    while True:
        try:
            msg_pack = consumer.poll(timeout_ms=1000, max_records=100)
            for tp, messages in msg_pack.items():
                for m in messages:
                    try:
                        payload = {
                            "topic": tp.topic,
                            "partition": tp.partition,
                            "offset": m.offset,
                            "timestamp": None,
                            "valueJson": m.value,
                        }
                        # Try to parse JSON to ensure valid body for Twin
                        try:
                            json.loads(m.value)
                        except Exception:
                            # Non-JSON payloads are ignored
                            continue
                        r = requests.post(ingest_url, json=payload, timeout=5)
                        if r.status_code >= 300:
                            print(f"Ingest error {r.status_code}: {r.text}")
                    except Exception as e:
                        print(f"Error handling message: {e}")
            backoff = 1.0
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Poll error: {e}. Backing off {backoff:.1f}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 10.0)


def main():
    parser = argparse.ArgumentParser(description='Ambo Twin Kafka consumer')
    parser.add_argument('--bootstrap-server', default='localhost:9092')
    parser.add_argument('--group', default='ambo-twin-live')
    parser.add_argument('--topics', nargs='+', required=False,
                        default=['patient', 'condition', 'encounter_ed_presentation', 'encounter_discharge',
                                 'event_ambulance_heading_to_house', 'event_ambulance_redirect', 'event_arrive_hospital',
                                 'event_discharge', 'event_hospital_location', 'event_off_stretcher', 'event_offload',
                                 'event_pickup_and_depart', 'event_ramping'])
    parser.add_argument('--twin-url', default='http://localhost:5001')
    parser.add_argument('--auto-offset', default='latest', choices=['latest', 'earliest'])
    args = parser.parse_args()

    try:
        run(args.bootstrap_server, args.group, args.topics, args.twin_url, args.auto_offset)
    except KeyboardInterrupt:
        print("Stopping consumer...")
    finally:
        sys.exit(0)


if __name__ == '__main__':
    main()


