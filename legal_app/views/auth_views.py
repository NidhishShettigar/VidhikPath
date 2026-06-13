from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from ..firebase_utils import FirebaseAuth
from ..models import User, UserSession, FirebaseTokenManager

def login_page(request):
    if request.session.get('firebase_uid'):
        return redirect('dashboard')
    return render(request, 'login.html')

def register_page(request):
    if request.session.get('firebase_token'):
        return redirect('login')
    return render(request, 'register.html')

@csrf_exempt
def firebase_verify_token(request):
    """Verify Firebase ID token and create/login user"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            id_token = data.get('idToken')
            user_data = data.get('userData', {})  # Additional user data from registration
            
            if not id_token:
                return JsonResponse({'success': False, 'error': 'No token provided'})
            
            # Verify Firebase token
            token_result = FirebaseTokenManager.verify_token(id_token)
            
            if not token_result['success']:
                return JsonResponse({'success': False, 'error': 'Invalid token'})
            
            firebase_uid = token_result['firebase_uid']
            email = token_result['email']
            
            # Check if user exists in MongoDB
            user = User.find_by_firebase_uid(firebase_uid)
            
            if not user:
                # Create new user if doesn't exist
                user_creation_data = {
                    'name': user_data.get('name', token_result.get('name', '')),
                    'user_type': user_data.get('user_type', 'user'),
                    'phone': user_data.get('phone', ''),
                    'location': user_data.get('location', ''),
                }
                
                # Add lawyer-specific fields if user_type is lawyer
                if user_data.get('user_type') == 'lawyer':
                    user_creation_data.update({
                        'lawyer_type': user_data.get('lawyer_type', ''),
                        'experience': int(user_data.get('experience', 0)),
                        'license_number': user_data.get('license_number', ''),
                        'languages_spoken': user_data.get('languages_spoken', []),
                        'education': user_data.get('education', ''),
                    })
                
                User.create(firebase_uid, email, **user_creation_data)
                user = User.find_by_firebase_uid(firebase_uid)
            
            # Store session data
            request.session['firebase_token'] = id_token
            request.session['firebase_uid'] = firebase_uid
            request.session['user_email'] = email
            
            # Update/create session in MongoDB
            refresh_token = data.get('refreshToken', '')
            UserSession.update_session(firebase_uid, id_token, refresh_token)
            
            return JsonResponse({
                'success': True,
                'user': {
                    'firebase_uid': firebase_uid,
                    'email': email,
                    'name': user.get('name', ''),
                    'user_type': user.get('user_type', 'user'),
                    'is_lawyer': user.get('user_type') == 'lawyer'
                },
                'redirect': '/dashboard/'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
        except Exception as e:
            print(f"Error in firebase_verify_token: {e}")
            return JsonResponse({'success': False, 'error': f'Server error: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@csrf_exempt
def firebase_password_reset(request):
    """Send password reset email via Firebase"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            
            result = FirebaseAuth.send_password_reset_email(email)
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

