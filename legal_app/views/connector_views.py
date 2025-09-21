from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .base_views import firebase_login_required
from ..models import User


@csrf_exempt
@firebase_login_required
def find_lawyers_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            location = data.get('location', '')
            lawyer_type = data.get('lawyer_type', '')
            specialization = data.get('specialization', '')
            
            lawyers = User.find_lawyers(location, lawyer_type)
            
            lawyers_data = []
            for lawyer in lawyers:
                lawyers_data.append({
                    'firebase_uid': lawyer['firebase_uid'],
                    'name': lawyer.get('name', ''),
                    'lawyer_type': lawyer.get('lawyer_type', ''),
                    'experience': lawyer.get('experience', 0),
                    'location': lawyer.get('location', ''),
                    'email': lawyer.get('email', ''),
                    'languages_spoken': lawyer.get('languages_spoken', []),
                    'verified': lawyer.get('verified', False),
                    'rating': lawyer.get('rating', 0.0)
                })
            
            return JsonResponse({'lawyers': lawyers_data})
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)