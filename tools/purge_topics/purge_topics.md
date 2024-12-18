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
python3 purge_topics.py --file-path ./topics_to_delete.txt --bootstrap-servers localhost:9092

```

