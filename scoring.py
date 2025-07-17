# scoring.py
WEIGHTS = {
    "Mandarin": 2,
    "Meals": 1,
    "Curriculum": 1,
    "Staff Stability": 2,
    "Cultural Diversity": 1,
    "MSFT Discount": 3
}

def compute_score(row, weights):
    score = 0
    if row.get("Mandarin") == "Yes":
        score += weights["Mandarin"]
    if row.get("Meals Provided") == "Yes":
        score += weights["Meals"]
    if row.get("Curriculum"):
        score += weights["Curriculum"]
    if row.get("Staff Stability") == "Yes":
        score += weights["Staff Stability"]
    if row.get("Cultural Diversity") == "High":
        score += weights["Cultural Diversity"]
    if row.get("MSFT Discount") == "Yes":
        score += weights["MSFT Discount"]
    return score

