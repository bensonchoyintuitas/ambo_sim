# Introduction
use to purge topics from the kafka cluster


# Getting started
<!-- linux -->
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
# run
<!-- linux -->
```bash
source .venv/bin/activate
python3 main.py ./topics_to_delete.txt
python3 main.py /mnt/d/Work/Intuitas/repo/intuitas_blueprint/processors/streaming/synthea_processor/synthea_processor__new_topics.log
python3 main.py /mnt/d/Work/Intuitas/repo/intuitas_blueprint/processors/streaming/fhir_normaliser/fhir_normaliser__new_topics.log


```
processors\streaming\synthea_processor\synthea_processor__new_topics.log
# Status
Dev - not added to end-to-end yet

