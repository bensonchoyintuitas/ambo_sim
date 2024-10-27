import ollama
from datetime import datetime, timezone

# Get current time in UTC and format it
current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

prompt = f"""Generate two valid FHIR R4 resources:
1. A Patient resource with:
   - ID, Full name, address in Brisbane, contacts, and DOB
   - Make a more obscure name, dont use typical names like John or Jane that are likely to duplicate
2. A Condition resource that:
   - References the patient
   - onsetDateTime is {current_time}
   - Represents a condition that is realistic for an emergency presentation reason
   - Includes appropriate clinical status, verification status, and severity
   - Uses proper SNOMED CT codes
   - Includes onset date/time and when recorded
   - Has clinical notes in the note field

Return valid FHIR JSON only."""

response = ollama.generate(model='gemma:2b', prompt=prompt)

print(response)
