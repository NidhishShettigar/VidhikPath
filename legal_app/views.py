from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
import json
import os
import base64
from .models import UserProfile, ForumPost, ForumReply

# Landing page with hammer animation
def landing_page(request):
    return render(request, 'landing.html')

# Authentication views
def login_page(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            user = User.objects.get(email=email)
            user = authenticate(request, username=user.username, password=password)
            if user:
                login(request, user)
                return redirect('dashboard')
            else:
                return render(request, 'login.html', {'error': 'Invalid credentials'})
        except User.DoesNotExist:
            return render(request, 'login.html', {'error': 'User not found'})
    
    return render(request, 'login.html')

def register_page(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type')
        
        # Create user
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name
        )
        
        # Create profile
        profile = UserProfile.objects.create(
            user=user,
            is_lawyer=(user_type == 'lawyer')
        )
        
        # If lawyer, save additional info
        if user_type == 'lawyer':
            profile.lawyer_type = request.POST.get('lawyer_type', '')
            profile.experience = int(request.POST.get('experience', 0))
            profile.location = request.POST.get('location', '')
            if 'license_document' in request.FILES:
                profile.license_document = request.FILES['license_document']
            profile.save()
        
        login(request, user)
        return redirect('dashboard')
    
    return render(request, 'register.html')

# Main dashboard
@login_required
def dashboard(request):
    return render(request, 'dashboard.html')

# Feature views
@login_required
def chatbot(request):
    return render(request, 'chatbot.html')

@login_required
def document_summarizer(request):
    return render(request, 'document_summarizer.html')

@login_required
def lawyer_connector(request):
    lawyers = UserProfile.objects.filter(is_lawyer=True)
    return render(request, 'lawyer_connector.html', {'lawyers': lawyers})

@login_required
def public_forum(request):
    posts = ForumPost.objects.all().order_by('-created_at')
    return render(request, 'forum.html', {'posts': posts})

@login_required
def user_profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        profile.phone = request.POST.get('phone', '')
        profile.location = request.POST.get('location', '')
        if 'profile_photo' in request.FILES:
            profile.profile_photo = request.FILES['profile_photo']
        profile.save()
        
        # Update user info
        request.user.first_name = request.POST.get('name', '')
        request.user.save()
    
    return render(request, 'profile.html', {'profile': profile})

def logout_view(request):
    logout(request)
    return redirect('landing')

# API endpoints
@csrf_exempt
@login_required
def chat_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        message = data.get('message', '')
        language = data.get('language', 'english')
        
        # Placeholder for AI processing
        # Here you would implement:
        # 1. NLP processing (tokenization, lemmatization)
        # 2. Text embedding using text-embedding-3-large
        # 3. FAISS vector search
        # 4. RAG with legal database
        # 5. GPT-4o response generation
        
        response = f"Legal AI Response for: {message} (Language: {language})"
        
        return JsonResponse({
            'response': response,
            'language': language
        })

@csrf_exempt
@login_required
def summarize_api(request):
    if request.method == 'POST':
        if 'document' in request.FILES:
            document = request.FILES['document']
            
            # Placeholder for document processing
            # Here you would implement:
            # 1. OpenCV image cleaning
            # 2. Tesseract OCR
            # 3. Text extraction and chunking
            # 4. GPT-4o summarization
            
            summary = f"Document Summary: This document contains legal information that has been processed and summarized for easy understanding."
            
            return JsonResponse({
                'summary': summary,
                'status': 'success'
            })
        
        return JsonResponse({'error': 'No document provided'}, status=400)

@csrf_exempt
@login_required
def find_lawyers_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        location = data.get('location', '')
        lawyer_type = data.get('lawyer_type', '')
        use_current_location = data.get('use_current_location', False)
        
        lawyers = UserProfile.objects.filter(is_lawyer=True)
        
        if location:
            lawyers = lawyers.filter(location__icontains=location)
        
        if lawyer_type:
            lawyers = lawyers.filter(lawyer_type__icontains=lawyer_type)
        
        lawyers_data = []
        for lawyer in lawyers:
            lawyers_data.append({
                'name': lawyer.user.first_name,
                'type': lawyer.lawyer_type,
                'experience': lawyer.experience,
                'location': lawyer.location,
                'email': lawyer.user.email
            })
        
        return JsonResponse({'lawyers': lawyers_data})

@csrf_exempt
@login_required
def create_post_api(request):
    if request.method == 'POST':
        content = request.POST.get('content', '')
        image = request.FILES.get('image')
        
        post = ForumPost.objects.create(
            user=request.user,
            content=content,
            image=image
        )
        
        return JsonResponse({
            'id': post.id,
            'content': post.content,
            'user': post.user.first_name,
            'created_at': post.created_at.strftime('%Y-%m-%d %H:%M'),
            'likes_count': post.likes.count()
        })

@csrf_exempt
@login_required
def like_post_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        post_id = data.get('post_id')
        
        post = get_object_or_404(ForumPost, id=post_id)
        
        if request.user in post.likes.all():
            post.likes.remove(request.user)
            liked = False
        else:
            post.likes.add(request.user)
            liked = True
        
        return JsonResponse({
            'liked': liked,
            'likes_count': post.likes.count()
        })

@csrf_exempt
@login_required
def reply_post_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        post_id = data.get('post_id')
        content = data.get('content')
        
        post = get_object_or_404(ForumPost, id=post_id)
        reply = ForumReply.objects.create(
            post=post,
            user=request.user,
            content=content
        )
        
        return JsonResponse({
            'id': reply.id,
            'content': reply.content,
            'user': reply.user.first_name,
            'created_at': reply.created_at.strftime('%Y-%m-%d %H:%M')
        })
