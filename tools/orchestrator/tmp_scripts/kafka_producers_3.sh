#!/bin/bash
echo 'Date: 2024-12-18 21:02:38.744789'
echo 'Script: ./tmp_scripts/kafka_producers_3.sh'
cd /mnt/d/Work/Intuitas/repo/ambo_sim/tools/kafka_producer
source .venv/bin/activate
python3 -c 'print("Firing up kafka_producer encounter_discharge")'
python3 produce_json.py --input ../../fhir_export/session_20241218_210201/encounter_discharge/ --output-topic encounter_discharge --continuous 30
python3 -c "import time; time.sleep(60)"
