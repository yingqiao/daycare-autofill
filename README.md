# Daycare Autofill Streamlit App

This app helps families search and compare daycare providers near a given location using the Google Maps Places API. It scores daycares based on development-focused criteria and MSFT discount eligibility.

## 🔧 Setup (Local)

1. Add your API key to a `.env` file:
GOOGLE_MAPS_API_KEY=your-key-here

2. Install dependencies:
pip install -r requirements.txt

3. Run the app:
streamlit run app.py

## 🚀 Deployment (Streamlit Cloud)

1. Push this repo to GitHub (public repo).
2. Go to [Streamlit Cloud](https://streamlit.io/cloud)
3. Select this repo and set `app.py` as the entry point.
4. Under **Secrets**, add:
GOOGLE_MAPS_API_KEY=your-key-here

## ⚙️ Configuration

- Weights are in `scoring.py`
- MSFT provider names in `providers_msft.json`
