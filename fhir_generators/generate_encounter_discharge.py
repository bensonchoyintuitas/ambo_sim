from datetime import datetime, timezone
import json

def generate_encounter_discharge(encounter_id, start_time, end_time):
    """Generate a FHIR Encounter discharge resource.
    
    Args:
        encounter_id (str): The ID of the original encounter being discharged
        start_time (str): The start time of the encounter in ISO format
        end_time (str): The end time of the encounter in ISO format
    
    Returns:
        dict: A FHIR Encounter discharge resource
    """
    return {
        "resourceType": "Encounter",
        "id": encounter_id,
        "status": "completed",
        "hospitalization": {
            "dischargeDisposition": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/discharge-disposition",
                    "code": "home",
                    "display": "Discharged to home"
                }],
                "text": "Patient discharged to home after treatment"
            }
        },
        "period": {
            "start": start_time,
            "end": end_time
        }
    }

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate a FHIR Encounter discharge resource')
    parser.add_argument('--encounter-id', type=str, required=True,
                       help='ID of the encounter being discharged')
    parser.add_argument('--start-time', type=str,
                       help='Start time of the encounter (ISO format)')
    parser.add_argument('--end-time', type=str,
                       help='End time of the encounter (ISO format)')
    
    args = parser.parse_args()
    
    # Use current time for start/end if not provided
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    discharge = generate_encounter_discharge(
        args.encounter_id,
        args.start_time or current_time,
        args.end_time or current_time
    )
    
    print(json.dumps(discharge, indent=2))