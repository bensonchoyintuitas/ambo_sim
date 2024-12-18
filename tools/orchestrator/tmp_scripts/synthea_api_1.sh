#!/bin/bash
echo 'Date: 2024-12-18 21:01:52.612954'
echo 'Script: ./tmp_scripts/synthea_api_1.sh'
cd /mnt/d/Work/Intuitas/repo/synthea_api
source .venv/bin/activate
python3 -c 'print("Firing up synthea api")'
python3 api.py
python3 -c "import time; time.sleep(60)"
