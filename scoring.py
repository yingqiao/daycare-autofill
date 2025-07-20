# scoring.py
WEIGHTS = {
    "Mandarin": 2,
    "Meals": 1,
    "Curriculum": 1,
    "Staff Stability": 3,
    "Cultural Diversity": 1,
    "MSFT Discount": 2
}

def compute_score(row, weights):
    score = 0
    if row.get("Mandarin") == "Yes":
        score += weights["Mandarin"]
    if row.get("MealsProvided") == "Yes":
        score += weights["Meals"]
    if row.get("Curriculum"):
        score += weights["Curriculum"]
    if row.get("StaffStability") == "Yes":
        score += weights["Staff Stability"]
    if row.get("CulturalDiversity") == "High":
        score += weights["Cultural Diversity"]
    if row.get("MSFT_Discount") == "Yes":
        score += weights["MSFT Discount"]
    return score

