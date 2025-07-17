# daycare_scraper.py
import requests
from bs4 import BeautifulSoup

# Define keyword banks
KEYWORDS = {
    "Ages Served": ["infant", "toddler", "preschool", "pre-k", "school age"],
    "Mandarin": ["mandarin", "chinese", "bilingual"],
    "Meals Provided": ["meals", "lunch", "snack included"],
    "Curriculum": ["montessori", "play-based", "reggio", "emergent"],
    "Cultural Diversity": ["diverse", "inclusive", "multicultural", "equity"],
    "Staff Stability": ["same teacher", "low turnover", "consistent caregiver", "long term"]
}

def scrape_keywords(url, keywords=KEYWORDS):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(separator=' ').lower()

        found = {}
        for label, keys in keywords.items():
            found[label] = "Yes" if any(k in text for k in keys) else "No"

        return found
    except Exception as e:
        print(f"[ERROR scraping {url}] {e}")
        return {label: "No" for label in keywords}
