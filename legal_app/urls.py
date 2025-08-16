from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('login/', views.login_page, name='login'),
    path('register/', views.register_page, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('document-summarizer/', views.document_summarizer, name='summerizer'),
    path('lawyer-connector/', views.lawyer_connector, name='connector'),
    path('forum/', views.public_forum, name='forum'),
    path('profile/', views.user_profile, name='profile'),
    path('logout/', views.logout_view, name='logout'),
    
    # API endpoints
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/summarize/', views.summarize_api, name='summarize_api'),
    path('api/find-lawyers/', views.find_lawyers_api, name='find_lawyers_api'),
    path('api/forum/post/', views.create_post_api, name='create_post_api'),
    path('api/forum/like/', views.like_post_api, name='like_post_api'),
    path('api/forum/reply/', views.reply_post_api, name='reply_post_api'),
]
