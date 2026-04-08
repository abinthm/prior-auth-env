HARD_SCENARIO = {
    "goal": (
        "Obtain prior authorization for Lumbar Spinal Fusion L4-L5 (CPT 22612) "
        "for patient Robert Okonkwo. The initial submission will be denied as 'not medically necessary.' "
        "You must: (1) gather all required clinical documentation, (2) submit a formal appeal, "
        "(3) request and complete a peer-to-peer review with the payer's medical director, and "
        "(4) if still denied, escalate to an Independent Review Organization (IRO). "
        "Each stage requires assembling specific evidence addressing the payer's stated criteria."
    ),
    "patient": {
        "name": "Robert Okonkwo",
        "dob": "1961-11-05",
        "member_id": "UNH-779341",
        "group_number": "GRP-55089",
        "payer": "United National Health PPO",
        "payer_phone": "1-800-555-0271",
        "primary_care": "Dr. Linda Park, MD",
        "referring_physician": "Dr. James Ortega, MD (Orthopedic Surgery)",
    },
    "procedure": {
        "code": "22612",
        "name": "Lumbar arthrodesis, posterior technique, single level L4-L5",
        "place_of_service": "Inpatient Hospital",
    },
    "diagnosis": {
        "code": "M43.16",
        "description": "Spondylolisthesis, lumbar region",
        "secondary": "M51.16 (IVD degeneration lumbar), M54.4 (Lumbago with sciatica)",
    },
    "step_limit": 26,
    "denial_sequence": [
        {
            "trigger": "initial_submit",
            "response": (
                "Prior authorization DENIED. Reason: Medical necessity not established. "
                "United National Health criteria for lumbar spinal fusion (22612) require: "
                "(1) Imaging confirming structural pathology (MRI within 12 months), "
                "(2) Documented failure of 6+ months conservative treatment "
                "    (PT, epidural steroid injections, and oral medications), "
                "(3) Functional assessment documenting disability severity (ODI score >= 40%), "
                "(4) Neurosurgeon or orthopedic surgeon attestation. "
                "Missing: imaging documentation, functional assessment, conservative treatment history. "
                "Denial code: CO-50. You may appeal this decision within 60 days."
            ),
            "reason_code": "CO-50",
        },
        {
            "trigger": "after_appeal",
            "response": (
                "Appeal reviewed. Determination upheld — DENIED. "
                "Clinical documentation partially satisfies criteria. "
                "Peer-to-peer review with our medical director is required before further reconsideration. "
                "Please contact 1-800-555-0271 ext. 4 to schedule the peer-to-peer call. "
                "Request reference number: APP-2024-7739."
            ),
            "reason_code": "CO-50",
        },
        {
            "trigger": "after_p2p",
            "response": (
                "Peer-to-peer review completed. Medical director has reviewed the case. "
                "Determination: UPHELD — DENIED. "
                "Rationale: While documentation is comprehensive, our internal policy requires "
                "independent validation for high-cost surgical procedures. "
                "You may request an Independent Review Organization (IRO) / External Review. "
                "IRO escalation is your right under state law. Reference: IRO-2024-9921."
            ),
            "reason_code": "CO-50",
        },
    ],
    "required_docs_by_stage": {
        "0": ["imaging", "functional_assessment", "clinical_notes"],
        "1": [],
        "2": [],
    },
    "available_records": {
        "imaging": {
            "summary": (
                "MRI Lumbar Spine without contrast, 2024-01-08 (St. Mary's Radiology): "
                "Grade II spondylolisthesis L4 on L5. Moderate-severe central canal stenosis L4-L5. "
                "Neural foraminal narrowing bilateral L4-L5, worse on left. "
                "L4-L5 disc: moderate degeneration with annular fissure. "
                "Clinical correlation recommended."
            ),
            "raw": {
                "date": "2024-01-08",
                "modality": "MRI Lumbar without contrast",
                "findings": (
                    "Grade II spondylolisthesis L4/L5 (6mm anterior translation). "
                    "Moderate-severe central canal stenosis at L4-L5 level. "
                    "Left-sided neural foraminal stenosis L4-L5 (severe). "
                    "Multilevel degenerative disc disease most pronounced L4-L5."
                ),
                "impression": "Grade II L4/L5 spondylolisthesis with significant stenosis. Surgical consultation advised.",
            },
        },
        "functional_assessment": {
            "summary": (
                "Oswestry Disability Index (ODI) 2024-02-20: Score 62% (Severe disability). "
                "Patient unable to perform: prolonged sitting >20min, standing >10min, "
                "lifting >5lbs, or walking >1 block without significant pain. "
                "VAS pain score: 8/10 at rest, 10/10 with activity. "
                "Unable to work since November 2023."
            ),
            "raw": {
                "instrument": "Oswestry Disability Index",
                "date": "2024-02-20",
                "score_pct": 62,
                "interpretation": "Severe disability",
                "vas_rest": 8,
                "vas_activity": 10,
                "work_status": "Disabled since 2023-11-01",
            },
        },
        "clinical_notes": {
            "summary": (
                "Orthopedic surgery consultation 2024-02-28 (Dr. Ortega): "
                "Patient with 18 months LBP and left leg radiculopathy. "
                "Conservative treatment: PT x 6 months (completed July 2023), "
                "ESI x 3 (April, June, August 2023 — transient relief <4 weeks each), "
                "Gabapentin 600mg TID, Meloxicam 15mg daily. "
                "All conservative measures failed. ODI 62%. "
                "MRI confirms Grade II spondylolisthesis. Surgical intervention indicated. "
                "Recommending L4-L5 posterior lumbar interbody fusion (PLIF)."
            ),
            "raw": [
                {
                    "date": "2024-02-28",
                    "provider": "Dr. James Ortega, MD (Orthopedics)",
                    "conservative_treatment": {
                        "physical_therapy": {"duration_weeks": 24, "completed": True, "response": "Minimal"},
                        "epidural_injections": {
                            "count": 3,
                            "dates": ["2023-04", "2023-06", "2023-08"],
                            "response": "Transient relief <4 weeks each",
                        },
                        "medications": ["Gabapentin 600mg TID", "Meloxicam 15mg daily"],
                    },
                    "surgical_recommendation": "L4-L5 PLIF (CPT 22612). Conservative treatment exhausted.",
                    "diagnosis_codes": ["M43.16", "M51.16", "M54.4"],
                },
            ],
        },
        "lab_results": {
            "summary": "CBC, CMP within normal limits. No contraindications to surgery identified.",
            "raw": {"date": "2024-02-15", "findings": "All within normal limits."},
        },
        "medication_history": {
            "summary": "Gabapentin 600mg TID (Aug 2023-present). Meloxicam 15mg daily (Jun 2023-present). Cyclobenzaprine 10mg PRN.",
            "raw": [],
        },
    },
    "payer_criteria": (
        "United National Health criteria for lumbar fusion (CPT 22612): "
        "ALL of the following must be documented: "
        "(1) Structural pathology confirmed on MRI within 12 months (disc herniation, spondylolisthesis, stenosis), "
        "(2) Failure of conservative care for minimum 6 months including: "
        "    physical therapy (>=12 sessions), medication management, AND "
        "    epidural steroid injections (if not contraindicated), "
        "(3) Functional disability documented by validated tool (ODI, SF-36, or PROMIS) "
        "    showing moderate-severe impairment (ODI >= 40%), "
        "(4) Attestation from fellowship-trained spine surgeon. "
        "Peer-to-peer review available upon request after formal appeal submission. "
        "External IRO review available as final step under state law."
    ),
    "correct_docs_required": ["imaging", "functional_assessment", "clinical_notes"],
    "optimal_step_count": 13,
}
