from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
import functools
from ..firebase_utils import FirebaseAuth
from ..models import UserSession, FirebaseTokenManager
from openai import OpenAI

# client = OpenAI(api_key=settings.OPENAI_API_KEY)

def firebase_login_required(view_func):
    """Decorator to require Firebase authentication"""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check for Firebase token in session or header
        firebase_token = request.session.get('firebase_token') or request.headers.get('Authorization')
        
        if not firebase_token:
            if request.is_ajax() or 'api' in request.path:
                return JsonResponse({'error': 'Authentication required', 'redirect': '/login/'}, status=401)
            return redirect('login')
        
        # Clean token if it has "Bearer " prefix
        if firebase_token.startswith('Bearer '):
            firebase_token = firebase_token[7:]
        
        # Verify token and get user
        result = FirebaseTokenManager.get_user_from_token(firebase_token)
        
        if not result['success']:
            # Clear invalid session
            request.session.pop('firebase_token', None)
            request.session.pop('firebase_uid', None)
            
            if request.is_ajax() or 'api' in request.path:
                return JsonResponse({'error': 'Invalid token', 'redirect': '/login/'}, status=401)
            return redirect('login')
        
        # Add user data to request
        request.firebase_user = result['user']
        request.firebase_uid = result['firebase_uid']
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def landing_page(request):
    return render(request, 'landing.html')

def logout_view(request):
    firebase_uid = request.session.get('firebase_uid')
    if firebase_uid:
        UserSession.invalidate_session(firebase_uid)
    request.session.flush()
    return redirect('login')
