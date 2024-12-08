import ollama
from datetime import datetime, timezone
import json
import uuid
import argparse

def generate_encounter_ed_presentation(patient_id, condition_id, practitioner_id, organization_id, condition_description=None, llm_model='gemma:2b'):
    """Generate a FHIR Encounter resource for a given patient and condition.
    
    Args:
        patient_id (str): The ID of the patient this encounter is for
        condition_id (str): The ID of the related condition
        practitioner_id (str): The ID of the treating practitioner
        organization_id (str): The ID of the healthcare organization
        condition_description (str, optional): Description of patient's condition to inform diagnosis and procedures
        llm_model (str, optional): The Ollama model to use. Defaults to 'gemma:2b'
    
    Returns:
        dict: A FHIR Encounter resource, or None if generation fails
    """
    try:
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        encounter_id = str(uuid.uuid4())
        procedure_id = str(uuid.uuid4())

        condition_context = ""
        if condition_description:
            condition_context = f"""
            Patient Condition Context:
            {condition_description}
            
            Use this condition description to:
            1. Generate appropriate SNOMED codes for the diagnosis
            2. Select relevant procedures that would be performed for this condition
            3. Ensure the encounter type and reason codes align with the described condition
            """

        prompt = f"""Generate a valid FHIR R4 Encounter resource that exactly follows this structure:
        {condition_context}
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
                    "code": "<generate valid SNOMED CT code for emergency encounter matching the condition>",
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
                    "code": "<generate valid SNOMED CT code matching the condition>",
                    "display": "<matching SNOMED display name>"
                }}],
                "text": "<reason for visit description based on the condition>"
            }}],
            "diagnosis": [{{
                "condition": {{
                    "reference": "Condition/{condition_id}",
                    "display": "<generate condition display name matching the description>"
                }},
                "rank": 1
            }}],
            "procedure": [{{
                "reference": "Procedure/{procedure_id}",
                "display": "<generate procedure name appropriate for the condition>",
                "performedDateTime": "{current_time}",
                "code": {{
                    "coding": [{{
                        "system": "http://snomed.info/sct",
                        "code": "<generate valid SNOMED CT code for procedure appropriate for the condition>",
                        "display": "<matching SNOMED display name>"
                    }}],
                    "text": "<procedure description explaining treatment for the condition>"
                }}
            }}]
        }}

        Requirements:
        - Use real SNOMED CT codes and matching display names that are appropriate for the described condition
        - Make the encounter type, reason, and procedure descriptions realistic and relevant to the condition
        - Generate plausible names for the organization and practitioner
        - Ensure all generated content is medically appropriate for an emergency setting
        - Return valid FHIR JSON only, no markdown or explanation

        Return the JSON only."""

        print(f"Generating encounter using model: {llm_model}")
        print(f"Patient condition context: {condition_description}")
        
        response = ollama.generate(model=llm_model, prompt=prompt)
        response_text = response['response']
        
        print(f"Raw LLM response: {response_text}")
        
        # Clean up the response text
        response_text = response_text.replace('```json', '').replace('```', '')
        
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start >= 0 and end > start:
            try:
                encounter = json.loads(response_text[start:end])
                print(f"Successfully parsed encounter JSON: {json.dumps(encounter, indent=2)}")
                
                if encounter.get("resourceType") != "Encounter":
                    print("Generated resource is not an Encounter")
                    return None
                
                # Validate required fields
                required_fields = [
                    "resourceType", "id", "status", "class", "type",
                    "subject", "participant", "period", "serviceProvider"
                ]
                
                missing_fields = [field for field in required_fields if field not in encounter]
                if missing_fields:
                    print(f"Missing required fields: {missing_fields}")
                    return None
                
                print(f"Successfully generated encounter with ID: {encounter['id']}")
                return encounter
                
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {str(e)}")
                print(f"Invalid JSON content: {response_text[start:end]}")
                return None
        else:
            print("No valid JSON found in response")
            print(f"Response content: {response_text}")
            return None
            
    except Exception as e:
        print(f"Error generating Encounter resource: {str(e)}")
        print(f"Full traceback:", exc_info=True)
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
    parser.add_argument('--condition-description', type=str,
                       help='Description of patient condition to inform diagnosis and procedures')
    parser.add_argument('--llm-model', type=str, default='gemma:2b',
                       help='Ollama model to use (default: gemma:2b)')
    
    args = parser.parse_args()
    
    print(f"Generating encounter using {args.llm_model}")
    encounter = generate_encounter_ed_presentation(
        args.patient_id,
        args.condition_id,
        args.practitioner_id,
        args.organization_id,
        condition_description=args.condition_description,
        llm_model=args.llm_model
    )
    
    if encounter:
        print(json.dumps(encounter, indent=2))
    else:
        print("Failed to generate encounter") 