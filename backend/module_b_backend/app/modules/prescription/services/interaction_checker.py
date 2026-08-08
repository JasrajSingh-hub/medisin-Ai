def check_interactions(patient_id: str, prescribed_drugs: list[str]) -> dict:
    return {
        "patient_id": patient_id,
        "interactions": [],
        "safe": True
    }
