#!/bin/bash
echo 'Date: 2024-12-18 20:59:51.837910'
echo 'Script: ./tmp_scripts/infrastructure_1.sh'
cd /mnt/d/Work/Intuitas/repo/ambo_sim/infrastructure/confluent
python3 -c 'print("Firing up confluent")'
python3 -c "import time; time.sleep(1)"
docker-compose up -d
