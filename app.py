import streamlit as st
import pandas as pd
from io import BytesIO
from google_places import search_daycares
from daycare_scraper import scrape_keywords
from daycare_scraper_gemini import scrape_daycare_info
from scoring import compute_score, WEIGHTS as DEFAULT_WEIGHTS
from formatter import classify_type, check_msft_discount
import json, os

if os.getenv("GEMINI_DEBUG") == "1":
    st.info("🔍 Gemini debug mode is ON. JSON outputs will print to terminal.")

st.set_page_config(page_title="Daycare Autofill", layout="wide")
st.title("🔍 Daycare Autofill Tool")

# Sidebar for selecting scraper engine
st.sidebar.header("🔎 Scraper Engine")
scraper_mode = st.sidebar.radio("", ["Gemini (Smart)", "Keyword (Fast)"])

# Set up sidebar for user input, default weights, and scoring
st.sidebar.header("⚖️ Scoring Weights")
user_weights = {
    "Mandarin": st.sidebar.slider("Mandarin Exposure", 0, 5, DEFAULT_WEIGHTS["Mandarin"]),
    "Meals": st.sidebar.slider("Meals Provided", 0, 5, DEFAULT_WEIGHTS["Meals"]),
    "Curriculum": st.sidebar.slider("Curriculum", 0, 5, DEFAULT_WEIGHTS["Curriculum"]),
    "Staff Stability": st.sidebar.slider("Staff Stability", 0, 5, DEFAULT_WEIGHTS["Staff Stability"]),
    "Cultural Diversity": st.sidebar.slider("Cultural Diversity", 0, 5, DEFAULT_WEIGHTS["Cultural Diversity"]),
    "MSFT Discount": st.sidebar.slider("MSFT Discount", 0, 5, DEFAULT_WEIGHTS["MSFT Discount"])
}



location = st.text_input("Enter your address", value="1028 179th PL NE, Bellevue, WA 98008")
radius_miles = st.slider("📍 Search Radius (miles)", min_value=1, max_value=10, step=1, value=5)
limit = st.number_input("Max results", min_value=1, max_value=50, value=10)

if st.button("Search Daycares"):
    with st.spinner("Fetching from Google Maps..."):
        results = search_daycares(location, max_driving_distance_miles=radius_miles, limit=limit)

    st.success(f"Found {len(results)} results. Scraping websites...")

    with open("providers_msft.json") as f:
        msft_list = json.load(f)

    keywords = {
        "Mandarin": ["mandarin", "chinese", "bilingual"],
        "Meals Provided": ["meals", "lunch", "snack included"],
        "Curriculum": ["montessori", "play-based", "reggio", "emergent"],
        "Cultural Diversity": ["diverse", "inclusive", "multicultural"],
        "Staff Stability": ["same teacher", "low turnover", "consistent caregiver"]
    }

    for row in results:
        row["Type (Center/Family)"] = classify_type(row["Name"])
        row["MSFT Discount"] = check_msft_discount(row["Name"], msft_list)
        # Scrape website for detailed info
        if row["Website"]:
            if scraper_mode.startswith("Gemini"):                
                scraped = scrape_daycare_info(row["Website"], name=row["Name"])
            else:                
                scraped = scrape_keywords(row["Website"], keywords)
            row.update(scraped)
        else:
            row.update({
                "AgesServed": "",
                "Mandarin": "No",
                "MealsProvided": "No",
                "Curriculum": "",
                "CulturalDiversity": "Unknown",
                "StaffStability": "No"
            })
        # Update scoring to use current user_weights
        row["Score"] = compute_score(row, weights=user_weights)

    df = pd.DataFrame(results)
    st.dataframe(df)

    # Convert dataframe to Excel bytes for download
    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False, engine='openpyxl')
    excel_buffer.seek(0)
    
    st.download_button(
        label="Download as Excel",
        data=excel_buffer.getvalue(),
        file_name="daycare_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
