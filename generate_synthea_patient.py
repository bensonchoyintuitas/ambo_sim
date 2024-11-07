import requests
import json
import random

def generate_fhir_resources(patient_guid=None):
    """
    Generate FHIR resources by calling the Synthea API
    
    Args:
        patient_guid (str): Optional GUID for the patient (not used)
        
    Returns:
        dict: Patient resource and condition resource
    """
    try:
        # Call the Synthea API
        response = requests.post('http://127.0.0.1:5001/generate_patient')
        
        if response.status_code == 200:
            # Get the patient data directly
            patient_resource = response.json()
            
            # Create a bundle-like structure for compatibility
            return {
                "patient": patient_resource,
                "condition": {
                    "resourceType": "Condition",
                    "code": {
                        "text": "Emergency Condition"
                    }
                }
            }
        else:
            print(f"Error calling Synthea API: {response.status_code}")
            return create_fallback_resources()
            
    except Exception as e:
        print(f"Error generating FHIR resources: {str(e)}")
        return create_fallback_resources()

def create_fallback_resources():
    """Create fallback resources when API fails"""
    return {
        "patient": {
            "resourceType": "Patient",
            "id": f"fallback-{random.randint(1000,9999)}",
            "name": [{"given": ["Unknown"], "family": "Patient"}],
            "gender": "unknown",
            "birthDate": "unknown"
        },
        "condition": {
            "resourceType": "Condition",
            "code": {
                "text": "Emergency Condition"
            }
        }
    } 