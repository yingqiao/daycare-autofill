# daycare_scraper_gemini.py
import requests
from google import genai
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import urlparse
import os, json, time, sys
from pathlib import Path

load_dotenv()
MODEL = "gemini-2.5-flash"

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
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
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
            response = client.models.generate_content(
                model=MODEL,
                contents=[system_prompt, full_prompt])
            output = response.text
            json_start = output.find("{")
            json_end = output.rfind("}") + 1
            json_text = output[json_start:json_end]
            response_json = json.loads(json_text)  # Use json.loads instead of eval
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

def get_text_cache_path(name):
    """Get path for caching raw website text for debugging"""
    safe_name = "".join(c if c.isalnum() else "_" for c in name.lower())
    return CACHE_DIR / f"{safe_name}_text.txt"

def scrape_daycare_info(url, name="daycare"):
    cache_path = get_cache_path(name)
    text_cache_path = get_text_cache_path(name)
    
    if cache_path.exists():
        with open(cache_path, "r") as f:
            return json.load(f)

    text = get_text_from_url(url)
    if not text:
        return {}

    # Cache the raw website text for debugging
    with open(text_cache_path, "w", encoding="utf-8") as f:
        f.write(f"URL: {url}\n")
        f.write("=" * 80 + "\n")
        f.write(text)

    summary = call_gemini_summary(text)

    with open(cache_path, "w") as f:
        json.dump(summary, f, indent=2)

    if DEBUG:
        print(f"[DEBUG] Gemini JSON for {name}:")
        print(json.dumps(summary, indent=2))

    return summary


def test_single_website(url, name=None):
    """
    Test function to scrape a single website and see detailed results.
    Stores both input (website text) and output (JSON) for debugging.
    
    Args:
        url (str): The website URL to test
        name (str, optional): Custom name for cache files. If None, uses domain name.
    
    Returns:
        dict: The extracted daycare information
    """
    print("🧪 Testing Single Website Scraper...")
    print("=" * 60)
    
    # Generate name from URL if not provided
    if not name:        
        domain = urlparse(url).netloc
        name = f"test_{domain.replace('.', '_')}"
    
    print(f"🌐 URL: {url}")
    print(f"📁 Cache name: {name}")
    
    # Get cache paths
    cache_path = get_cache_path(name)
    text_cache_path = get_text_cache_path(name)
    
    print(f"\n📄 Files that will be created:")
    print(f"  • Raw text: {text_cache_path}")
    print(f"  • JSON output: {cache_path}")
    
    # Force refresh by removing existing cache
    if cache_path.exists():
        cache_path.unlink()
        print(f"🗑️ Removed existing JSON cache")
    if text_cache_path.exists():
        text_cache_path.unlink()
        print(f"🗑️ Removed existing text cache")
    
    print(f"\n🔍 Fetching website content...")
    text = get_text_from_url(url)
    
    if not text:
        print("❌ Failed to fetch website content")
        return {}
    
    print(f"✅ Fetched {len(text)} characters of text")
    
    # Cache the raw website text for debugging
    print(f"💾 Saving raw text to: {text_cache_path}")
    with open(text_cache_path, "w", encoding="utf-8") as f:
        f.write(f"URL: {url}\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n")
        f.write(text)
    
    print(f"🤖 Calling Gemini API...")
    summary = call_gemini_summary(text)
    
    # Cache the JSON output
    print(f"💾 Saving JSON output to: {cache_path}")
    with open(cache_path, "w") as f:
        json.dump({
            "url": url,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "text_length": len(text),
            **summary
        }, f, indent=2)
    
    print(f"\n📊 Extracted Information:")
    print("=" * 40)
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    print(f"\n✅ Test completed successfully!")
    print(f"📁 Check cache_json/ folder for saved files")
    
    return summary


if __name__ == "__main__":
    # Interactive test when script is run directly    
    if len(sys.argv) > 1:
        # URL provided as command line argument
        test_url = sys.argv[1]
        test_name = sys.argv[2] if len(sys.argv) > 2 else None
        test_single_website(test_url, test_name)
    else:
        # Interactive mode
        print("🧪 Gemini Scraper Unit Test")
        print("=" * 40)
        print("Enter a daycare website URL to test:")
        print("Example: https://www.brightbeginningsdaycare.com")
        print()
        
        test_url = input("URL: ").strip()
        if test_url:
            test_name = input("Cache name (optional, press Enter for auto): ").strip()
            if not test_name:
                test_name = None
            
            result = test_single_website(test_url, test_name)
        else:
            print("❌ No URL provided")
