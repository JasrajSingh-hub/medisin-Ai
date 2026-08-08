def match_drugs(text: str) -> tuple[list[dict], list]:
    matched = []
    words = text.split()
    for w in words:
        w_clean = w.strip(",.()[]{}")
        if len(w_clean) > 3:
            matched.append({
                "matched_drug": w_clean,
                "input_token": w_clean,
                "confidence": 90.0,
                "status": "matched",
                "brand": ""
            })
    return matched, []
