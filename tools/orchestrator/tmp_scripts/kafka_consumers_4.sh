#!/bin/bash
echo 'Date: 2024-12-18 16:14:11.006964'
echo 'Script: ./tmp_scripts/kafka_consumers_4.sh'
cd /mnt/d/Work/Intuitas/repo/ambo_sim/tools/kafka_consumer_adls
source .venv/bin/activate
python3 -c 'print("Firing up condition consumer to adls --auto-offset earliest --reset-offset")'
python3 kafka_consumer_adls.py --topic condition --container dev --path bronze/landing/kafka__local/ --consumer-group DefaultConsumerGroup --bootstrap-server localhost:9092 --auto-offset earliest --reset-offset
python3 -c "import time; time.sleep(60)"
