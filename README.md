# Daycare Autofill Streamlit App

This app helps families search and compare daycare providers near a given location using the Google Maps Places API. It scores daycares based on development-focused criteria and MSFT discount eligibility.

## 🚀 Deployment (Streamlit Cloud)

1. Push this repo to GitHub (public repo).
2. Go to [Streamlit Cloud](https://streamlit.io/cloud)
3. Select this repo and set `app.py` as the entry point.
4. Under **Secrets**, add:
GOOGLE_MAPS_API_KEY=your-key-here
GEMINI_API_KEY=your-key-here

## ⚙️ Configuration

- Weights are in `scoring.py`
- MSFT provider names in `providers_msft.json`

## 🧪 Local Setup (Python virtual environment)

### 1. Clone this repo
```bash
git clone https://github.com/YOUR_USERNAME/daycare-autofill.git
cd daycare-autofill
```
### 2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate       # Mac/Linux
venv\Scripts\activate          # Windows
```
### 3. Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
### 4. Create .env file
```ini
GOOGLE_MAPS_API_KEY=your-key-here
GEMINI_API_KEY=your-key-here
```
### 5. Run the Streamlit app
```bash
streamlit run app.py
```
You can now test the app locally at http://localhost:8501