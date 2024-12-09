# Patient Schema Documentation

This document describes the different schema versions of patient data used in the system.

## Common Fields Across Schemas
Both schema versions share these core fields:
```json
{
    "resourceType": "Patient",  // Always "Patient" per FHIR spec
    "id": "string",            // Unique identifier (e.g., "pat-1234")
    "name": [{
        "given": ["string"],   // Given/first names as array (e.g., "John1234")
        "family": "string"     // Family/last name (e.g., "Smith1234")
    }],
    "birthDate": "YYYY-MM-DD", // Date of birth in ISO format
    "gender": "male|female",   // Patient's gender
    "identifier": [{           // Additional identifiers
        "system": "string",    // Identifier system (e.g., "ambosim/fallback")
        "value": "string"      // Identifier value (same as id)
    }]
}
```

## Full FHIR Patient Schema (Synthea) 
Example: `patient_6462bf29-68f3-36ca-2f78-ff1ce05d1484.json`

A comprehensive FHIR Patient resource with complete demographic information: 
```json
{
    "resourceType": "Patient",
    "id": "string",
    "address": [{
        "city": "string",
        "country": "string",
        "extension": [{
            "extension": [{
                "url": "latitude|longitude",
                "valueDecimal": "number"
            }],
            "url": "http://hl7.org/fhir/StructureDefinition/geolocation"
        }],
        "line": ["string"],
        "postalCode": "string",
        "state": "string"
    }],
    "birthDate": "YYYY-MM-DD",
    "communication": [{
        "language": {
            "coding": [{
                "code": "string",
                "display": "string",
                "system": "string"
            }],
            "text": "string"
        }
    }],
    "extension": [{
        "url": "string",
        "valueString|valueDecimal|valueAddress": "varies"
    }],
    "gender": "male|female",
    "identifier": [{
        "system": "string",
        "type": {
            "coding": [{
                "code": "string",
                "display": "string",
                "system": "string"
            }],
            "text": "string"
        },
        "value": "string"
    }],
    "maritalStatus": {
        "coding": [{
            "code": "string",
            "display": "string",
            "system": "string"
        }],
        "text": "string"
    },
    "multipleBirthBoolean": "boolean",
    "name": [{
        "family": "string",
        "given": ["string"],
        "prefix": ["string"],
        "use": "string"
    }],
    "telecom": [{
        "system": "string",
        "use": "string",
        "value": "string"
    }],
    "text": {
        "div": "string",
        "status": "string"
    }
}
```

## Minimal Patient Schema (Non-synthea / fallback)
Example: `patient_pat-2731.json`

A simplified patient schema with basic demographic information:

```json
{
    "resourceType": "Patient",  // Always "Patient" per FHIR spec
    "id": "string",            // Unique identifier with "pat-" prefix (e.g., "pat-9791")
    "name": [{
        "given": ["string"],   // Given name with ID suffix (e.g., "James9791")
        "family": "string"     // Family name with ID suffix (e.g., "Garcia9791")
    }],
    "birthDate": "YYYY-MM-DD", // Date of birth in ISO format
    "gender": "male|female",   // Patient's gender
    "identifier": [{
        "system": "ambosim/fallback", // Fixed identifier system for minimal schema
        "value": "string"             // Same as id field (e.g., "pat-9791")
    }]
}
```
