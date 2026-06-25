from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from ..firebase_utils import FirebaseAuth
from ..models import User, UserSession, FirebaseTokenManager
import firebase_admin
import traceback
from django.conf import settings

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
            # Log incoming headers and body for debugging
            try:
                headers = dict(request.headers)
            except Exception:
                headers = {k: v for k, v in request.META.items() if k.startswith('HTTP_')}
            print('[firebase_verify_token] headers:', headers)

            raw_body = request.body.decode('utf-8', errors='replace') if request.body else ''
            print('[firebase_verify_token] raw_body:', raw_body)

            data = json.loads(request.body) if raw_body else {}
            id_token = data.get('idToken')
            user_data = data.get('userData', {})  # Additional user data from registration

            # Also accept Authorization: Bearer <token>
            auth_header = headers.get('Authorization') or headers.get('authorization') or request.META.get('HTTP_AUTHORIZATION')
            if not id_token and auth_header:
                if auth_header.startswith('Bearer '):
                    id_token = auth_header.split(' ', 1)[1].strip()

            if not id_token:
                print('[firebase_verify_token] No idToken found in body or Authorization header')
                return JsonResponse({'success': False, 'error': 'No token provided'})

            # Log token presence and length (do not print full token)
            try:
                token_len = len(id_token)
            except Exception:
                token_len = None
            masked = (id_token[:10] + '...' + id_token[-10:]) if token_len and token_len > 30 else id_token
            print(f"[firebase_verify_token] token_len={token_len} masked={masked}")

            # Verify Firebase token
            token_result = FirebaseTokenManager.verify_token(id_token)

            # Log Firebase verification result
            print('[firebase_verify_token] token_result:', token_result)

            if not token_result.get('success'):
                # Log detailed error and traceback if available
                err_msg = token_result.get('error')
                tb = token_result.get('traceback')
                print(f"[firebase_verify_token] verification failed: {err_msg}")
                if tb:
                    print(tb)

                # Log Firebase admin init status and configured frontend project id
                try:
                    apps = list(firebase_admin._apps.keys()) if hasattr(firebase_admin, '_apps') else []
                except Exception:
                    apps = []
                print(f"[firebase_verify_token] firebase_admin apps={apps} configured_project={settings.FIREBASE_CONFIG.get('projectId')}")

                # Return the real exception message and type to frontend for debugging
                return JsonResponse({
                    'success': False,
                    'error': err_msg or 'Invalid token',
                    'exception_type': type(err_msg).__name__ if err_msg is not None else None,
                    'traceback': tb,
                })
            
            firebase_uid = token_result['firebase_uid']
            email = token_result.get('email')
            
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
                'uid': firebase_uid,
                'email': email,
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