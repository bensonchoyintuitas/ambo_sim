# Introduction 
This application acts as a generic orchestrator that runs any python command in any type of terminal as a parallel thread.

##  helpers
Some helpers have been created to automate generation of scripts
- [kafka_producers__update_session_timestamp.md](kafka_producers__update_session_timestamp.md)


# Requirements
- latest WSL2 with gui support (xterm)
- docker needs to be running

# Getting started
<!-- linux -->
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

sudo apt-get install xfonts-base
sudo apt-get install xterm
```
# Running
<!-- example -->
python3 main.py [command yaml]

<!-- linux -->
```bash
source .venv/bin/activate
python3 main.py purge.yml (optional)
python3 main.py 'end_to_end.yml' 
```

<!-- example -->
xterm -e "echo 'Set 1';cd '/mnt/d/work/Intuitas/repo/intuitas_blueprint/producers/synthea_producer' \
;date; source .venv/bin/activate;  pwd; ls ; python main.py; python3 -c \"import time; time.sleep(10)\"; "