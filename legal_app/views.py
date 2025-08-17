from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
from bson import ObjectId
import json
import os
import base64
from datetime import datetime
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
                return redirect('chatbot')
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
        
        # Create profile using PyMongo
        is_lawyer = (user_type == 'lawyer')
        phone = ''
        location = request.POST.get('location', '') if is_lawyer else ''
        lawyer_type = request.POST.get('lawyer_type', '') if is_lawyer else ''
        experience = int(request.POST.get('experience', 0)) if is_lawyer else None
        license_document = ''
        
        if is_lawyer and 'license_document' in request.FILES:
            # Handle file upload for license document
            file = request.FILES['license_document']
            file_path = default_storage.save(f'licenses/{file.name}', file)
            license_document = file_path
        
        UserProfile.create(
            username=user.username,
            is_lawyer=is_lawyer,
            phone=phone,
            location=location,
            lawyer_type=lawyer_type,
            experience=experience,
            license_document=license_document
        )
        
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
    return render(request, 'summerizer.html')

@login_required
def lawyer_connector(request):
    lawyers = list(UserProfile.collection.find({"is_lawyer": True}))
    return render(request, 'connector.html', {'lawyers': lawyers})

@login_required
def public_forum(request):
    posts = list(ForumPost.collection.find().sort("created_at", -1))
    return render(request, 'forum.html', {'posts': posts})

@login_required
def user_profile(request):
    profile = UserProfile.find_by_username(request.user.username)
    
    if not profile:
        # Create profile if it doesn't exist
        UserProfile.create(username=request.user.username)
        profile = UserProfile.find_by_username(request.user.username)
    
    if request.method == 'POST':
        phone = request.POST.get('phone', '')
        location = request.POST.get('location', '')
        profile_photo = ''
        
        if 'profile_photo' in request.FILES:
            file = request.FILES['profile_photo']
            file_path = default_storage.save(f'profiles/{file.name}', file)
            profile_photo = file_path
        
        # Update profile using PyMongo
        update_data = {
            "phone": phone,
            "location": location
        }
        if profile_photo:
            update_data["profile_photo"] = profile_photo
            
        UserProfile.collection.update_one(
            {"username": request.user.username},
            {"$set": update_data}
        )
        
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
        
        query = {"is_lawyer": True}
        
        if location:
            query["location"] = {"$regex": location, "$options": "i"}
        
        if lawyer_type:
            query["lawyer_type"] = {"$regex": lawyer_type, "$options": "i"}
        
        lawyers = list(UserProfile.collection.find(query))
        
        lawyers_data = []
        for lawyer in lawyers:
            # Get user info from Django User model
            try:
                user = User.objects.get(username=lawyer['username'])
                lawyers_data.append({
                    'name': user.first_name,
                    'type': lawyer.get('lawyer_type', ''),
                    'experience': lawyer.get('experience', 0),
                    'location': lawyer.get('location', ''),
                    'email': user.email
                })
            except User.DoesNotExist:
                continue
        
        return JsonResponse({'lawyers': lawyers_data})

@csrf_exempt
@login_required
def create_post_api(request):
    if request.method == 'POST':
        content = request.POST.get('content', '')
        image = ''
        
        if 'image' in request.FILES:
            file = request.FILES['image']
            file_path = default_storage.save(f'forum_images/{file.name}', file)
            image = file_path
        
        result = ForumPost.create(
            username=request.user.username,
            content=content,
            image=image
        )
        
        return JsonResponse({
            'id': str(result.inserted_id),
            'content': content,
            'user': request.user.first_name,
            'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
            'likes_count': 0
        })

@csrf_exempt
@login_required
def like_post_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        post_id = data.get('post_id')
        
        try:
            post = ForumPost.collection.find_one({"_id": ObjectId(post_id)})
            if not post:
                return JsonResponse({'error': 'Post not found'}, status=404)
            
            likes = post.get('likes', [])
            
            if request.user.username in likes:
                # Remove like
                ForumPost.collection.update_one(
                    {"_id": ObjectId(post_id)},
                    {"$pull": {"likes": request.user.username}}
                )
                liked = False
                likes_count = len(likes) - 1
            else:
                # Add like
                ForumPost.like(ObjectId(post_id), request.user.username)
                liked = True
                likes_count = len(likes) + 1
            
            return JsonResponse({
                'liked': liked,
                'likes_count': likes_count
            })
            
        except Exception as e:
            return JsonResponse({'error': 'Invalid post ID'}, status=400)

@csrf_exempt
@login_required
def reply_post_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        post_id = data.get('post_id')
        content = data.get('content')
        
        try:
            post = ForumPost.collection.find_one({"_id": ObjectId(post_id)})
            if not post:
                return JsonResponse({'error': 'Post not found'}, status=404)
            
            ForumReply.create(ObjectId(post_id), request.user.username, content)
            
            return JsonResponse({
                'content': content,
                'user': request.user.first_name,
                'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
            })
            
        except Exception as e:
            return JsonResponse({'error': 'Invalid post ID'}, status=400)