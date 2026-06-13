from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.templatetags.static import static
import functools
import logging
import os
from ..firebase_utils import FirebaseAuth
from ..models import UserSession, FirebaseTokenManager
from openai import OpenAI
from ..models import User

# client = OpenAI(api_key=settings.OPENAI_API_KEY)

logger = logging.getLogger(__name__)


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'

def firebase_login_required(view_func):
    """Decorator to require Firebase authentication and attach user to request"""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check for Firebase token in session or header
        firebase_token = request.session.get('firebase_token') or request.headers.get('Authorization')
        
        if not firebase_token:
            if _is_ajax(request) or 'api' in request.path:
                return JsonResponse({'error': 'Authentication required', 'redirect': '/login/'}, status=401)
            return redirect('login')
        
        # Clean token if it has "Bearer " prefix
        if firebase_token.startswith('Bearer '):
            firebase_token = firebase_token[7:]
        
        # Verify token and get Firebase info
        result = FirebaseTokenManager.verify_token(firebase_token)
        
        if not result['success']:
            # Clear invalid session
            request.session.pop('firebase_token', None)
            request.session.pop('firebase_uid', None)
            
            if _is_ajax(request) or 'api' in request.path:
                return JsonResponse({'error': 'Invalid token', 'redirect': '/login/'}, status=401)
            return redirect('login')
        
        # Attach Firebase UID
        request.firebase_uid = result['firebase_uid']
        
        # Fetch full user document from MongoDB
        user_doc = User.find_by_firebase_uid(result['firebase_uid'])
        request.firebase_user = user_doc  # Attach full user object
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def landing_page(request):
    try:
        base_css_url = static("css/base.css")
        landing_css_url = static("css/landing.css")
        base_css_collected = os.path.exists(os.path.join(settings.STATIC_ROOT, "css", "base.css"))
        landing_css_collected = os.path.exists(os.path.join(settings.STATIC_ROOT, "css", "landing.css"))
        static_root_entries = []
        if os.path.exists(settings.STATIC_ROOT):
            for root, _, files in os.walk(settings.STATIC_ROOT):
                for file_name in files:
                    rel_path = os.path.relpath(os.path.join(root, file_name), settings.STATIC_ROOT)
                    static_root_entries.append(rel_path.replace("\\", "/"))
                    if len(static_root_entries) >= 8:
                        break
                if len(static_root_entries) >= 8:
                    break
        logger.info(
            "Homepage static diagnostics: static_root=%s base_css_url=%s landing_css_url=%s base_css_collected=%s landing_css_collected=%s sample_collected_files=%s",
            settings.STATIC_ROOT,
            base_css_url,
            landing_css_url,
            base_css_collected,
            landing_css_collected,
            static_root_entries,
        )
        return render(request, 'landing.html')
    except Exception:
        logger.exception(
            "Homepage render failed. path=%s host=%s secure=%s",
            request.path,
            request.get_host(),
            request.is_secure(),
        )
        return HttpResponse("VidhikPath Backend Running Successfully", status=200)

def logout_view(request):
    firebase_uid = request.session.get('firebase_uid')
    if firebase_uid:
        UserSession.invalidate_session(firebase_uid)
    request.session.flush()
    return redirect('login')
