import streamlit as st
import pandas as pd
from google_places import search_daycares
from daycare_scraper import scrape_keywords
from scoring import compute_score, WEIGHTS as DEFAULT_WEIGHTS
from formatter import classify_type, check_msft_discount
import json

st.set_page_config(page_title="Daycare Autofill", layout="wide")
st.title("🔍 Daycare Autofill Tool")
st.sidebar.header("⚖️ Scoring Weights")

user_weights = {
    "Mandarin": st.sidebar.slider("Mandarin Exposure", 0, 5, DEFAULT_WEIGHTS["Mandarin"]),
    "Meals": st.sidebar.slider("Meals Provided", 0, 5, DEFAULT_WEIGHTS["Meals"]),
    "Curriculum": st.sidebar.slider("Curriculum", 0, 5, DEFAULT_WEIGHTS["Curriculum"]),
    "Staff Stability": st.sidebar.slider("Staff Stability", 0, 5, DEFAULT_WEIGHTS["Staff Stability"]),
    "Cultural Diversity": st.sidebar.slider("Cultural Diversity", 0, 5, DEFAULT_WEIGHTS["Cultural Diversity"]),
    "MSFT Discount": st.sidebar.slider("MSFT Discount", 0, 5, DEFAULT_WEIGHTS["MSFT Discount"])
}



location = st.text_input("Enter your address", value="Bellevue, WA 98008")
radius = st.slider("Search radius (meters)", min_value=1000, max_value=10000, value=5000)
limit = st.number_input("Max results", min_value=1, max_value=50, value=10)

if st.button("Search Daycares"):
    with st.spinner("Fetching from Google Maps..."):
        results = search_daycares(location, radius, limit)

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
        if row["Website"]:
            scraped = scrape_keywords(row["Website"], keywords)
            row.update(scraped)
        else:
            row.update({k: "No" for k in keywords})
        # Update scoring to use current user_weights
        row["Score"] = compute_score(row, weights=user_weights)

    df = pd.DataFrame(results)
    st.dataframe(df)

    st.download_button("Download as Excel", df.to_excel(index=False), file_name="daycare_results.xlsx")
