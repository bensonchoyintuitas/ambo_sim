#!/bin/bash
echo 'Date: 2024-12-18 21:02:38.741356'
echo 'Script: ./tmp_scripts/kafka_producers_2.sh'
cd /mnt/d/Work/Intuitas/repo/ambo_sim/tools/kafka_producer
source .venv/bin/activate
python3 -c 'print("Firing up kafka_producer condition")'
python3 produce_json.py --input ../../fhir_export/session_20241218_210201/condition/ --output-topic condition --continuous 30
python3 -c "import time; time.sleep(60)"
