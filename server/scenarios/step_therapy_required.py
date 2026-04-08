MEDIUM_SCENARIO = {
    "goal": (
        "Obtain prior authorization for Adalimumab (Humira) 40mg injection (J0135/J3490) "
        "for patient Maria Santos with rheumatoid arthritis. "
        "Payer requires proof of step therapy failure: patient must have tried and failed "
        "methotrexate AND one other DMARD before biologic therapy is approved."
    ),
    "patient": {
        "name": "Maria Santos",
        "dob": "1968-07-22",
        "member_id": "AHMO-221847",
        "group_number": "GRP-88103",
        "payer": "Apex Health HMO",
        "payer_phone": "1-800-555-0448",
        "primary_care": "Dr. Benjamin Choi, MD",
        "referring_physician": "Dr. Sarah Nakamura, MD (Rheumatology)",
    },
    "procedure": {
        "code": "J0135",
        "name": "Adalimumab injection 20mg (Humira)",
        "place_of_service": "Office / Self-administered",
    },
    "diagnosis": {
        "code": "M06.09",
        "description": "Rheumatoid arthritis, unspecified site",
        "secondary": "M79.3 (Panniculitis)",
    },
    "step_limit": 14,
    "denial_sequence": [
        {
            "trigger": "initial_submit",
            "response": (
                "Prior authorization denied. Step therapy requirements not satisfied. "
                "Apex Health HMO requires documented failure of first-line DMARD therapy "
                "(methotrexate) before approving biologic agents. "
                "Please submit: medication_history documenting methotrexate trial."
            ),
            "reason_code": "CO-167",
        },
        {
            "trigger": "after_stage_0",
            "response": (
                "Methotrexate trial documented. However, step therapy policy requires "
                "documented failure of a SECOND conventional DMARD prior to biologic approval. "
                "Acceptable agents: sulfasalazine, hydroxychloroquine, or leflunomide. "
                "Please submit: visit_notes documenting second DMARD trial and failure."
            ),
            "reason_code": "CO-167",
        },
    ],
    "required_docs_by_stage": {
        "0": ["medication_history"],
        "1": ["visit_notes"],
    },
    "available_records": {
        "medication_history": {
            "summary": (
                "Methotrexate 15mg weekly (Mar 2022 - Feb 2023, 11 months). "
                "Discontinued: hepatotoxicity (ALT elevation 3x ULN). "
                "Sulfasalazine 1000mg BID (Mar 2023 - Nov 2023, 9 months). "
                "Discontinued: inadequate response (DAS28 score 5.8 at 6 months). "
                "Current: Prednisone 5mg daily for symptom management."
            ),
            "raw": [
                {
                    "drug": "Methotrexate",
                    "dose": "15mg weekly",
                    "start": "2022-03-01",
                    "end": "2023-02-28",
                    "duration_months": 11,
                    "discontinuation_reason": "Hepatotoxicity - ALT 3x ULN on LFT 2023-02-10",
                },
                {
                    "drug": "Sulfasalazine",
                    "dose": "1000mg BID",
                    "start": "2023-03-01",
                    "end": "2023-11-30",
                    "duration_months": 9,
                    "discontinuation_reason": "Inadequate response - DAS28 5.8 at month 6",
                },
                {
                    "drug": "Prednisone",
                    "dose": "5mg daily",
                    "start": "2023-12-01",
                    "end": "ongoing",
                    "reason": "Bridging therapy while biologic auth pursued",
                },
            ],
        },
        "visit_notes": {
            "summary": (
                "Rheumatology f/u 2024-02-14 (Dr. Nakamura): "
                "RA poorly controlled despite 2 DMARD trials. DAS28 = 6.1. "
                "Bilateral hand swelling, morning stiffness >1hr. "
                "Recommends escalation to biologic (adalimumab). "
                "Patient meets ACR criteria for biologic therapy."
            ),
            "raw": [
                {
                    "date": "2024-02-14",
                    "provider": "Dr. Sarah Nakamura, MD",
                    "note": (
                        "Maria presents with active RA. Failed MTX (hepatotoxicity) and "
                        "sulfasalazine (inadequate response per DAS28). DAS28 today: 6.1. "
                        "Initiating adalimumab 40mg SQ q2weeks. PA requested."
                    ),
                    "diagnosis_codes": ["M06.09"],
                    "das28_score": 6.1,
                },
            ],
        },
        "lab_results": {
            "summary": "RF positive 128 IU/mL, Anti-CCP positive 240 U/mL, CRP 18 mg/L, ESR 62 mm/hr.",
            "raw": [
                {"test": "RF", "value": "128 IU/mL", "flag": "HIGH"},
                {"test": "Anti-CCP", "value": "240 U/mL", "flag": "HIGH"},
                {"test": "CRP", "value": "18 mg/L", "flag": "HIGH"},
                {"test": "ESR", "value": "62 mm/hr", "flag": "HIGH"},
                {"test": "ALT", "value": "18 IU/L", "flag": "NORMAL", "note": "Normalized after MTX discontinuation"},
            ],
        },
        "imaging": {
            "summary": "Hand X-ray 2024-01-20: erosive changes at MCP joints bilaterally. Joint space narrowing.",
            "raw": [{"date": "2024-01-20", "type": "X-ray hands", "findings": "Erosive changes MCP bilateral"}],
        },
    },
    "payer_criteria": (
        "Apex Health HMO biologic step therapy policy (RA): "
        "TNF inhibitors (adalimumab, etanercept, infliximab) require: "
        "(1) Diagnosis of moderate-to-severe RA (DAS28 > 3.2), "
        "(2) Failure of methotrexate at adequate dose (>=15mg/week) for >=3 months OR intolerance, "
        "(3) Failure of ONE additional conventional DMARD (sulfasalazine, hydroxychloroquine, or leflunomide) "
        "    for >=3 months OR intolerance, "
        "(4) Documentation from rheumatologist within past 90 days."
    ),
    "correct_docs_required": ["medication_history", "visit_notes"],
    "optimal_step_count": 6,
}
