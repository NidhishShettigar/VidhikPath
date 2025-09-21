# middleware.py - Firebase Authentication Middleware
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from .models import FirebaseTokenManager, User
import json


class FirebaseAuthenticationMiddleware:
    """
    Middleware to handle Firebase authentication for protected routes
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Routes that require authentication
        self.protected_routes = [
            '/dashboard/',
            '/api/chat/',
            '/api/summarize/',
            '/api/find-lawyers/',
            '/api/forum/',
            '/profile/',
            '/chatbot/',
            '/document-summarizer/',
            '/lawyer-connector/',
            '/forum/',
        ]
        
        # Routes that should redirect to dashboard if already logged in
        self.guest_only_routes = [
            '/login/',
            '/register/',
        ]

    def __call__(self, request):
        # Check if route requires protection
        requires_auth = any(request.path.startswith(route) for route in self.protected_routes)
        is_guest_only = any(request.path.startswith(route) for route in self.guest_only_routes)
        
        # Get Firebase token from session or header
        firebase_token = request.session.get('firebase_token')
        if not firebase_token:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                firebase_token = auth_header[7:]
        
        # Handle protected routes
        if requires_auth:
            if not firebase_token:
                if request.path.startswith('/api/'):
                    return JsonResponse({
                        'error': 'Authentication required',
                        'redirect': '/login/'
                    }, status=401)
                return HttpResponseRedirect(reverse('login'))
            
            # Verify token and get user
            result = FirebaseTokenManager.verify_token(firebase_token)
            
            if not result['success']:
                # Clear invalid session
                request.session.pop('firebase_token', None)
                request.session.pop('firebase_uid', None)
                
                if request.path.startswith('/api/'):
                    return JsonResponse({
                        'error': 'Invalid or expired token',
                        'redirect': '/login/'
                    }, status=401)
                return HttpResponseRedirect(reverse('login'))
            
            # Add user data to request
            request.firebase_uid = result['firebase_uid']
        
        # Handle guest-only routes (redirect if already logged in)
        elif is_guest_only and firebase_token:
            # Verify token is still valid
            result = FirebaseTokenManager.verify_token(firebase_token)
            if result['success']:
                return HttpResponseRedirect(reverse('dashboard'))
        
        response = self.get_response(request)
        return response


class FirebaseTokenRefreshMiddleware:
    """
    Middleware to automatically refresh Firebase tokens when they're about to expire
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if user has Firebase token
        firebase_token = request.session.get('firebase_token')
        firebase_uid = request.session.get('firebase_uid')
        
        if firebase_token and firebase_uid:
            # Here you could implement token refresh logic
            # Firebase tokens typically expire after 1 hour
            # You might want to decode the token and check its expiry time
            pass
        
        response = self.get_response(request)
        return response