from importlib import import_module
import logging

from django.http import HttpResponse, JsonResponse
from django.urls import path

logger = logging.getLogger(__name__)


def _lazy_view(module_path, func_name, is_api=False):
    def _view(request, *args, **kwargs):
        try:
            module = import_module(module_path)
            view_fn = getattr(module, func_name)
            return view_fn(request, *args, **kwargs)
        except Exception:
            logger.exception(
                "Route execution failed for path=%s module=%s view=%s",
                request.path,
                module_path,
                func_name,
            )
            if request.path == "/":
                return HttpResponse("VidhikPath Backend Running Successfully", status=200)
            if is_api:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Service temporarily unavailable",
                    },
                    status=503,
                )
            return HttpResponse("Service temporarily unavailable", status=503)

    _view.__name__ = f"lazy_{func_name}"

    # Preserve @csrf_exempt from the wrapped view onto this wrapper.
    # Without this, CsrfViewMiddleware enforces CSRF on the wrapper
    # (since it checks the resolved callable, not the inner function),
    # causing Django's HTML CSRF-failure page to be returned to fetch()
    # calls that expect JSON.
    if is_api:
        _view.csrf_exempt = True
    else:
        try:
            module = import_module(module_path)
            view_fn = getattr(module, func_name)
            if getattr(view_fn, "csrf_exempt", False):
                _view.csrf_exempt = True
        except Exception:
            pass

    return _view

urlpatterns = [
    path('', _lazy_view('legal_app.views.base_views', 'landing_page'), name='landing'),
    path('login/', _lazy_view('legal_app.views.auth_views', 'login_page'), name='login'),
    path('register/', _lazy_view('legal_app.views.auth_views', 'register_page'), name='register'),
    path('dashboard/', _lazy_view('legal_app.views.pages', 'dashboard'), name='dashboard'),
    path('chatbot/', _lazy_view('legal_app.views.pages', 'chatbot'), name='chatbot'),
    path('document-summarizer/', _lazy_view('legal_app.views.pages', 'document_summarizer'), name='summerizer'),
    path('lawyer-connector/', _lazy_view('legal_app.views.pages', 'lawyer_connector'), name='connector'),
    path('forum/', _lazy_view('legal_app.views.pages', 'public_forum'), name='forum'),
    path('profile/', _lazy_view('legal_app.views.profile_views', 'user_profile'), name='profile'),
    path('api/profile/update/', _lazy_view('legal_app.views.profile_views', 'update_profile', is_api=True), name='update_profile'),
    path('logout/', _lazy_view('legal_app.views.base_views', 'logout_view'), name='logout'),
    
    # API endpoints
    path('api/chat/', _lazy_view('legal_app.views.chatbot_views', 'chat_api', is_api=True), name='chat_api'),
    path('api/summarize/', _lazy_view('legal_app.views.summarizer_views', 'summarize_api', is_api=True), name='summarize_api'),
    path('api/find-lawyers/', _lazy_view('legal_app.views.connector_views', 'find_lawyers_api', is_api=True), name='find_lawyers_api'),
    
    # Forum API endpoints - ENHANCED
    path('api/forum/post/', _lazy_view('legal_app.views.forum_views', 'create_post_api', is_api=True), name='create_post_api'),
    path('api/forum/edit/', _lazy_view('legal_app.views.forum_views', 'edit_post_api', is_api=True), name='edit_post_api'),
    path('api/forum/like/', _lazy_view('legal_app.views.forum_views', 'like_post_api', is_api=True), name='like_post_api'),
    path('api/forum/reply/', _lazy_view('legal_app.views.forum_views', 'reply_post_api', is_api=True), name='reply_post_api'),
    path('api/forum/reply/edit/', _lazy_view('legal_app.views.forum_views', 'edit_reply_api', is_api=True), name='edit_reply_api'),
    path('api/forum/reply/delete/', _lazy_view('legal_app.views.forum_views', 'delete_reply_api', is_api=True), name='delete_reply_api'),
    path('api/forum/nested-reply/', _lazy_view('legal_app.views.forum_views', 'nested_reply_api', is_api=True), name='nested_reply_api'),
    path('api/forum/nested-reply/edit/', _lazy_view('legal_app.views.forum_views', 'edit_nested_reply_api', is_api=True), name='edit_nested_reply_api'),
    path('api/forum/nested-reply/delete/', _lazy_view('legal_app.views.forum_views', 'delete_nested_reply_api', is_api=True), name='delete_nested_reply_api'),
    path('api/forum/delete/', _lazy_view('legal_app.views.forum_views', 'delete_post_api', is_api=True), name='delete_post_api'),
    
    # Firebase API endpoints
    path('api/firebase/verify-token/', _lazy_view('legal_app.views.auth_views', 'firebase_verify_token', is_api=True), name='firebase_verify_token'),
    path('api/firebase/password-reset/', _lazy_view('legal_app.views.auth_views', 'firebase_password_reset', is_api=True), name='firebase_password_reset'),
]