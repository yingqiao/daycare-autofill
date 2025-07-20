# daycare_scraper_gemini.py
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
import json
import time
from pathlib import Path

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = genai.GenerativeModel("gemini-pro")

# Set debug mode
DEBUG = os.getenv("GEMINI_DEBUG", "0") == "1"
CACHE_DIR = Path("cache_json")
CACHE_DIR.mkdir(exist_ok=True)

def get_text_from_url(url):
    try:
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        return soup.get_text(separator=' ')
    except Exception as e:
        print(f"[Scraper error] {e}")
        return ""

def call_gemini_summary(text, retries=3):
    system_prompt = (
        "You are a helpful assistant extracting childcare program information from websites. "
        "Read the page content and summarize in structured JSON format using these fields:\n\n"
        "- AgesServed (e.g., infant, toddler, preschool)\n"
        "- Mandarin (Yes/No)\n"
        "- MealsProvided (Yes/No)\n"
        "- Curriculum (Montessori, play-based, etc.)\n"
        "- CulturalDiversity (High/Medium/Low)\n"
        "- StaffStability (Yes/No)\n\n"
        "Only return a JSON object."
    )

    full_prompt = f"Website content:\n\n{text[:16000]}\n\nPlease extract and return a JSON object."

    attempt = 0
    while attempt < retries:
        try:
            response = MODEL.generate_content([system_prompt, full_prompt])
            output = response.text
            json_start = output.find("{")
            json_end = output.rfind("}") + 1
            response_json = eval(output[json_start:json_end])
            return response_json
        except Exception as e:
            attempt += 1
            wait = 2 ** attempt
            print(f"[Gemini retry {attempt}] {e}, waiting {wait}s...")
            time.sleep(wait)

    return {
        "AgesServed": "",
        "Mandarin": "No",
        "MealsProvided": "No",
        "Curriculum": "",
        "CulturalDiversity": "Unknown",
        "StaffStability": "No"
    }

def get_cache_path(name):
    safe_name = "".join(c if c.isalnum() else "_" for c in name.lower())
    return CACHE_DIR / f"{safe_name}.json"

def scrape_daycare_info(url, name="daycare"):
    cache_path = get_cache_path(name)
    if cache_path.exists():
        with open(cache_path, "r") as f:
            return json.load(f)

    text = get_text_from_url(url)
    if not text:
        return {}

    summary = call_gemini_summary(text)

    with open(cache_path, "w") as f:
        json.dump(summary, f, indent=2)

    if DEBUG:
        print(f"[DEBUG] Gemini JSON for {name}:")
        print(json.dumps(summary, indent=2))

    return summary
