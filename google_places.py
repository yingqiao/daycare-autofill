import googlemaps
from dotenv import load_dotenv
import os
import sys

load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Debug function to check API key status
def check_api_key():
    if not API_KEY:
        print("❌ ERROR: No API key found in .env file")
        return False
    elif len(API_KEY) < 30:
        print("❌ ERROR: API key seems too short (invalid)")
        return False
    else:
        print(f"✅ API key found: {API_KEY[:10]}...{API_KEY[-4:]}")
        return True

if not check_api_key():
    print("Please check your .env file and Google Cloud Console settings")

try:
    gmaps = googlemaps.Client(key=API_KEY)
    print("✅ Google Maps client initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize Google Maps client: {e}")
    gmaps = None

def search_daycares(location, radius_meters=5000, limit=20):
    if not gmaps:
        print("❌ Google Maps client not available")
        return []
        
    try:
        print(f"🔍 Searching for daycares near: {location}")
        loc = gmaps.geocode(location)[0]['geometry']['location']
        latlng = (loc['lat'], loc['lng'])
        print(f"📍 Coordinates: {latlng}")

        places_result = gmaps.places_nearby(
            location=latlng,
            radius=radius_meters,
            keyword="daycare",
            #type="school"
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
        print(f"✅ Found {len(results)} daycares")
        return results
    except Exception as e:
        print(f"❌ Error searching daycares: {e}")
        return []


def test_google_places_api():
    """
    Test function to verify Google Places API is working correctly.
    Tests basic geocoding and places search functionality.
    """
    print("🧪 Testing Google Places API...")
    print("=" * 50)
    
    # Test 1: Check API key
    print("Test 1: API Key Check")
    if not check_api_key():
        return False
    
    # Test 2: Test geocoding
    print("\nTest 2: Geocoding Test")
    try:
        test_location = "Seattle, WA"
        geocode_result = gmaps.geocode(test_location)
        if geocode_result:
            coords = geocode_result[0]['geometry']['location']
            print(f"✅ Geocoding works: {test_location} -> {coords}")
        else:
            print("❌ Geocoding failed: No results")
            return False
    except Exception as e:
        print(f"❌ Geocoding error: {e}")
        return False
    
    # Test 3: Test places search (limited to 3 results for testing)
    print("\nTest 3: Places Search Test")
    try:
        results = search_daycares("Seattle, WA", limit=3)
        if results:
            print(f"✅ Places search works: Found {len(results)} daycares")
            for i, daycare in enumerate(results[:2], 1):
                print(f"  {i}. {daycare['Name']} - {daycare['Address']}")
        else:
            print("❌ Places search failed: No results")
            return False
    except Exception as e:
        print(f"❌ Places search error: {e}")
        return False
    
    print("\n🎉 All tests passed! Google Places API is working correctly.")
    return True


if __name__ == "__main__":
    # Run test when script is executed directly
    test_google_places_api()
