from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import requests
from .base_views import firebase_login_required
from ..models import User


def get_location_from_coordinates(latitude, longitude):
    """
    Convert coordinates to city/district name using reverse geocoding
    Using OpenStreetMap's Nominatim API (free, no API key needed)
    """
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=json"
        headers = {
            'User-Agent': 'VidhikPath/1.0'  # Required by Nominatim
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            address = data.get('address', {})
            
            # Extract city/district information
            city = (address.get('city') or 
                   address.get('town') or 
                   address.get('village') or 
                   address.get('municipality') or
                   address.get('district'))
            
            state = address.get('state', '')
            country = address.get('country', '')
            
            return {
                'city': city,
                'state': state,
                'country': country,
                'full_location': f"{city}, {state}" if city and state else city or state
            }
    except Exception as e:
        print(f"Geocoding error: {str(e)}")
    
    return None


@csrf_exempt
@firebase_login_required
def find_lawyers_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            location = data.get('location', '').strip()
            lawyer_type = data.get('lawyer_type', '').strip()
            specialization = data.get('specialization', '').strip()
            use_current_location = data.get('use_current_location', False)
            user_lat = data.get('latitude')
            user_lng = data.get('longitude')
            
            # Location is already provided from frontend's LocationIQ API
            # No need to do geocoding again in backend
            
            # Validate that we have a location to search
            if not location:
                return JsonResponse({
                    'error': 'Please provide a location to search.',
                    'lawyers': []
                }, status=400)
            
            # Get lawyers based on location and type
            lawyers = User.find_lawyers(location, lawyer_type)
            
            # Filter lawyers whose location matches the search location
            lawyers_data = []
            for lawyer in lawyers:
                lawyer_location = lawyer.get('location', '').lower()
                search_location = location.lower()
                
                # Check if lawyer's location contains the search location
                # or if search location is contained in lawyer's location
                if search_location in lawyer_location or lawyer_location in search_location:
                    lawyers_data.append({
                        'firebase_uid': lawyer.get('firebase_uid', ''),
                        'name': lawyer.get('name', 'N/A'),
                        'phone': lawyer.get('phone', 'N/A'),
                        'lawyer_type': lawyer.get('lawyer_type', 'N/A'),
                        'experience': lawyer.get('experience', 0),
                        'location': lawyer.get('location', 'N/A'),
                        'email': lawyer.get('email', 'N/A'),
                        'languages_spoken': lawyer.get('languages_spoken', []),
                        'verified': lawyer.get('verified', False),
                        'rating': lawyer.get('rating', 0.0)
                    })
            
            response_data = {
                'lawyers': lawyers_data,
                'count': len(lawyers_data)
            }
            
            return JsonResponse(response_data)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data', 'lawyers': []}, status=400)
        except Exception as e:
            print(f"Error in find_lawyers_api: {str(e)}")
            return JsonResponse({'error': f'Server error: {str(e)}', 'lawyers': []}, status=500)
    
    return JsonResponse({'error': 'Invalid request method. Use POST.', 'lawyers': []}, status=405)