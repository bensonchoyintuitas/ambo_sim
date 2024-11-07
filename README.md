# Ambulance simulator
a rectangular map to represent the town. Then some houses on the left. Hospitals on the right. and ambulances travelling between the houses and hospitals. In the houses, patients appear and then are taken from the houses to the hospitals.

See [business_process.md](business_process.md) for the business process.
See [fhir_process.md](fhir_process.md) for the FHIR resources and exchanges.

**What you'll see:**
- A rectangular canvas representing the town.
- Houses on the left, hospitals on the right.
- Ambulances moving from houses (when there’s a patient) to the hospital.
- The system automatically generates patients in random houses, and ambulances respond to them.

# Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate 
pip install -r requirements.txt
```

# Run

```bash
source .venv/bin/activate 
python3 app.py
```

# Todo

# Stage 1
- [x] Create patients as objects
- [x] Make more than one patient in a house
- [x] Display the patient id in an array in either house, ambo or hospital
- [x] Add wait time
- [x] Assign nearest available ambulance
- [x] Separate event logs by class

# Stage 2 Patients have associated FHIR resources 
- [-] Switch approach and use Synthea as a seed for each patient
- [-] Find a better LLM for generating FHIR resources


# Stage 3
- [ ] Train a custom LLM for generating FHIR resources correctly to a defined template
- [ ] Reflect more accurate patient flow (see [fhir_process.md](fhir_process.md))
- [ ] Have patient-centric view of flow events (filterable)
- [ ] Ambulances cannot leave if waiting
- [ ] Make patient ID more unique and consistent

# Stage 4
- [ ] Use icons 
- [ ] Agent-driven independent ambulances
- [ ] Configurable number of ambulances, hospitals and houses





