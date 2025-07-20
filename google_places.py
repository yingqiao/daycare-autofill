import googlemaps
from dotenv import load_dotenv
import os, time

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

def search_daycares(location, max_driving_distance_miles=5, limit=20):
    if not gmaps:
        print("❌ Google Maps client not available")
        return []
        
    try:
        print(f"🔍 Searching for daycares near: {location} (within {max_driving_distance_miles} miles driving)")
        loc = gmaps.geocode(location)[0]['geometry']['location']
        latlng = (loc['lat'], loc['lng'])
        print(f"📍 Coordinates: {latlng}")

        # Step 1: Get all places using rankby='distance' with pagination
        all_places = []
        next_page_token = None
        max_pages = 3  # Limit to avoid excessive API calls (60 results max)
        
        for page in range(max_pages):
            if page == 0:
                # First request
                places_result = gmaps.places_nearby(
                    location=latlng,
                    rank_by='distance',  # Sort by straight-line distance, no radius limit
                    keyword="daycare"
                )
            else:
                # Subsequent requests with page token
                if not next_page_token:
                    break
                # Small delay required for page tokens                
                time.sleep(2)
                places_result = gmaps.places_nearby(
                    location=latlng,
                    page_token=next_page_token
                )
            
            if places_result.get("status") != "OK":
                print(f"Places API error: {places_result.get('status')}")
                break
                
            current_places = places_result.get("results", [])
            all_places.extend(current_places)
            print(f"📄 Page {page + 1}: Found {len(current_places)} places (total: {len(all_places)})")
            
            # Check for next page
            next_page_token = places_result.get("next_page_token")
            if not next_page_token:
                break

        print(f"🔍 Processing {len(all_places)} places to calculate driving distances...")

        # Step 2: Calculate driving distance for ALL places (no early limit)
        all_results = []
        for i, place in enumerate(all_places):
            if i % 10 == 0:  # Progress indicator
                print(f"Processing place {i + 1}/{len(all_places)}...")
                
            details = gmaps.place(place["place_id"], fields=[
                "name", "formatted_address", "website", "formatted_phone_number", "rating", "geometry"
            ])
            data = details.get("result", {})
            
            # Calculate distance using Google's Distance Matrix API
            daycare_location = data.get("geometry", {}).get("location")
            distance_info = {"distance_miles": None, "distance_text": "Unknown"}
            
            if daycare_location:
                try:
                    distance_result = gmaps.distance_matrix(
                        origins=[latlng],
                        destinations=[(daycare_location['lat'], daycare_location['lng'])],
                        units="imperial"
                    )
                    
                    if (distance_result['status'] == 'OK' and 
                        distance_result['rows'][0]['elements'][0]['status'] == 'OK'):
                        element = distance_result['rows'][0]['elements'][0]
                        distance_info = {
                            "distance_miles": element['distance']['value'] / 1609.34,  # Convert meters to miles
                            "distance_text": element['distance']['text']
                        }
                except Exception as dist_error:
                    print(f"Distance calculation failed for {data.get('name', 'Unknown')}: {dist_error}")
            
            all_results.append({
                "Name": data.get("name"),
                "Address": data.get("formatted_address"),
                "Website": data.get("website"),
                "Phone": data.get("formatted_phone_number"),
                "Rating": data.get("rating"),
                "Distance": distance_info["distance_text"],
                "DistanceMiles": distance_info["distance_miles"]
            })

        # Step 3: Filter by actual driving distance
        filtered_results = [
            r for r in all_results 
            if r['DistanceMiles'] is not None and r['DistanceMiles'] <= max_driving_distance_miles
        ]
        
        # Step 4: Sort by driving distance (might reorder from straight-line sorting)
        filtered_results.sort(key=lambda x: x['DistanceMiles'])
        
        # Step 5: Apply final limit to get closest N results
        final_results = filtered_results[:limit]
        
        # Step 6: Remove DistanceMiles column for user output (keep Distance for display)
        for result in final_results:
            del result['DistanceMiles']
        
        print(f"✅ Found {len(all_results)} total places, {len(filtered_results)} within {max_driving_distance_miles} miles")
        print(f"📋 Returning {len(final_results)} closest results")
        return final_results
        
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
        results = search_daycares("Seattle, WA", max_driving_distance_miles=3, limit=3)
        if results:
            print(f"✅ Places search works: Found {len(results)} daycares")
            for i, daycare in enumerate(results[:2], 1):
                distance = daycare.get('Distance', 'Unknown')
                print(f"  {i}. {daycare['Name']} - {daycare['Address']} ({distance})")
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
