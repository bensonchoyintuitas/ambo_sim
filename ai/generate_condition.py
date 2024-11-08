import ollama
from datetime import datetime, timezone
import json
import uuid

def generate_condition(patient_id, llm_model='llama3.1:8b'):
    """Generate a FHIR Condition resource for a given patient ID.
    
    Args:
        patient_id (str): The ID of the patient this condition is for
        llm_model (str, optional): The Ollama model to use. Defaults to 'llama3:8b'
    
    Returns:
        dict: A FHIR Condition resource, or None if generation fails
    """
    # Get current time in UTC and format it
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    condition_id = str(uuid.uuid4())

    prompt = f"""Generate a valid FHIR R4 Condition resource that exactly follows this structure:
    {{
        "resourceType": "Condition",
        "id": "{condition_id}",
        "clinicalStatus": {{
            "coding": [{{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                "code": "active",
                "display": "Active"
            }}]
        }},
        "verificationStatus": {{
            "coding": [{{
                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                "code": "confirmed",
                "display": "Confirmed"
            }}]
        }},
        "severity": {{
            "coding": [{{
                "system": "http://snomed.info/sct",
                "code": "<generate valid SNOMED CT severity code only - no other symbols>",
                "display": "<severity display: mild, moderate, or severe>"
            }}]
        }},
        "category": [{{
            "coding": [{{
                "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                "code": "encounter-diagnosis",
                "display": "Encounter Diagnosis"
            }}]
        }}],
        "code": {{
            "coding": [{{
                "system": "http://snomed.info/sct",
                "code": "<generate valid SNOMED CT code - no other symbols>",
                "display": "<matching SNOMED display name>"
            }}],
            "text": "<human readable condition description>"
        }},
        "subject": {{
            "reference": "Patient/{patient_id}"
        }},
        "onsetDateTime": "{current_time}",
        "recordedDate": "{current_time}",
        "note": [{{
            "text": "<detailed clinical notes about the emergency presentation>"
        }}]
    }}

    Requirements:
    - Use a real SNOMED CT code and matching display name for an emergency condition
    - Use appropriate SNOMED CT severity codes (e.g., 24484000 |Severe|, 6736007 |Moderate|, 255604002 |Mild|)
    - Make the condition text and clinical notes realistic for an emergency presentation
    - Return valid FHIR JSON only, no markdown or explanation

    Return the JSON only."""

    try:
        response = ollama.generate(model=llm_model, prompt=prompt)
        
        # Extract just the JSON content from the response
        response_text = response['response']
        
        # Find the JSON content between curly braces
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start >= 0 and end > start:
            try:
                condition = json.loads(response_text[start:end])
                
                # Validate that it's a Condition resource
                if condition.get("resourceType") != "Condition":
                    print("Generated resource is not a Condition")
                    return None
                
                return condition
                
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {str(e)}")
                return None
        else:
            print("No valid JSON found in response")
            return None
            
    except Exception as e:
        print(f"Error generating Condition resource: {str(e)}")
        return None

if __name__ == '__main__':
    # Test the function with a sample patient ID
    test_patient_id = "test-patient-123"
    
    # Test with default model
    print("Testing with default model:")
    condition = generate_condition(test_patient_id)
    if condition:
        print(json.dumps(condition, indent=2))
    
    # Test with specific model
    print("\nTesting with specific model:")
    condition = generate_condition(test_patient_id, llm_model='gemma:2b')
    if condition:
        print(json.dumps(condition, indent=2))