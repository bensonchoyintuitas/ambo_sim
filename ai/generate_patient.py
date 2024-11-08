import ollama
import random
from datetime import datetime, timezone
import json
import uuid

def generate_fhir_resources(patient_guid=None):
    """Generate FHIR resources for a patient and their condition."""
    # Get current time in UTC and format it
    patient_guid = patient_guid or str(uuid.uuid4())
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    
    # Generate a random seed
    seed = random.randint(1, 1000000)

    prompt = f"""Using seed {seed} for randomization: Generate two valid FHIR R4 resources:
    1. A Patient resource with:
       - Use this exact ID: {patient_guid}
       - random First and Last name (IMPORTANT: 
         * Make it truly random and unique
         * DO NOT use common names like John, Jane, Smith, etc.
         * First name should be uncommon but real
         * Last name should be uncommon but real
       - random street 
       - city in Brisbane Australia 
       - random contacts
       - random dob of YYYY-MM-DD format (not just 1990-01-01)
    2. A Condition resource that:
       - References the patient
       - onsetDateTime is {current_time}
       - Represents a condition that is realistic for an emergency presentation reason
       - Includes appropriate clinical status, verification status, and severity
       - Uses proper SNOMED CT codes and includes severity and display
       - Includes onset date/time and when recorded
       - Has clinical notes in the note field

    Return valid FHIR JSON only."""

    try:
        response = ollama.generate(model='gemma:2b', prompt=prompt)
        
        # Extract just the JSON content from the response
        response_text = response['response']
        
        # Parse the response into a FHIR Bundle
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": []
        }
        
        # Split the response into separate JSON objects and parse them
        json_texts = response_text.split('```json')
        for json_text in json_texts:
            if '{' in json_text and '}' in json_text:
                start = json_text.find('{')
                end = json_text.rfind('}') + 1
                try:
                    resource = json.loads(json_text[start:end])
                    bundle["entry"].append({"resource": resource})
                except json.JSONDecodeError:
                    continue
        
        return bundle if bundle["entry"] else None
        
    except Exception as e:
        print(f"Error generating FHIR resources: {str(e)}")
        return None

if __name__ == '__main__':
    # Test the function
    resources = generate_fhir_resources()
    if resources:
        print(json.dumps(resources, indent=2))
