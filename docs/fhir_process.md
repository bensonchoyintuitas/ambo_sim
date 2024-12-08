1. Patient at Home Appearing with a Condition (Before Calling Ambulance)
FHIR Resource:
Patient: Represents the patient's demographics and basic details.
Condition: Represents the patient’s health condition or symptoms at home.
Description: When the patient starts experiencing symptoms, a health system (like a home monitoring device or patient self-reporting app) could record data about their condition, symptoms, or vitals.
FHIR Exchange:
If integrated with a home monitoring device or personal health record (PHR) system, information about the patient’s condition can be shared with healthcare providers through an Observation or Condition resource.


*Donald Krump, a 74-year-old man, falls in his house and experiences some pain and swelling, particularly in his right knee. Recognizing that he might need medical attention, he (or someone with him) calls for an ambulance.*

```json
{
  "resourceType": "Patient",
  "id": "patient-krump-id",
  "name": [{
    "use": "official",
    "family": "Krump",
    "given": ["Donald"]
  }],
  "gender": "male",
  "birthDate": "1950-01-01"
}

```
```json
{
  "resourceType": "Condition",
  "id": "condition-fall-home",
  "subject": {
    "reference": "Patient/patient-krump-id"
  },
  "code": {
    "text": "Fall at home"
  },
  "onsetDateTime": "2024-10-26T12:00:00+10:00",
  "severity": {
    "text": "Moderate"
  }
}

```

2. Calling the Ambulance
FHIR Resource:
Encounter: Represents the request for service and response.
ServiceRequest: Represents the request for the ambulance to respond.
Description: When the emergency call is placed, an encounter is initiated, and the ServiceRequest resource would capture the request for emergency transport.
FHIR Exchange:
Encounter creation begins when emergency services are contacted.
ServiceRequest for the ambulance is sent to emergency medical services (EMS) systems.



*After the call is made, the emergency services are notified, and an ambulance is dispatched to Donald's home to take him to the hospital. The paramedics arrive shortly after and begin to assess his condition.*

```json
{
  "resourceType": "ServiceRequest",
  "id": "sr-ambulance-request",
  "subject": {
    "reference": "Patient/patient-krump-id"
  },
  "code": {
    "text": "Ambulance transport requested"
  },
  "intent": "order",
  "status": "active",
  "priority": "stat",
  "authoredOn": "2024-10-26T12:10:00+10:00"
}


```
```json
{
  "resourceType": "Encounter",
  "id": "encounter-ambulance-krump",
  "status": "in-progress",
  "class": {
    "code": "AMB",
    "display": "Ambulance"
  },
  "subject": {
    "reference": "Patient/patient-krump-id"
  },
  "period": {
    "start": "2024-10-26T12:12:00+10:00"
  }
}


```

3. Ambulance Arrival and Care in Transit
FHIR Resource:
Encounter: Continues from the call, representing the EMS involvement.
Observation: Vital signs and patient assessments conducted by paramedics (e.g., heart rate, blood pressure).
MedicationAdministration: If medications are administered in the ambulance (e.g., pain relief, oxygen).
Description: During transport, paramedics assess the patient and administer care. Vital signs and interventions are recorded.
FHIR Exchange:
Observation: Paramedics collect and store vital signs and medical observations.
MedicationAdministration: Record of any treatments provided by paramedics.
These FHIR resources are exchanged with hospital systems in real time or upon arrival.

*The paramedics assess Donald's vitals (like heart rate and blood pressure) and provide any necessary treatment, such as monitoring his condition while transporting him to the hospital. They determine that while Donald’s condition is stable, he needs to be seen at the hospital for further evaluation.*
```json
{
  "resourceType": "Observation",
  "id": "observation-vitals-ambulance",
  "status": "final",
  "subject": {
    "reference": "Patient/patient-krump-id"
  },
  "code": {
    "text": "Vital signs in ambulance"
  },
  "effectiveDateTime": "2024-10-26T12:20:00+10:00",
  "component": [
    {
      "code": { "text": "Heart rate" },
      "valueQuantity": { "value": 95, "unit": "beats/min" }
    },
    {
      "code": { "text": "Blood pressure" },
      "valueQuantity": { "value": "120/80", "unit": "mmHg" }
    }
  ]
}

```
```json
{
  "resourceType": "MedicationAdministration",
  "id": "med-admin-1",
  "status": "completed",
  "subject": {
    "reference": "Patient/123456"
  },
  "medicationCodeableConcept": {
    "text": "Pain relief medication"
  },
  "effectiveDateTime": "2024-10-26T10:20:00Z"
}

```

4. Ambulance Arrival at the Hospital (Ramping)
FHIR Resource:
Encounter: Updated to reflect the patient's arrival at the hospital.
Communication: A resource to notify the hospital of the patient’s condition prior to handover.
Description: When ramping occurs, the hospital is often updated about the patient's condition while still in the ambulance.
FHIR Exchange:
Encounter continues, with details about the ambulance’s arrival and any further updates to the patient's condition.
Communication resource may be used to provide the hospital with updates on the patient’s status.

*The ambulance arrives at the hospital, but due to the emergency department being busy, Donald may have to wait in the ambulance for a short time (this is called “ramping”). The hospital is informed about Donald’s condition, so they can prepare for his arrival.*

```json
{
  "resourceType": "Communication",
  "id": "communication-ambulance-hospital",
  "status": "completed",
  "subject": {
    "reference": "Patient/patient-krump-id"
  },
  "sent": "2024-10-26T12:35:00+10:00",
  "payload": [{
    "contentString": "Patient Donald Krump arriving with fall-related injury, stable vitals."
  }]
}


```

5. Transfer to Emergency Department (ED)
FHIR Resource:
Encounter: Continues and transitions to the hospital.
Condition: Updated with the patient’s presenting symptoms and diagnosis upon arrival.
CarePlan: May be created as the ED outlines the patient's treatment plan.
Description: When the patient is handed over, the ED staff continues the existing encounter or starts a new one, documenting the handover and initial assessments.
FHIR Exchange:
Handover information includes the patient's Condition, any administered treatments, and updates to the Encounter.

*Once space becomes available, Donald is transferred from the ambulance into the ED. The paramedics give a detailed report to the hospital staff about his condition and the care they provided during transport.*

```json
{
  "resourceType": "Encounter",
  "id": "encounter-ed-krump",
  "status": "in-progress",
  "class": {
    "code": "EMER",
    "display": "Emergency Department"
  },
  "subject": {
    "reference": "Patient/patient-krump-id"
  },
  "period": {
    "start": "2024-10-26T12:40:00+10:00"
  }
}


```
6. Triage
FHIR Resource:
Observation: For recording triage details such as vitals (heart rate, blood pressure).
Condition: Updated or created based on the triage nurse’s assessment.
Description: The triage nurse assesses the patient’s vitals and urgency, often updating or creating new Condition or Observation records.
FHIR Exchange:
Observation data is exchanged for vital signs, pain levels, etc.
Condition is created or updated based on the findings from the triage.

*After arriving in the ED, Donald is seen by a triage nurse, who assesses the urgency of his condition. The nurse checks his vital signs and evaluates the severity of his knee injury. Since his condition isn’t life-threatening but still requires attention, he is assigned a moderate priority.*

```json
{
  "resourceType": "Observation",
  "id": "observation-triage",
  "status": "final",
  "subject": {
    "reference": "Patient/patient-krump-id"
  },
  "code": {
    "text": "Triage assessment"
  },
  "effectiveDateTime": "2024-10-26T12:45:00+10:00",
  "valueString": "Moderate priority, pain level 5/10, swelling in right knee"
}


```
7. Waiting Room or Immediate Treatment
FHIR Resource:
Appointment: If the patient is scheduled for a specific time or bay in the ED for treatment.
Procedure: For any procedures or interventions performed in the ED (e.g., IV fluids).
DiagnosticReport: If any tests (e.g., blood work, X-rays) are ordered.
Description: If the patient is less urgent, they might wait, otherwise, they are moved directly to a treatment area. Here, any tests or procedures will be documented.
FHIR Exchange:
Procedure documents medical interventions.
DiagnosticReport documents test results.
Appointment is used for scheduled interventions.

*Depending on how busy the ED is, Donald may wait in the waiting area or be taken directly to a treatment room. In this case, there is some waiting time before a doctor is available to see him.*

```json
{
  "resourceType": "Appointment",
  "id": "appointment-ed-room-krump",
  "status": "booked",
  "description": "Waiting for ED treatment room",
  "start": "2024-10-26T12:50:00+10:00",
  "end": "2024-10-26T13:00:00+10:00",
  "participant": [{
    "actor": {
      "reference": "Patient/patient-krump-id"
    },
    "status": "accepted"
  }]
}



```
8. Doctor/Nurse Practitioner Assessment
FHIR Resource:
DiagnosticReport: Results from lab tests, imaging, etc.
Observation: Further assessments, such as clinical findings during the physical examination.
CarePlan: Updated or created based on the doctor’s findings and proposed treatments.
MedicationRequest: For prescribing medications.
Description: A more detailed assessment by doctors, potentially involving tests or treatment plans.
FHIR Exchange:
Exchange of DiagnosticReport with results.
CarePlan and MedicationRequest for ongoing care or treatment decisions.

*A doctor examines Donald and orders an X-ray of his right knee to check for fractures. The X-ray shows that there is no fracture, but there is moderate swelling that may require further treatment. The doctor provides the diagnosis and begins planning the next steps.*

```json
{
  "resourceType": "Procedure",
  "id": "procedure-xray",
  "status": "completed",
  "subject": {
    "reference": "Patient/patient-krump-id"
  },
  "performedDateTime": "2024-10-26T13:10:00+10:00",
  "code": {
    "text": "X-ray of right knee"
  }
}


```
```json
{
  "resourceType": "DiagnosticReport",
  "id": "diagnosticreport-xray-results",
  "status": "final",
  "subject": {
    "reference": "Patient/patient-krump-id"
  },
  "code": {
    "text": "X-ray report"
  },
  "result": [{
    "reference": "Observation/observation-xray-result"
  }],
  "conclusion": "No fracture, moderate swelling in the knee."
}


```
9. Ongoing Care or Discharge
FHIR Resource:
DischargeSummary: For patients being discharged, summarizing their ED visit and care instructions.
Encounter: Completed if the patient is discharged.
MedicationRequest or ReferralRequest: For follow-up care, if needed.
Condition: Updated if the patient is discharged with new diagnoses.
Description: The patient is either discharged with instructions or admitted for further care. A discharge summary is created if discharged.
FHIR Exchange:
DischargeSummary is generated and shared with other providers or the patient.
If admitted, the Encounter continues, and follow-up resources like ReferralRequest or CarePlan are shared.

*After the assessment, Donald is given a discharge plan. The doctor advises him to follow up with a physiotherapist in a week to help with the knee recovery. Donald is discharged from the ED with instructions for managing his pain and swelling at home.*

```json
{
  "resourceType": "CarePlan",
  "id": "careplan-discharge-krump",
  "status": "active",
  "subject": {
    "reference": "Patient/patient-krump-id"
  },
  "description": "Discharge plan with follow-up physiotherapy",
  "activity": [{
    "detail": {
      "status": "scheduled",
      "code": {
        "text": "Follow-up with physiotherapy in 1 week"
      }
    }
  }]
}

```
```json
{
  "resourceType": "Encounter",
  "id": "encounter-ed-krump",
  "status": "completed",
  "subject": {
    "reference": "Patient/patient-krump-id"
  },
  "period": {
    "start": "2024-10-26T12:40:00+10:00",
    "end": "2024-10-26T14:00:00+10:00"
  }
}

```

Summary of FHIR Data Flow:
Pre-Ambulance: Condition and Observation created in home-monitoring or self-reporting systems.
Ambulance: Encounter and Observation data are collected and shared with hospital ED.
Hospital Arrival to Triage: Handoff information, updated Encounter, triage Observations, and possibly CarePlans are exchanged.
Doctor/Nurse Assessment to Treatment: DiagnosticReport, Procedure, and updated Condition resources.
Discharge/Admission: DischargeSummary or transition of the Encounter into an inpatient admission.
Each step in this flow creates or exchanges FHIR resources that help ensure continuity of care across different healthcare settings.
