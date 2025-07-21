# daycare_scraper_gemini.py
import requests
from google import genai
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import urlparse, urljoin
import os, json, time, sys
from pathlib import Path

load_dotenv()
MODEL = "gemini-2.5-flash"

# Set debug mode
DEBUG = os.getenv("GEMINI_DEBUG", "0") == "1"
CACHE_DIR = Path("cache_json")
CACHE_TEXT_DIR = Path("cache_text")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TEXT_DIR.mkdir(exist_ok=True)

def get_text_from_url(url):
    try:
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        return soup.get_text(separator=' ')
    except Exception as e:
        print(f"[Scraper error] {e}")
        return ""

def needs_javascript(text):
    """Check if the scraped content indicates JavaScript is needed"""
    if not text or len(text.strip()) < 500:
        return True
    
    js_indicators = [
        "enable javascript",
        "javascript is required", 
        "please enable javascript",
        "javascript is disabled",
        "noscript",
        "loading...",
        "please wait",
        "redirecting",
    ]
    
    text_lower = text.lower()
    return any(indicator in text_lower for indicator in js_indicators)

def get_text_from_url_selenium(url):
    """Get text from URL using Selenium for JavaScript-heavy sites"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        
        options = Options()
        options.add_argument('--headless')  # Run in background
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # Use webdriver-manager to automatically handle ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        try:
            driver.get(url)
            # Wait for body to load
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Additional wait for dynamic content
            time.sleep(3)
            
            # Get text content
            text = driver.find_element(By.TAG_NAME, "body").text
            return text
            
        finally:
            driver.quit()
            
    except Exception as e:
        print(f"[Selenium error] {e}")
        return ""

def get_text_from_url_smart(url):
    """Smart hybrid scraper that tries static first, falls back to Selenium if needed"""
    start_time = time.time()
    
    # Try static scraping first
    print(f"🔍 Trying static scraping for {url}")
    static_text = get_text_from_url(url)
    
    if static_text and not needs_javascript(static_text):
        elapsed = time.time() - start_time
        print(f"✅ Static scraping successful ({elapsed:.1f}s, {len(static_text)} chars)")
        return static_text, "static"
    
    # Fallback to Selenium
    print(f"🔄 Static content insufficient, trying JavaScript rendering...")
    js_text = get_text_from_url_selenium(url)
    
    elapsed = time.time() - start_time
    method = "selenium"
    
    if js_text:
        print(f"✅ JavaScript scraping successful ({elapsed:.1f}s, {len(js_text)} chars)")
        return js_text, method
    else:
        print(f"❌ Both methods failed ({elapsed:.1f}s)")
        return static_text or "", "failed"

def discover_all_internal_links(base_url):
    """Get ALL internal links from a website homepage"""
    base_domain = urlparse(base_url).netloc
    internal_links = set()
    
    try:
        print(f"🔍 Discovering links from {base_url}")
        response = requests.get(base_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if not href:
                continue
            
            # Filter out mailto and other communication protocol links
            if href.lower().startswith(('mailto:', 'tel:', 'sms:', 'skype:', 'whatsapp:', 'facetime:')):
                continue  # Skip communication links to avoid triggering services and delays
                
            # Convert relative URLs to absolute
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            # Only internal links (same domain)
            if parsed.netloc == base_domain or not parsed.netloc:
                # Clean URL (remove fragments, normalize)
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    clean_url += f"?{parsed.query}"
                
                # Remove trailing slash for consistency
                clean_url = clean_url.rstrip('/')
                
                # Skip empty paths and duplicates
                if clean_url != base_url.rstrip('/') and len(clean_url) > len(base_url):
                    internal_links.add(clean_url)
                    
    except Exception as e:
        print(f"❌ Link discovery error: {e}")
    
    return list(internal_links)

def filter_non_content_pages(urls):
    """Exclude pages that are unlikely to contain program information"""
    
    # Pages to EXCLUDE (contact, admin, etc.)
    exclude_patterns = [
        # Contact & Location
        'contact', 'location', 'directions', 'map', 'address', 'phone',
        
        # Administrative & Account
        'login', 'register', 'signup', 'account', 'portal', 'admin', 'dashboard',
        'payment', 'billing', 'invoice', 'checkout', 'cart', 'shop', 'store',
        
        # Legal & Policies
        'privacy', 'terms', 'legal', 'policy', 'disclaimer', 'copyright', 'gdpr',
        
        # Technical & System
        'sitemap', 'search', 'rss', 'feed', 'api', '404', 'error', 'maintenance',
        
        # Employment (usually not program info)
        'jobs', 'careers', 'employment', 'hiring', 'apply', 'work-with-us',
        
        # News/Blog/Events (usually not core program details)
        'news', 'blog', 'events', 'calendar', 'newsletter', 'articles', 'posts',
        
        # Social & External
        'facebook', 'instagram', 'twitter', 'linkedin', 'youtube', 'social',
        
        # File downloads
        '.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.mp4'
    ]
    
    # Pages to PRIORITIZE (high value content)
    priority_patterns = [
        'program', 'curriculum', 'philosophy', 'approach', 'method',
        'about', 'overview', 'services', 'care',
        'ages', 'infant', 'toddler', 'preschool', 'pre-k', 'kindergarten',
        'schedule', 'hours', 'day', 'routine', 'activities', 'learning',
        'meals', 'nutrition', 'food', 'lunch', 'snack', 'menu',
        'staff', 'teachers', 'caregivers', 'team', 'educators',
        'enrollment', 'admission', 'tuition', 'rates', 'fees', 'cost',
        'tour', 'visit', 'information', 'details'
    ]
    
    priority_urls = []
    regular_urls = []
    
    for url in urls:
        url_lower = url.lower()
        
        # Skip if matches exclude patterns
        if any(pattern in url_lower for pattern in exclude_patterns):
            continue
        
        # Categorize by priority
        if any(pattern in url_lower for pattern in priority_patterns):
            priority_urls.append(url)
        else:
            regular_urls.append(url)
    
    # Return priority URLs first, then regular ones
    return priority_urls + regular_urls

def scrape_comprehensive_daycare_info(base_url, name="daycare", max_pages=10):
    """Comprehensive multi-page daycare scraper"""
    print(f"🌐 Starting comprehensive scraping for {base_url}")
    start_time = time.time()
    
    # Step 1: Always include homepage
    homepage_text, homepage_method = get_text_from_url_smart(base_url)
    all_content = [{
        'url': base_url,
        'text': homepage_text,
        'method': homepage_method,
        'length': len(homepage_text) if homepage_text else 0,
        'type': 'homepage'
    }]
    
    # Step 2: Discover all internal links
    print("🔍 Discovering internal links...")
    all_links = discover_all_internal_links(base_url)
    print(f"📄 Found {len(all_links)} total internal links")
    
    # Step 3: Filter out non-content pages
    print("🔽 Filtering out non-content pages...")
    content_links = filter_non_content_pages(all_links)
    print(f"📋 Filtered to {len(content_links)} relevant pages")
    
    # Step 4: Limit to prevent excessive scraping
    if len(content_links) > max_pages - 1:  # -1 because we already have homepage
        content_links = content_links[:max_pages - 1]
        print(f"⚡ Limited to {max_pages - 1} additional pages for performance")
    
    # Step 5: Scrape all content pages
    scraped_urls = [base_url]
    
    for i, url in enumerate(content_links, 1):
        print(f"📖 Scraping page {i}/{len(content_links)}: {url}")
        try:
            text, method = get_text_from_url_smart(url)
            if text and len(text.strip()) > 200:  # Only meaningful content
                all_content.append({
                    'url': url,
                    'text': text,
                    'method': method,
                    'length': len(text),
                    'type': 'subpage'
                })
                scraped_urls.append(url)
                print(f"  ✅ Success ({len(text)} chars, {method})")
                        
            else:
                print(f"  ⚠️ Skipped (insufficient content: {len(text) if text else 0} chars)")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Small delay to be respectful
        time.sleep(0.5)
    
    # Step 6: Combine all content intelligently
    combined_text = f"=== HOMEPAGE CONTENT ===\n{homepage_text}\n\n"
    
    for content in all_content[1:]:  # Skip homepage as it's already added
        combined_text += f"=== CONTENT FROM {content['url']} ===\n"
        combined_text += f"{content['text']}\n\n"
    
    elapsed = time.time() - start_time
    print(f"✅ Comprehensive scraping completed in {elapsed:.1f}s")
    print(f"📊 Total: {len(scraped_urls)} pages, {len(combined_text)} characters")
    
    return combined_text, scraped_urls, all_content

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

def call_gemini_summary_multipage(combined_text, scraped_urls, retries=3):
    """Enhanced Gemini call for multi-page content"""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    system_prompt = (
        "You are analyzing comprehensive content from multiple pages of a daycare website. "
        "The content below comes from several pages including homepage, program details, curriculum info, etc. "
        "Extract and summarize in structured JSON format:\n\n"
        "- AgesServed (e.g., '6 weeks - 5 years', 'infant, toddler, preschool')\n"
        "- Mandarin (Yes/No - look for Chinese, Mandarin, bilingual, language immersion, dual language)\n"
        "- MealsProvided (Yes/No - look for meals, lunch, snacks, nutrition, food program, catering)\n"
        "- Curriculum (e.g., 'Montessori', 'play-based', 'emergent', 'academic', 'Reggio Emilia')\n"
        "- CulturalDiversity (High/Medium/Low - look for multicultural, diverse, inclusive, international)\n"
        "- StaffStability (Yes/No - look for low turnover, same teachers, consistent caregivers, experienced staff)\n\n"
        "Be thorough since this is comprehensive website content. Only return a JSON object."
    )

    # Use more content for multi-page analysis (up to 24k chars)
    url_list = ', '.join(scraped_urls[:5])  # Show first 5 URLs
    if len(scraped_urls) > 5:
        url_list += f" and {len(scraped_urls) - 5} more pages"
    
    full_prompt = f"Comprehensive content from {len(scraped_urls)} pages of daycare website:\nPages analyzed: {url_list}\n\n{combined_text[:24000]}\n\nExtract detailed daycare information as JSON:"

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
            response_json = json.loads(json_text)
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
    return CACHE_TEXT_DIR / f"{safe_name}_text.txt"

def scrape_multiple_urls(url_list, name="daycare"):
    """
    Scrape multiple URLs for a single provider and combine the content.
    Useful for providers with main website + social media pages.
    
    Args:
        url_list (list): List of URLs to scrape
        name (str): Provider name for caching and identification
    
    Returns:
        dict: Combined scraped information from all URLs
    """
    print(f"🌐 Multi-URL scraping for {name}: {len(url_list)} URLs")
    
    combined_content = ""
    scraped_urls = []
    scraping_methods = []
    
    for i, url in enumerate(url_list, 1):
        print(f"  📖 Scraping URL {i}/{len(url_list)}: {url}")
        try:
            # Use smart hybrid scraping for each URL
            text, method = get_text_from_url_smart(url)
            
            if text and len(text.strip()) > 200:  # Only meaningful content
                combined_content += f"\n=== CONTENT FROM {url} ===\n"
                combined_content += f"{text}\n"
                scraped_urls.append(url)
                scraping_methods.append(method)
                print(f"    ✅ Success ({len(text)} chars, {method})")
                        
            else:
                print(f"    ⚠️ Skipped (insufficient content: {len(text) if text else 0} chars)")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
        
        # Small delay between URLs
        time.sleep(0.5)
    
    if not combined_content:
        print(f"  ❌ No content extracted from any URL")
        return {}
    
    print(f"  ✅ Combined content from {len(scraped_urls)} URLs ({len(combined_content)} total chars)")
    
    # Cache the combined content (always saved, not just in DEBUG)
    text_cache_path = get_text_cache_path(name)
    with open(text_cache_path, "w", encoding="utf-8") as f:
        f.write(f"Multi-URL scraping for: {name}\n")
        f.write(f"URLs processed: {len(url_list)}\n") 
        f.write(f"Successful URLs: {len(scraped_urls)}\n")
        f.write(f"Methods used: {', '.join(set(scraping_methods))}\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("Scraped URLs:\n")
        for j, scraped_url in enumerate(scraped_urls, 1):
            f.write(f"  {j}. {scraped_url}\n")
        f.write("=" * 80 + "\n")
        f.write(combined_content)
    
    # DEBUG: Save combined content before Gemini analysis
    if DEBUG:
        debug_cache_path = CACHE_TEXT_DIR / f"debug_{name.replace(' ', '_')}_{int(time.time())}.txt"
        try:
            with open(debug_cache_path, "w", encoding="utf-8") as f:
                f.write(f"DEBUG - Combined content before Gemini analysis\n")
                f.write(f"Provider: {name}\n")
                f.write(f"Scraping type: Multi-URL\n")
                f.write(f"Total URLs provided: {len(url_list)}\n")
                f.write(f"Successful URLs: {len(scraped_urls)}\n")
                f.write(f"Failed URLs: {len(url_list) - len(scraped_urls)}\n")
                f.write(f"Methods used: {', '.join(set(scraping_methods))}\n")
                f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Combined content length: {len(combined_content)}\n")
                f.write("All provided URLs:\n")
                for j, provided_url in enumerate(url_list, 1):
                    status = "✅ Success" if provided_url in scraped_urls else "❌ Failed"
                    f.write(f"  {j}. {provided_url} - {status}\n")
                f.write("=" * 80 + "\n")
                f.write(combined_content)
            print(f"[DEBUG] Combined content saved to: {debug_cache_path}")
        except Exception as e:
            print(f"[DEBUG] Failed to save combined content: {e}")
    
    # Enhanced Gemini analysis for multi-URL content
    print(f"🤖 Analyzing combined content with Gemini...")
    summary = call_gemini_summary_multiurl(combined_content, scraped_urls, url_list)
    
    # Enhanced caching with multi-URL metadata
    cache_path = get_cache_path(name)
    enhanced_summary = {
        "scraping_method": "multi_url",
        "total_urls_provided": len(url_list),
        "successful_urls": len(scraped_urls),
        "scraped_urls": scraped_urls,
        "failed_urls": [url for url in url_list if url not in scraped_urls],
        "scraping_methods": scraping_methods,
        "total_text_length": len(combined_content),
        **summary
    }
    
    with open(cache_path, "w") as f:
        json.dump(enhanced_summary, f, indent=2)
    
    return summary


def call_gemini_summary_multiurl(combined_text, scraped_urls, all_urls, retries=3):
    """Enhanced Gemini call specifically for multi-URL content"""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    system_prompt = (
        "You are analyzing comprehensive content from multiple sources for a single daycare provider. "
        "The content below comes from their main website, social media pages, and other online sources. "
        "Extract and synthesize information from ALL sources to provide the most complete picture. "
        "Extract detailed information in structured JSON format:\n\n"
        "- AgesServed (e.g., '6 weeks - 5 years', 'infant, toddler, preschool')\n"
        "- Mandarin (Yes/No - look for Chinese, Mandarin, bilingual, language immersion, dual language)\n"
        "- MealsProvided (Yes/No - look for meals, lunch, snacks, nutrition, food program, catering)\n"
        "- Curriculum (e.g., 'Montessori', 'play-based', 'emergent', 'academic', 'Reggio Emilia')\n"
        "- CulturalDiversity (High/Medium/Low - look for multicultural, diverse, inclusive, international)\n"
        "- StaffStability (Yes/No - look for low turnover, same teachers, consistent caregivers, experienced staff)\n\n"
        "Synthesize information from all sources. If different sources provide different details, use the most comprehensive or recent information. Only return a JSON object."
    )

    # Create URL summary for context
    url_summary = f"Combined content from {len(scraped_urls)} sources out of {len(all_urls)} provided"
    if len(scraped_urls) < len(all_urls):
        url_summary += f" (some URLs failed to load)"
    
    full_prompt = f"Multi-source analysis for daycare provider:\n{url_summary}\nSuccessfully scraped: {', '.join(scraped_urls[:3])}{'...' if len(scraped_urls) > 3 else ''}\n\n{combined_text[:28000]}\n\nExtract comprehensive daycare information as JSON:"

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
            response_json = json.loads(json_text)
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


def scrape_daycare_info(url_or_urls, name="daycare"):
    """
    Enhanced scrape_daycare_info with support for multiple URLs per provider.
    
    Args:
        url_or_urls: Either a single URL string or a list of URLs
        name: Provider name for caching
    
    Returns:
        dict: Comprehensive daycare information
    """
    # Handle both single URL and list of URLs
    if isinstance(url_or_urls, list):
        if len(url_or_urls) == 0:
            return {}
        elif len(url_or_urls) == 1:
            # Single URL in list - use comprehensive approach
            url = url_or_urls[0]
        else:
            # Multiple URLs - use multi-URL approach
            return scrape_multiple_urls(url_or_urls, name)
    else:
        # Single URL string
        url = url_or_urls
    
    # Rest of function handles single URL comprehensive scraping
    cache_path = get_cache_path(name)
    text_cache_path = get_text_cache_path(name)
    
    if cache_path.exists():
        with open(cache_path, "r") as f:
            cached_data = json.load(f)
            # Return only the daycare info, not the metadata
            return {k: v for k, v in cached_data.items() 
                   if k not in ['scraping_method', 'pages_scraped', 'scraped_urls', 'total_text_length']}

    # Comprehensive multi-page scraping
    print(f"🚀 Starting comprehensive daycare analysis for {url}")
    combined_text, scraped_urls, page_details = scrape_comprehensive_daycare_info(url, name, max_pages=8)
    
    if not combined_text:
        return {}

    # Cache the comprehensive text with detailed metadata
    with open(text_cache_path, "w", encoding="utf-8") as f:
        f.write(f"Base URL: {url}\n")
        f.write(f"Scraping Method: comprehensive_multipage\n")
        f.write(f"Pages Scraped: {len(scraped_urls)}\n")
        f.write(f"Total Characters: {len(combined_text)}\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Scraped URLs:\n")
        for i, scraped_url in enumerate(scraped_urls, 1):
            f.write(f"  {i}. {scraped_url}\n")
        f.write("=" * 80 + "\n")
        f.write(combined_text)

    # DEBUG: Save combined content before Gemini analysis
    if DEBUG:
        debug_cache_path = CACHE_TEXT_DIR / f"debug_{name.replace(' ', '_')}_{int(time.time())}.txt"
        try:
            with open(debug_cache_path, "w", encoding="utf-8") as f:
                f.write(f"DEBUG - Combined content before Gemini analysis\n")
                f.write(f"Provider: {name}\n")
                f.write(f"Scraping type: Comprehensive multi-page\n")
                f.write(f"Base URL: {url}\n")
                f.write(f"Total pages scraped: {len(scraped_urls)}\n")
                f.write(f"Total content length: {len(combined_text)}\n")
                f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("All scraped URLs:\n")
                for i, scraped_url in enumerate(scraped_urls, 1):
                    f.write(f"  {i}. {scraped_url}\n")
                f.write("=" * 80 + "\n")
                f.write(combined_text)
            print(f"[DEBUG] Combined content saved to: {debug_cache_path}")
        except Exception as e:
            print(f"[DEBUG] Failed to save combined content: {e}")

    # Enhanced Gemini analysis for multi-page content
    print(f"🤖 Analyzing {len(combined_text)} characters with Gemini...")
    summary = call_gemini_summary_multipage(combined_text, scraped_urls)

    # Enhanced caching with comprehensive metadata
    enhanced_summary = {
        "scraping_method": "comprehensive_multipage",
        "pages_scraped": len(scraped_urls),
        "scraped_urls": scraped_urls,
        "total_text_length": len(combined_text),
        **summary
    }

    with open(cache_path, "w") as f:
        json.dump(enhanced_summary, f, indent=2)

    if DEBUG:
        print(f"[DEBUG] Analysis for {name}:")
        print(f"  Method: {enhanced_summary.get('scraping_method', 'unknown')}")
        print(f"  Content: {len(combined_text)} chars")
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
    start_time = time.time()
    text, method = get_text_from_url_smart(url)
    elapsed = time.time() - start_time
    
    if not text:
        print("❌ Failed to fetch website content")
        return {}
    
    print(f"✅ Fetched {len(text)} characters using {method} method ({elapsed:.1f}s)")
    
    # Cache the raw website text for debugging
    print(f"💾 Saving raw text to: {text_cache_path}")
    with open(text_cache_path, "w", encoding="utf-8") as f:
        f.write(f"URL: {url}\n")
        f.write(f"Method: {method}\n")
        f.write(f"Performance: {elapsed:.1f}s\n")
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
            "scraping_method": method,
            "performance_seconds": elapsed,
            **summary
        }, f, indent=2)
    
    print(f"\n📊 Extracted Information:")
    print("=" * 40)
    print(f"  Method Used: {method}")
    print(f"  Performance: {elapsed:.1f}s")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    print(f"\n✅ Test completed successfully!")
    print(f"📁 Check cache_json/ and cache_text/ folders for saved files")
    
    if DEBUG:
        print(f"🔍 DEBUG MODE: Simplified debug files saved to cache_text/ folder")
        print(f"   - Combined content before Gemini analysis only")
        print(f"   - Individual scraping attempts removed for cleaner output")
    
    return summary


def test_comprehensive_website(url, name=None):
    """
    Test function for comprehensive multi-page scraping.
    Shows detailed breakdown of pages scraped and analysis.
    """
    print("🧪 Testing Comprehensive Multi-Page Scraper...")
    print("=" * 70)
    
    # Generate name from URL if not provided
    if not name:        
        domain = urlparse(url).netloc
        name = f"comprehensive_{domain.replace('.', '_')}"
    
    print(f"🌐 Base URL: {url}")
    print(f"📁 Cache name: {name}")
    
    # Get cache paths
    cache_path = get_cache_path(name)
    text_cache_path = get_text_cache_path(name)
    
    print(f"\n📄 Files that will be created:")
    print(f"  • Comprehensive text: {text_cache_path}")
    print(f"  • Analysis JSON: {cache_path}")
    
    # Force refresh by removing existing cache
    if cache_path.exists():
        cache_path.unlink()
        print(f"🗑️ Removed existing JSON cache")
    if text_cache_path.exists():
        text_cache_path.unlink()
        print(f"🗑️ Removed existing text cache")
    
    # Run comprehensive scraping
    start_time = time.time()
    summary = scrape_daycare_info(url, name)
    elapsed = time.time() - start_time
    
    if not summary:
        print("❌ Comprehensive scraping failed")
        return {}
    
    # Read the cached metadata for display
    with open(cache_path, "r") as f:
        full_data = json.load(f)
    
    print(f"\n📊 Comprehensive Analysis Results:")
    print("=" * 50)
    print(f"  Total Performance: {elapsed:.1f}s")
    print(f"  Pages Scraped: {full_data.get('pages_scraped', 'Unknown')}")
    print(f"  Total Content: {full_data.get('total_text_length', 0):,} characters")
    
    if 'scraped_urls' in full_data:
        print(f"  Scraped URLs:")
        for i, scraped_url in enumerate(full_data['scraped_urls'][:10], 1):
            print(f"    {i}. {scraped_url}")
        if len(full_data['scraped_urls']) > 10:
            print(f"    ... and {len(full_data['scraped_urls']) - 10} more")
    
    print(f"\n🎯 Extracted Daycare Information:")
    print("=" * 40)
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    print(f"\n✅ Comprehensive test completed successfully!")
    print(f"📁 Check cache_json/ and cache_text/ folders for detailed files")
    
    if DEBUG:
        print(f"🔍 DEBUG MODE: Simplified debug files saved to cache_text/ folder")
        print(f"   - Combined content before Gemini analysis only")
        print(f"   - Individual scraping attempts removed for cleaner output")
    
    return summary


if __name__ == "__main__":
    # Interactive test when script is run directly    
    if len(sys.argv) > 1:
        # URL provided as command line argument
        test_url = sys.argv[1]
        
        # Auto-generate test name from domain if not provided
        if len(sys.argv) > 2:
            test_name = sys.argv[2]
        else:
            domain = urlparse(test_url).netloc
            test_name = f"auto_{domain.replace('.', '_')}"
        
        # Check for single page test flag (comprehensive is default)
        if len(sys.argv) > 3 and sys.argv[3].lower() in ['--single', '-s', 'single']:
            test_single_website(test_url, test_name)
        else:
            test_comprehensive_website(test_url, test_name)
    else:
        # Interactive mode
        print("🧪 Gemini Scraper Unit Test")
        print("=" * 40)
        print("Choose test mode:")
        print("1. Single page test (fast)")
        print("2. Comprehensive multi-page test (thorough) [DEFAULT]")
        print()
        
        choice = input("Enter choice (1 or 2, default is 2): ").strip()
        if not choice:
            choice = '2'  # Default to comprehensive
        
        while choice not in ['1', '2']:
            print("Please enter 1 or 2")
            choice = input("Enter choice (1 or 2, default is 2): ").strip()
            if not choice:
                choice = '2'
        
        print("\nEnter a daycare website URL to test:")
        print("Example: https://www.brightbeginningsdaycare.com")
        print()
        
        test_url = input("URL: ").strip()
        if test_url:
            # Auto-generate test name from domain
            domain = urlparse(test_url).netloc
            default_name = f"auto_{domain.replace('.', '_')}"
            
            test_name = input(f"Cache name (press Enter for '{default_name}'): ").strip()
            if not test_name:
                test_name = default_name
            
            if choice == '1':
                result = test_single_website(test_url, test_name)
            else:
                result = test_comprehensive_website(test_url, test_name)
        else:
            print("❌ No URL provided")
