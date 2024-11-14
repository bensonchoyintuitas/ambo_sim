import ollama
from datetime import datetime, timezone
import json
import uuid
import argparse

def generate_encounter(patient_id, condition_id, practitioner_id, organization_id, llm_model='gemma:2b'):
    """Generate a FHIR Encounter resource for a given patient and condition.
    
    Args:
        patient_id (str): The ID of the patient this encounter is for
        condition_id (str): The ID of the related condition
        practitioner_id (str): The ID of the treating practitioner
        organization_id (str): The ID of the healthcare organization
        llm_model (str, optional): The Ollama model to use. Defaults to 'gemma:2b'
    
    Returns:
        dict: A FHIR Encounter resource, or None if generation fails
    """
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    encounter_id = str(uuid.uuid4())
    procedure_id = str(uuid.uuid4())

    prompt = f"""Generate a valid FHIR R4 Encounter resource that exactly follows this structure:
    {{
        "resourceType": "Encounter",
        "id": "{encounter_id}",
        "status": "in-progress",
        "class": {{
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "EMER",
            "display": "Emergency"
        }},
        "type": [{{
            "coding": [{{
                "system": "http://snomed.info/sct",
                "code": "<generate valid SNOMED CT code for emergency encounter>",
                "display": "<matching SNOMED display name>"
            }}],
            "text": "<encounter type description>"
        }}],
        "subject": {{
            "reference": "Patient/{patient_id}"
        }},
        "participant": [{{
            "type": [{{
                "coding": [{{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                    "code": "PPRF",
                    "display": "Primary Performer"
                }}]
            }}],
            "individual": {{
                "reference": "Practitioner/{practitioner_id}",
                "display": "<generate practitioner name>"
            }}
        }}],
        "period": {{
            "start": "{current_time}"
        }},
        "location": [{{
            "location": {{
                "reference": "Location/emergency-1",
                "display": "Emergency Department"
            }},
            "status": "active"
        }}],
        "serviceProvider": {{
            "reference": "Organization/{organization_id}",
            "display": "<generate organization name>"
        }},
        "reasonCode": [{{
            "coding": [{{
                "system": "http://snomed.info/sct",
                "code": "<generate valid SNOMED CT code for reason>",
                "display": "<matching SNOMED display name>"
            }}],
            "text": "<reason for visit description>"
        }}],
        "diagnosis": [{{
            "condition": {{
                "reference": "Condition/{condition_id}",
                "display": "<generate condition display name>"
            }},
            "rank": 1
        }}],
        "procedure": [{{
            "reference": "Procedure/{procedure_id}",
            "display": "<generate procedure name>",
            "performedDateTime": "{current_time}",
            "code": {{
                "coding": [{{
                    "system": "http://snomed.info/sct",
                    "code": "<generate valid SNOMED CT code for procedure>",
                    "display": "<matching SNOMED display name>"
                }}],
                "text": "<procedure description>"
            }}
        }}]
    }}

    Requirements:
    - Use real SNOMED CT codes and matching display names for emergency encounter types, reasons, and procedures
    - Make the encounter type, reason, and procedure descriptions realistic for an emergency presentation
    - Generate plausible names for the organization, practitioner, and procedure
    - Ensure all generated content is medically appropriate for an emergency setting
    - Return valid FHIR JSON only, no markdown or explanation

    Return the JSON only."""

    try:
        response = ollama.generate(model=llm_model, prompt=prompt)
        response_text = response['response']
        
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start >= 0 and end > start:
            try:
                encounter = json.loads(response_text[start:end])
                
                if encounter.get("resourceType") != "Encounter":
                    print("Generated resource is not an Encounter")
                    return None
                
                return encounter
                
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {str(e)}")
                return None
        else:
            print("No valid JSON found in response")
            return None
            
    except Exception as e:
        print(f"Error generating Encounter resource: {str(e)}")
        return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a FHIR Encounter resource')
    parser.add_argument('--patient-id', type=str, default='test-patient-123',
                       help='Patient ID to generate encounter for')
    parser.add_argument('--condition-id', type=str, default='test-condition-123',
                       help='Condition ID to link to encounter')
    parser.add_argument('--practitioner-id', type=str, default='test-practitioner-123',
                       help='Practitioner ID for the encounter')
    parser.add_argument('--organization-id', type=str, default='test-org-123',
                       help='Organization ID for the service provider')
    parser.add_argument('--llm-model', type=str, default='gemma:2b',
                       help='Ollama model to use (default: gemma:2b)')
    
    args = parser.parse_args()
    
    print(f"Generating encounter using {args.llm_model}")
    encounter = generate_encounter(
        args.patient_id,
        args.condition_id,
        args.practitioner_id,
        args.organization_id,
        llm_model=args.llm_model
    )
    
    if encounter:
        print(json.dumps(encounter, indent=2))
    else:
        print("Failed to generate encounter") 