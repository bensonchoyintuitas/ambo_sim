import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from threading import Lock

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
        return None
    finally:
        session.close() 