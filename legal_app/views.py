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
# from google.genai.types import HttpOptions
import tempfile
import cv2
import pytesseract
import os
import cv2
import tempfile
import pdfplumber
from pdf2image import convert_from_path
import google.generativeai as genai
import re



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
        phone = request.POST.get('phone') or profile.get("phone", "")
        location = request.POST.get('location') or profile.get("location", "")
        profile_photo = profile.get("profile_photo", "")
        
        if 'profile_photo' in request.FILES:
            file = request.FILES['profile_photo']
            file_path = default_storage.save(f'profiles/{file.name}', file)
            profile_photo = file_path
        
        # Update profile using PyMongo
        update_data = {
            "phone": phone,
            "location": location,
            "profile_photo": profile_photo
        }
        
        UserProfile.collection.update_one(
            {"username": request.user.username},
            {"$set": update_data}
        )
        
        # Update user info (Django User model)
        request.user.first_name = request.POST.get('name') or request.user.first_name
        request.user.save()

        # 🔑 Reload the updated profile after update
        profile = UserProfile.find_by_username(request.user.username)
    
    return render(request, 'profile.html', {'profile': profile})

def logout_view(request):
    logout(request)
    return redirect('login')


with open("legal_app\prompts\system_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()

# Load keywords from file once at startup
with open("legal_app\prompts\legal_keywords.txt", "r", encoding="utf-8") as f:
    LEGAL_KEYWORDS = [line.strip().lower() for line in f if line.strip()]
import google.generativeai as genai

# Configure Gemini API key (best: from Django settings or environment variable)
client = genai.configure(api_key=settings.GEMINI_API_KEY)  # Replace with your key or os.getenv


        

# Load MongoDB collection
ipc_collection = db["ipc"]

# Load LegalBERT + SpaCy once at server start
tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
bert_model = AutoModel.from_pretrained("nlpaueb/legal-bert-base-uncased")
nlp = spacy.load("en_core_web_lg")

# Load FAISS index + mapping
index = faiss.read_index("ipc_index.faiss")
with open("ipc_id_mapping.json", "r", encoding="utf-8") as f:
    id_mapping = json.load(f)     # List of MongoDB IDs (as strings)

def get_embedding(text: str):
    """Generate LegalBERT embeddings for text"""
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        outputs = bert_model(**inputs)
    # Use [CLS] token embedding
    embedding = outputs.last_hidden_state[:, 0, :].numpy()
    return embedding

def search_faiss(query: str, top_k: int = 20):
    query_vec = get_embedding(query).reshape(1, -1)
    distances, indices = index.search(query_vec, top_k)
    print("Indices:", indices)
    results = []
    for idx in indices[0]:
        print("Checking index:", idx)
        if idx != -1 and idx < len(id_mapping):
            doc_id = id_mapping[idx]
            print("Mapped doc_id:", doc_id)
            doc = ipc_collection.find_one({"_id": ObjectId(doc_id)})
            if doc:
                results.append({
                    "Section": doc.get("Section"),
                    "section_title": doc.get("section_title"),
                    "section_desc": doc.get("section_desc"),
                })
            else:
                print("⚠️ No document found for:", doc_id)
    print("Final Results:", results)
    return results


LEGAL_KEYWORDS = [
    "ipc", "section", "act", "law", "rights", "punishment", "bail", "crime", 
    "offence", "offense", "arrest", "case", "legal", "court", "judge", 
    "criminal", "civil", "constitution", "advocate", "lawyer", "police",
    "complaint", "fir", "chargesheet", "evidence", "witness", "trial",
    "sentence", "fine", "imprisonment", "appeal", "petition", "writ","commite"
]

def is_legal_query(text: str) -> bool:
    """Check if the query looks legal-related."""
    text_lower = text.lower()
    return any(word in text_lower for word in LEGAL_KEYWORDS)


@csrf_exempt
@login_required
def chat_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        language = data.get('language', 'english')

        # 👋 Handle small-talk / non-legal queries
        if not is_legal_query(message):
            return JsonResponse({
                "response": f"I’m here to assist with Indian law. Your message ('{message}') does not seem like a legal query.",
                "context": [],
                "language": language
            })

        # 1. NLP preprocessing
        doc = nlp(message.lower())
        processed_message = " ".join([token.lemma_ for token in doc])

        # 2 & 3. Embed & Search FAISS
        ipc_results = search_faiss(processed_message, top_k=20)

        # 4. Prepare RAG context
        rag_context = "\n".join([
            f"Section {sec['Section']} ({sec['section_title']}): {sec['section_desc']}"
            for sec in ipc_results if isinstance(sec, dict)
        ])


        user_input = (
            f"User Question: {message}\n\n"
            f"Relevant IPC Context:\n{rag_context if rag_context else 'No relevant IPC context found.'}\n\n"
            f"Answer in detail with reference to Indian law."
        )

        gemini_prompt = system_prompt + "\n\nUser Query: " + user_input

        # 6. Call Gemini API
        gemini_model = genai.GenerativeModel(
            "models/gemini-1.5-flash",
            generation_config={
                "temperature": 0.2,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 1024
            }
        )
        response = gemini_model.generate_content(gemini_prompt)

        gemini_response = response.text  

        # 7. Return JSON response
        return JsonResponse({
            'response': gemini_response,
            'context': ipc_results,
            'language': language
        })


#document summerizer

#✅ Initialize Gemini model once
genai.configure(api_key=settings.GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")


# ---------- OCR & Text Extraction ------

def clean_image(path):
    """Clean image for OCR (thresholding)."""
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    _, thresh = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cleaned_path = path.replace(".png", "_cleaned.png")
    cv2.imwrite(cleaned_path, thresh)
    return cleaned_path

def extract_text_from_pdf(path):
    """Extract text if PDF has embedded text."""
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

def ocr_pdf(path):
    """OCR scanned PDF (convert each page to image)."""
    pages = convert_from_path(path, dpi=300)
    text = ""
    for i, page in enumerate(pages):
        img_path = f"{path}_page_{i}.png"
        page.save(img_path, "PNG")
        cleaned = clean_image(img_path)
        text += pytesseract.image_to_string(cleaned) + "\n"
        os.remove(img_path)
        os.remove(cleaned)
    return text.strip()

def ocr_image(path):
    """OCR on single uploaded image."""
    cleaned = clean_image(path)
    text = pytesseract.image_to_string(cleaned)
    os.remove(cleaned)
    return text.strip()

# ---------- Text Processing ----------

def chunk_text(text, max_len=3000):
    """Split text into chunks by sentence boundaries."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current = [], ""
    for sentence in sentences:
        if len(current) + len(sentence) < max_len:
            current += " " + sentence
        else:
            chunks.append(current.strip())
            current = sentence
    if current:
        chunks.append(current.strip())
    return chunks

def summarize_chunk(chunk):
    """Summarize one chunk using Gemini."""
    prompt = f"""
    You are a legal assistant. Summarize the following legal document text.
    
    Provide output in two parts:
    1. **Plain summary** – explain clearly in simple words.
    2. **Key points** – bullet points highlighting important laws, rights, duties, or penalties.

    Text:
    {chunk}
    """
    response = gemini_model.generate_content(prompt)
    return response.text.strip()

# ---------- API View ----------

@csrf_exempt
@login_required
def summarize_api(request):
    if request.method == "POST" and "document" in request.FILES:
        document = request.FILES["document"]

        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=document.name) as tmp_file:
            for chunk in document.chunks():
                tmp_file.write(chunk)
            temp_path = tmp_file.name

        raw_text = ""
        ext = os.path.splitext(document.name)[1].lower()

        try:
            # 🔹 PDF
            if ext == ".pdf":
                raw_text = extract_text_from_pdf(temp_path)
                if not raw_text:  # fallback if scanned PDF
                    raw_text = ocr_pdf(temp_path)

            # 🔹 Images
            elif ext in [".png", ".jpg", ".jpeg"]:
                raw_text = ocr_image(temp_path)

            else:
                return JsonResponse(
                    {"error": f"Unsupported file type: {ext}"}, status=400
                )

            if not raw_text.strip():
                return JsonResponse(
                    {"error": "No readable text found in document"}, status=400
                )

            # Chunk + Summarize
            chunks = chunk_text(raw_text)
            summaries = [summarize_chunk(chunk) for chunk in chunks]
            final_summary = "\n\n---\n\n".join(summaries)

            # (Optional) Store in DB
            # db["summaries"].insert_one({
            #     "user_id": request.user.id,
            #     "filename": document.name,
            #     "summary": final_summary,
            #     "created_at": datetime.utcnow()
            # })

            return JsonResponse(
                {
                    "status": "success",
                    "summary": final_summary,
                    "chunks_processed": len(chunks),
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

        finally:
            # Cleanup temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)

    return JsonResponse({"error": "No document provided"}, status=400)


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


#forum
# Forum-related views only - Add these to your existing views.py

@login_required
def public_forum(request):
    """Render the forum page with existing posts"""
    try:
        posts_data = list(ForumPost.collection.find().sort("created_at", -1).limit(20))
        
        # Convert MongoDB data to template-friendly format
        posts = []
        for post_data in posts_data:
            # Get user's real name from Django User model
            try:
                user = User.objects.get(username=post_data.get('username', ''))
                display_name = user.first_name or user.username
            except User.DoesNotExist:
                display_name = post_data.get('username', 'Anonymous')
            
            # Format replies
            formatted_replies = []
            for reply in post_data.get('replies', []):
                try:
                    reply_user = User.objects.get(username=reply.get('username', ''))
                    reply_display_name = reply_user.first_name or reply_user.username
                except User.DoesNotExist:
                    reply_display_name = reply.get('username', 'Anonymous')
                
                formatted_replies.append({
                    'username': reply_display_name,
                    'content': reply.get('content', ''),
                    'created_at': reply.get('created_at', datetime.utcnow())
                })
            
            # Check if current user liked this post
            user_likes = post_data.get('likes', [])
            
            post = {
                'id': str(post_data['_id']),
                'username': post_data.get('username', 'Anonymous'),
                'first_name': display_name,
                'content': post_data.get('content', ''),
                'image': post_data.get('image', ''),
                'created_at': post_data.get('created_at', datetime.utcnow()),
                'likes': user_likes,  # List of usernames who liked
                'replies': formatted_replies
            }
            posts.append(post)
        
        return render(request, 'forum.html', {'posts': posts})
    
    except Exception as e:
        print(f"Error in public_forum view: {e}")
        return render(request, 'forum.html', {'posts': []})


@csrf_exempt
@login_required
def create_post_api(request):
    """API endpoint to create a new forum post"""
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        
        if not content:
            return JsonResponse({'error': 'Content is required'}, status=400)
        
        # Validate content length
        if len(content) > 5000:
            return JsonResponse({'error': 'Content too long. Maximum 5000 characters allowed.'}, status=400)
        
        image_path = ''
        if 'image' in request.FILES:
            file = request.FILES['image']
            
            # Validate file type
            if not file.content_type.startswith('image/'):
                return JsonResponse({'error': 'Invalid file type. Please upload an image.'}, status=400)
            
            # Validate file size (max 5MB)
            if file.size > 5 * 1024 * 1024:
                return JsonResponse({'error': 'File too large. Maximum 5MB allowed.'}, status=400)
            
            # Save the file
            try:
                file_path = default_storage.save(f'forum_images/{file.name}', file)
                image_path = file_path
            except Exception as e:
                return JsonResponse({'error': f'Error saving image: {str(e)}'}, status=500)
        
        try:
            # Create the post
            result = ForumPost.create(
                username=request.user.username,
                content=content,
                image=image_path
            )
            
            # Get display name
            display_name = request.user.first_name or request.user.username
            
            return JsonResponse({
                'id': str(result.inserted_id),
                'content': content,
                'user': display_name,
                'username': request.user.username,
                'created_at': datetime.utcnow().strftime('%b %d, %Y %H:%M'),
                'likes_count': 0,
                'image': image_path,
                'status': 'success'
            })
            
        except Exception as e:
            print(f"Error creating post: {e}")
            return JsonResponse({'error': f'Error creating post: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
@login_required
def like_post_api(request):
    """API endpoint to like/unlike a forum post"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            post_id = data.get('post_id')
            
            if not post_id:
                return JsonResponse({'error': 'Post ID is required'}, status=400)
            
            # Validate and convert ObjectId
            try:
                post_object_id = ObjectId(post_id)
            except Exception:
                return JsonResponse({'error': 'Invalid post ID format'}, status=400)
            
            # Find the post
            post = ForumPost.get_by_id(post_object_id)
            if not post:
                return JsonResponse({'error': 'Post not found'}, status=404)
            
            likes = post.get('likes', [])
            username = request.user.username
            
            if username in likes:
                # Remove like (unlike)
                result = ForumPost.unlike(post_object_id, username)
                if result and result.modified_count > 0:
                    liked = False
                    likes_count = len(likes) - 1
                else:
                    return JsonResponse({'error': 'Failed to remove like'}, status=500)
            else:
                # Add like
                result = ForumPost.like(post_object_id, username)
                if result and result.modified_count > 0:
                    liked = True
                    likes_count = len(likes) + 1
                else:
                    return JsonResponse({'error': 'Failed to add like'}, status=500)
            
            return JsonResponse({
                'liked': liked,
                'likes_count': likes_count,
                'status': 'success'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            print(f"Error in like_post_api: {e}")
            return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
@login_required
def reply_post_api(request):
    """API endpoint to reply to a forum post"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            post_id = data.get('post_id')
            content = data.get('content', '').strip()
            
            if not post_id:
                return JsonResponse({'error': 'Post ID is required'}, status=400)
            
            if not content:
                return JsonResponse({'error': 'Reply content is required'}, status=400)
            
            # Validate content length
            if len(content) > 1000:
                return JsonResponse({'error': 'Reply too long. Maximum 1000 characters allowed.'}, status=400)
            
            # Validate and convert ObjectId
            try:
                post_object_id = ObjectId(post_id)
            except Exception:
                return JsonResponse({'error': 'Invalid post ID format'}, status=400)
            
            # Check if post exists
            post = ForumPost.get_by_id(post_object_id)
            if not post:
                return JsonResponse({'error': 'Post not found'}, status=404)
            
            # Create the reply
            result = ForumReply.create(post_object_id, request.user.username, content)
            
            if result and result.modified_count > 0:
                # Get display name
                display_name = request.user.first_name or request.user.username
                
                return JsonResponse({
                    'content': content,
                    'user': display_name,
                    'username': request.user.username,
                    'created_at': datetime.utcnow().strftime('%b %d, %H:%M'),
                    'status': 'success'
                })
            else:
                return JsonResponse({'error': 'Failed to create reply'}, status=500)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            print(f"Error in reply_post_api: {e}")
            return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


# Additional utility view for forum stats (optional)
@login_required
def forum_stats_api(request):
    """Get forum statistics"""
    try:
        total_posts = ForumPost.collection.count_documents({})
        
        # Get total replies count across all posts
        pipeline = [
            {"$project": {"reply_count": {"$size": "$replies"}}},
            {"$group": {"_id": None, "total": {"$sum": "$reply_count"}}}
        ]
        result = list(ForumPost.collection.aggregate(pipeline))
        total_replies = result[0]['total'] if result else 0
        
        return JsonResponse({
            'total_posts': total_posts,
            'total_replies': total_replies,
            'status': 'success'
        })
        
    except Exception as e:
        print(f"Error in forum_stats_api: {e}")
        return JsonResponse({'error': 'Failed to get forum stats'}, status=500)