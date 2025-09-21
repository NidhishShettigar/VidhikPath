from django.shortcuts import render
from django.conf import settings
from .base_views import firebase_login_required
from ..models import User, ForumPost


# Feature views
@firebase_login_required
def dashboard(request):
    return render(request, 'dashboard.html', {
        'user': request.firebase_user,
        'firebase_uid': request.firebase_uid
    })

@firebase_login_required
def chatbot(request):
    return render(request, 'chatbot.html', {'user': request.firebase_user})

@firebase_login_required
def document_summarizer(request):
    return render(request, 'summerizer.html', {'user': request.firebase_user})

@firebase_login_required
def lawyer_connector(request):
    lawyers = User.find_lawyers()
    return render(request, 'connector.html', {
        'lawyers': lawyers,
        'user': request.firebase_user
    })

@firebase_login_required
def public_forum(request):
    """Render the forum page with existing posts"""
    try:
        posts = ForumPost.get_all_with_user_info(limit=20)
        return render(request, 'forum.html', {
            'posts': posts,
            'user': request.firebase_user
        })
    except Exception as e:
        print(f"Error in public_forum view: {e}")
        return render(request, 'forum.html', {
            'posts': [],
            'user': request.firebase_user
        })
