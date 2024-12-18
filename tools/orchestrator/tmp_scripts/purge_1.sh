#!/bin/bash
echo 'Date: 2024-12-18 21:00:52.219118'
echo 'Script: ./tmp_scripts/purge_1.sh'
cd /mnt/d/Work/Intuitas/repo/ambo_sim/tools/purge_topics
source .venv/bin/activate
python3 -c 'print("Firing up purge topics")'
python3 purge_topics.py --file-path ./topics_to_delete.txt --bootstrap-servers localhost:9092
python3 -c "import time; time.sleep(60)"
