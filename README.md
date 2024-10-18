# Ambulance simulator
a rectangular map to represent the town. Then some houses on the left. Hospitals on the right. and ambulances travelling between the houses and hospitals. In the houses, patients appear and then are taken from the houses to the hospitals.

**What you'll see:**
- A rectangular canvas representing the town.
- Houses on the left, hospitals on the right.
- Ambulances moving from houses (when there’s a patient) to the hospital.
- The system automatically generates patients in random houses, and ambulances respond to them.

# Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate 
pip install flask flask-socketio
```

# Run

```bash
python app.py
```
