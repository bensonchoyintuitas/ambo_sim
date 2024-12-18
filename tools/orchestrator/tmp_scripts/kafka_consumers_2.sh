#!/bin/bash
echo 'Date: 2024-12-18 16:23:26.146297'
echo 'Script: ./tmp_scripts/kafka_consumers_2.sh'
cd /mnt/d/Work/Intuitas/repo/ambo_sim/tools/kafka_consumer_adls
source .venv/bin/activate
python3 -c 'print("Firing up encounter_ed_presentation consumer to adls --auto-offset earliest --reset-offset")'
python3 kafka_consumer_adls.py --topic encounter_ed_presentation --container dev --path bronze/landing/kafka__local/ --consumer-group DefaultConsumerGroup --bootstrap-server localhost:9092 --auto-offset earliest --reset-offset
python3 -c "import time; time.sleep(60)"
