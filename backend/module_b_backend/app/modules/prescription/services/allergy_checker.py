def check_allergies(patient_id: str, prescribed_drugs: list[str]) -> dict:
    return {
        "patient_id": patient_id,
        "conflicts": [],
        "safe": True
    }
