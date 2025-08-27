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
from .db_connection import db
import os
import base64
from datetime import datetime
from .models import UserProfile, ForumPost, ForumReply
import faiss
import numpy as np
from transformers import AutoTokenizer, AutoModel
from openai import OpenAI
import torch
import spacy
import pickle
import os
# import google.generativeai as genai
# from google.genai.types import HttpOptions
import tempfile
import cv2
import pytesseract

client = OpenAI(api_key=settings.OPENAI_API_KEY)


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



# Load MongoDB collection
ipc_collection = db["ipc"]

# Load LegalBERT + SpaCy once at server start
tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
model = AutoModel.from_pretrained("nlpaueb/legal-bert-base-uncased")
nlp = spacy.load("en_core_web_lg")

# Load FAISS index + mapping
index = faiss.read_index("ipc_index.faiss")
with open("ipc_id_mapping.json", "r", encoding="utf-8") as f:
    id_mapping = json.load(f)     # List of MongoDB IDs (as strings)

def get_embedding(text: str):
    """Generate LegalBERT embeddings for text"""
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    # Use [CLS] token embedding
    embedding = outputs.last_hidden_state[:, 0, :].numpy()
    return embedding

def search_faiss(query: str, top_k: int = 3):
    """Search FAISS index for top_k IPC sections"""
    query_vec = get_embedding(query).reshape(1, -1)
    distances, indices = index.search(query_vec, top_k)
    results = []
    for idx in indices[0]:
        if idx != -1 and idx < len(id_mapping):  # valid index
            doc_id = id_mapping[idx]
            doc = ipc_collection.find_one({"_id": ObjectId(doc_id)})
            if doc:
                results.append({
                    "Section": doc.get("Section"),
                    "section_title": doc.get("section_title"),
                    "section_desc": doc.get("section_desc"),
                })
    return results


@csrf_exempt
@login_required
def chat_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        message = data.get('message', '')
        language = data.get('language', 'english')

        # 1. NLP preprocessing
        doc = nlp(message.lower())
        processed_message = " ".join([token.lemma_ for token in doc])

        # 2 & 3. Embed & Search FAISS
        ipc_results = search_faiss(processed_message, top_k=3)

        # 4. Prepare RAG context
        rag_context = "\n".join([
            f"Section {sec['Section']} ({sec['section_title']}): {sec['section_desc']}"
            for sec in ipc_results if isinstance(sec, dict)
        ])

        # 5. Prepare GPT prompt with context
        gpt_prompt = (
            f"User Question: {message}\n\n"
            f"Relevant IPC Context:\n{rag_context}\n\n"
            f"Answer in detail with reference to the context."
        )

        # 6. Call GPT-4o chat API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert legal assistant providing answers based on the Indian Penal Code."},
                {"role": "user", "content": gpt_prompt}
            ],
            max_tokens=1000,
            temperature=0.2
        )

        gpt_response = response.choices[0].message.content

        # 7. Return JSON response
        return JsonResponse({
            'response': gpt_response,
            'context': ipc_results,
            'language': language
        })

        



def get_legalbert_embedding(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state[:, 0, :].cpu().numpy().flatten()


def clean_image(path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    _, thresh = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cleaned_path = path.replace(".pdf", "_cleaned.png")
    cv2.imwrite(cleaned_path, thresh)
    return cleaned_path


def extract_text(image_path):
    return pytesseract.image_to_string(image_path)


def chunk_text(text, max_len=1000):
    return [text[i:i + max_len] for i in range(0, len(text), max_len)]


def summarize_chunk(chunk):
    prompt = f"Summarize the legal text below:\n\n{chunk}"
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a legal document summarizer."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.2
    )
    return response.choices[0].message.content


@csrf_exempt
@login_required
def summarize_api(request):
    if request.method == 'POST' and 'document' in request.FILES:
        document = request.FILES['document']

        # Write uploaded file to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            for chunk in document.chunks():
                tmp_file.write(chunk)
            temp_path = tmp_file.name

        # Convert PDF page(s) to images if needed here (not included)
        # For demo assume uploaded file is image or convert externally

        # Clean image for better OCR
        cleaned_path = clean_image(temp_path)

        # Extract text via OCR
        raw_text = extract_text(cleaned_path)

        # Chunk the text for summarization
        chunks = chunk_text(raw_text)

        # Summarize each chunk through GPT-4o API
        summaries = [summarize_chunk(chunk) for chunk in chunks]

        # Combine summaries into final summary
        final_summary = "\n\n".join(summaries)

        return JsonResponse({'summary': final_summary, 'status': 'success'})

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