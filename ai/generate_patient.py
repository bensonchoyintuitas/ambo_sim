import ollama
import random
from datetime import datetime, timezone

# Get current time in UTC and format it
current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# Generate a random seed
seed = random.randint(1, 1000000)

prompt = f"""Using seed {seed} for randomization: Generate two valid FHIR R4 resources:
1. A Patient resource with:
   - random ID 
   - random First and Last name (Make a more obscure name, dont use typical names like John or Jane that are likely to duplicate)
   - random street 
   - city in Brisbane Australia 
   - random contacts
   - random dob (not just 1990-01-01)
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

# Print just the response content from the dictionary
print(response['response'])
