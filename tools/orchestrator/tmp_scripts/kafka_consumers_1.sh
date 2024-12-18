#!/bin/bash
echo 'Date: 2024-12-18 16:23:26.138253'
echo 'Script: ./tmp_scripts/kafka_consumers_1.sh'
cd /mnt/d/Work/Intuitas/repo/ambo_sim/tools/kafka_consumer_adls
source .venv/bin/activate
python3 -c 'print("Firing up patient consumer to adls --auto-offset earliest --reset-offset")'
python3 kafka_consumer_adls.py --topic patient --container dev --path bronze/landing/kafka__local/ --consumer-group DefaultConsumerGroup --bootstrap-server localhost:9092 --auto-offset earliest --reset-offset
python3 -c "import time; time.sleep(60)"
