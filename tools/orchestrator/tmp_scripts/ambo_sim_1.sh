#!/bin/bash
echo 'Date: 2024-12-18 21:01:57.949963'
echo 'Script: ./tmp_scripts/ambo_sim_1.sh'
cd /mnt/d/Work/Intuitas/repo/ambo_sim
source .venv/bin/activate
python3 -c 'print("Firing up ambo_sim --llm-model llama3.1:8b --fhir-export")'
python3 app.py --llm-model llama3.1:8b --fhir-export
python3 -c "import time; time.sleep(60)"
