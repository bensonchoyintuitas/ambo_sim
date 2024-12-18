#!/bin/bash
echo 'Date: 2024-12-18 21:25:31.387022'
echo 'Script: ./tmp_scripts/infrastructure_1.sh'
cd /mnt/d/Work/Intuitas/repo/ambo_sim/infrastructure/confluent
python3 -c 'print("Firing up confluent")'
python3 -c "import time; time.sleep(1)"
docker-compose up -d
