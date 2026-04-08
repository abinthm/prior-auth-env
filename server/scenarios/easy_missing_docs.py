EASY_SCENARIO = {
    "goal": (
        "Obtain prior authorization for Lumbar Spine MRI (CPT 72148) for patient James Whitfield. "
        "Insurance requires clinical documentation before approving. "
        "Retrieve the required records from the patient chart and submit them."
    ),
    "patient": {
        "name": "James Whitfield",
        "dob": "1979-03-14",
        "member_id": "BCH-884729",
        "group_number": "GRP-44021",
        "payer": "BlueCrest HMO",
        "payer_phone": "1-800-555-0192",
        "primary_care": "Dr. Anita Rosen, MD",
        "referring_physician": "Dr. Anita Rosen, MD",
    },
    "procedure": {
        "code": "72148",
        "name": "MRI Lumbar Spine without contrast",
        "place_of_service": "Outpatient Radiology",
    },
    "diagnosis": {
        "code": "M54.5",
        "description": "Low back pain",
        "secondary": "M51.16 (Intervertebral disc degeneration, lumbar region)",
    },
    "step_limit": 8,
    "denial_sequence": [
        {
            "trigger": "initial_submit",
            "response": (
                "Additional clinical documentation required. "
                "Please submit office visit notes from the past 90 days documenting "
                "the onset, duration, and conservative treatment history for the reported condition. "
                "Missing documentation: clinical_notes."
            ),
            "reason_code": "CO-197",
        }
    ],
    "required_docs_by_stage": {
        "0": ["clinical_notes"],
    },
    "available_records": {
        "clinical_notes": {
            "summary": (
                "3 office visit notes from Dr. Rosen (Jan 12, Feb 3, Mar 8 2024). "
                "Chief complaint: chronic low back pain x 6 months, radiating to left leg. "
                "Conservative treatment: NSAIDs, physical therapy x 8 weeks. "
                "Inadequate response. Recommends MRI to rule out disc herniation."
            ),
            "raw": [
                {
                    "date": "2024-03-08",
                    "provider": "Dr. Anita Rosen, MD",
                    "note": "Patient returns with persistent LBP. 8 weeks PT completed, minimal improvement. "
                    "VAS pain score 7/10. Requesting MRI lumbar spine to rule out HNP.",
                    "diagnosis_codes": ["M54.5", "M51.16"],
                },
                {
                    "date": "2024-02-03",
                    "provider": "Dr. Anita Rosen, MD",
                    "note": "Follow-up LBP. PT ongoing. Patient reports limited improvement. "
                    "Continuing conservative management.",
                    "diagnosis_codes": ["M54.5"],
                },
                {
                    "date": "2024-01-12",
                    "provider": "Dr. Anita Rosen, MD",
                    "note": "New complaint: low back pain x 4 months. "
                    "Starting PT and NSAID therapy. Will reassess in 4 weeks.",
                    "diagnosis_codes": ["M54.5"],
                },
            ],
        },
        "imaging": {
            "summary": "X-ray lumbar spine 2024-01-15: mild degenerative changes L4-L5. No acute fracture.",
            "raw": [{"date": "2024-01-15", "type": "X-ray", "findings": "Mild DDD L4-L5"}],
        },
        "medication_history": {
            "summary": "Ibuprofen 800mg TID (Jan-Mar 2024). Cyclobenzaprine 10mg PRN.",
            "raw": [
                {"drug": "Ibuprofen", "dose": "800mg", "start": "2024-01-12", "end": "ongoing"},
                {"drug": "Cyclobenzaprine", "dose": "10mg PRN", "start": "2024-01-12"},
            ],
        },
    },
    "payer_criteria": (
        "BlueCrest HMO covers MRI lumbar spine (CPT 72148) when: "
        "(1) Low back pain present for >6 weeks with documented conservative treatment, "
        "(2) Clinical notes from treating physician within past 90 days, "
        "(3) Failure of conservative therapy (PT and/or medication). "
        "Required documentation: office visit notes documenting above criteria."
    ),
    "correct_docs_required": ["clinical_notes"],
    "optimal_step_count": 3,
}
