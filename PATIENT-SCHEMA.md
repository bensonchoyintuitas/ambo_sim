# Patient Schema Documentation

This document describes the different schema versions of patient data used in the system.

## Common Fields Across Schemas
Both schema versions share these core fields:
```json
{
    "resourceType": "Patient",  // Always "Patient" per FHIR spec
    "id": "string",            // Unique identifier
    "name": [{
        "given": ["string"],   // Given/first names as array
        "family": "string"     // Family/last name
    }],
    "birthDate": "YYYY-MM-DD"  // Date of birth in ISO format
}
```

## Full FHIR Patient Schema (Version 2)
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

# Minimal Patient Schema (Version 1)
Example: `patient_pat-2731.json`

A simplified patient schema with basic demographic information:

```json
{
    "resourceType": "Patient",
    "id": "string",
    "name": [{
        "given": ["string"],
        "family": "string"
    }],
    "birthDate": "YYYY-MM-DD"
}



