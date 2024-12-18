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
    # Generate patient ID first to use its number for name suffixes
    patient_number = random.randint(1000, 9999)
    patient_id = f"pat-{patient_number}"
    
    # Separate lists for male and female given names
    male_given_names = ['John', 'Bob', 'Charlie', 'Michael', 'David', 'Chris', 'Daniel', 'James', 'Matthew', 'Andrew']
    female_given_names = ['Jane', 'Alice', 'Emily', 'Sarah', 'Laura', 'Jessica', 'Emma', 'Olivia', 'Sophia', 'Isabella']
    family_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
                    'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin']
    
    # Randomly select gender
    gender = random.choice(['male', 'female'])
    
    # Choose given name based on gender
    if gender == 'male':
        given_name = random.choice(male_given_names) + str(patient_number)
    else:
        given_name = random.choice(female_given_names) + str(patient_number)
    
    family_name = random.choice(family_names) + str(patient_number)
    
    # Generate random birthdate for someone over 18
    current_year = datetime.now().year
    year = random.randint(current_year - 80, current_year - 18)  # Between 18 and 80 years old
    month = random.randint(1, 12)
    # Handle different days per month
    if month in [4, 6, 9, 11]:
        day = random.randint(1, 30)
    elif month == 2:
        # Handle leap years
        if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
            day = random.randint(1, 29)
        else:
            day = random.randint(1, 28)
    else:
        day = random.randint(1, 31)
    
    # Format date as YYYY-MM-DD
    birthDate = f"{year}-{month:02d}-{day:02d}"
    
    # Create FHIR patient resource
    fhir_patient = {
        'resourceType': 'Patient',
        'id': patient_id,
        'name': [{
            'given': [given_name],
            'family': family_name
        }],
        'birthDate': birthDate,  # Use the random birthdate
        'gender': gender,  # Add gender element
        'identifier': [  # Add identifier element
            {
                'system': 'ambosim/fallback',
                'value': patient_id
            }
        ]
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

def generate_fhir_resources(session_dir=None):
    """Thread-safe function to generate FHIR resources using Synthea API."""
    session = create_session()
    
    # Only create output_dir if session_dir is provided
    output_dir = session_dir if session_dir else None
    
    try:
        with api_call_lock:
            logging.info(f"Calling Synthea API with session_dir: {session_dir}")
            response = session.post('http://localhost:5001/generate_patient_bundle')
            response.raise_for_status()
            patient_data = response.json()
            
            # Save the FHIR patient resource if session_dir is provided
            if session_dir:
                try:
                    patient_dir = os.path.join(session_dir, 'patient')
                    os.makedirs(patient_dir, exist_ok=True)
                    
                    patient_id = patient_data['patient']['id']
                    filename = f"patient_{patient_id}.json"
                    filepath = os.path.join(patient_dir, filename)
                    with open(filepath, 'w') as f:
                        json.dump(patient_data['patient'], f, indent=2)
                    logging.info(f"Successfully saved patient {patient_id} to {filepath}")
                except Exception as e:
                    logging.error(f"Error saving FHIR patient resource: {str(e)}")
            
            return patient_data
    except requests.exceptions.RequestException as e:
        logging.error(f"Error generating FHIR resources: {str(e)}")
        logging.info("Using fallback patient generation")
        return generate_fallback_patient(output_dir)
    finally:
        session.close()