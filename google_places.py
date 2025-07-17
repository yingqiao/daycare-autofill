import googlemaps
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=API_KEY)

def search_daycares(location, radius=5000, limit=20):
    loc = gmaps.geocode(location)[0]['geometry']['location']
    latlng = (loc['lat'], loc['lng'])

    places_result = gmaps.places_nearby(
        location=latlng,
        radius=radius,
        keyword="daycare",
        type="school"
    )

    results = []
    for place in places_result.get("results", [])[:limit]:
        details = gmaps.place(place["place_id"], fields=[
            "name", "formatted_address", "website", "formatted_phone_number", "rating"
        ])
        data = details.get("result", {})
        results.append({
            "Name": data.get("name"),
            "Address": data.get("formatted_address"),
            "Website": data.get("website"),
            "Phone": data.get("formatted_phone_number"),
            "Rating": data.get("rating"),
        })
    return results
