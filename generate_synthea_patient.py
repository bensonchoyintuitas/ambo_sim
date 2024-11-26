import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from threading import Lock
import random

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

def generate_fallback_patient():
    """Generate a simple fallback patient when API fails."""
    birth_year = random.randint(1923, 2023)  # Random year under 100 years old
    given_name = "M" if random.choice(["male", "female"]) == "male" else "F"
    patient_id = f"{given_name}-{random.randint(1000, 9999)}"  # Consistent ID with given name
    return {
        "patient": {
            "id": patient_id,
            "resourceType": "Patient",
            "gender": random.choice(["male", "female"]),
            "birthDate": f"{birth_year}-01-01",  # Valid birthdate
            "name": [{
                "use": "official",
                "family": "Doe",
                "given": [f"{patient_id}"]
            }]
        }
    }

def generate_fhir_resources():
    """Thread-safe function to generate FHIR resources using Synthea API."""
    session = create_session()
    try:
        # Use lock to ensure thread safety of API calls
        with api_call_lock:
            response = session.post('http://localhost:5001/generate_patient_bundle')
            response.raise_for_status()
            return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error generating FHIR resources: {str(e)}")
        logging.info("Using fallback patient generation")
        return generate_fallback_patient()
    finally:
        session.close() 