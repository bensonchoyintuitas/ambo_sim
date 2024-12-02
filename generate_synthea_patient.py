import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from threading import Lock
import random
import uuid
import os
import json
from datetime import datetime

# Create a session with connection pooling and retry strategy
def create_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(
        pool_connections=10,
        pool_maxsize=10,
        max_retries=retries
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Add a lock for the API call
api_call_lock = Lock()

def generate_fallback_patient(session_dir=None):
    """Generate a basic patient with minimal FHIR resources."""
    # Generate basic patient data
    patient_id = f"pat-{random.randint(1000, 9999)}"
    given_name = random.choice(['John', 'Jane', 'Bob', 'Alice', 'Charlie'])
    family_name = random.choice(['Smith', 'Johnson', 'Williams', 'Brown', 'Jones'])
    
    # Create FHIR patient resource
    fhir_patient = {
        'resourceType': 'Patient',
        'id': patient_id,
        'name': [{
            'given': [given_name],
            'family': family_name
        }],
        'birthDate': '1970-01-01'  # Default birthdate
    }
    
    # If session_dir is provided, save the FHIR resource
    if session_dir:
        try:
            patient_dir = os.path.join(session_dir, 'patient')
            os.makedirs(patient_dir, exist_ok=True)
            
            filename = f"patient_{patient_id}.json"
            filepath = os.path.join(patient_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(fhir_patient, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving FHIR patient resource: {str(e)}")
    
    return {
        'patient': fhir_patient,
        'fhir_resources': {
            'patient': fhir_patient
        }
    }

def generate_fhir_resources():
    """Thread-safe function to generate FHIR resources using Synthea API."""
    session = create_session()
    output_dir = f"output_fhir/session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        with api_call_lock:
            response = session.post('http://localhost:5001/generate_patient_bundle')
            response.raise_for_status()
            return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error generating FHIR resources: {str(e)}")
        logging.info("Using fallback patient generation")
        return generate_fallback_patient(output_dir)
    finally:
        session.close()