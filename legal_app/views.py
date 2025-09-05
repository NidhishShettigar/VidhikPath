from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings

from bson import ObjectId
from datetime import datetime
import json
import os
import base64
import re
import tempfile

import cv2
import pdfplumber
import pytesseract
from pdf2image import convert_from_path

import faiss
import numpy as np
import torch
import spacy
import pickle
import functools

from transformers import AutoTokenizer, AutoModel
from openai import OpenAI
import google.generativeai as genai

from .firebase_utils import FirebaseAuth
from .db_connection import db
from .models import (
    User,
    ForumPost, 
    ForumReply, 
    FirebaseTokenManager,
    UserSession   # keep if you still track sessions in Mongo
)


client = OpenAI(api_key=settings.OPENAI_API_KEY)


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


@firebase_login_required
def update_profile(request):
    if request.method == "POST":
        try:
            firebase_uid = request.session.get("firebase_uid")
            if not firebase_uid:
                return JsonResponse({"success": False, "error": "User not authenticated"})

            name = request.POST.get("name")
            phone = request.POST.get("phone")
            location = request.POST.get("location")
            profile_photo = request.FILES.get("profile_photo")

            update_data = {
                "name": name,
                "phone": phone,
                "location": location
            }

            # Handle photo upload
            if profile_photo:
                photo_path = os.path.join("media/profile_photos", profile_photo.name)
                with open(photo_path, "wb+") as destination:
                    for chunk in profile_photo.chunks():
                        destination.write(chunk)
                update_data["profile_photo"] = photo_path

            # Update MongoDB
            db.users.update_one(
                {"firebase_uid": firebase_uid},
                {"$set": update_data}
            )

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid request"})

# Landing page
def landing_page(request):
    return render(request, 'landing.html')


#login
def login_page(request):
    if request.session.get('firebase_uid'):  # instead of firebase_token
        return redirect('chatbot')
    return render(request, 'login.html')



# registration
def register_page(request):
    # If already logged in, redirect to dashboard
    if request.session.get('firebase_token'):
        return redirect('login')
    
    return render(request, 'register.html')

@csrf_exempt
def firebase_verify_token(request):
    """Verify Firebase ID token and create/login user"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            id_token = data.get('idToken')
            user_data = data.get('userData', {})  # Additional user data from registration
            
            if not id_token:
                return JsonResponse({'success': False, 'error': 'No token provided'})
            
            # Verify Firebase token
            token_result = FirebaseTokenManager.verify_token(id_token)
            
            if not token_result['success']:
                return JsonResponse({'success': False, 'error': 'Invalid token'})
            
            firebase_uid = token_result['firebase_uid']
            email = token_result['email']
            
            # Check if user exists in MongoDB
            user = User.find_by_firebase_uid(firebase_uid)
            
            if not user:
                # Create new user if doesn't exist
                user_creation_data = {
                    'name': user_data.get('name', token_result.get('name', '')),
                    'user_type': user_data.get('user_type', 'user'),
                    'phone': user_data.get('phone', ''),
                    'location': user_data.get('location', ''),
                }
                
                # Add lawyer-specific fields if user_type is lawyer
                if user_data.get('user_type') == 'lawyer':
                    user_creation_data.update({
                        'lawyer_type': user_data.get('lawyer_type', ''),
                        'experience': int(user_data.get('experience', 0)),
                        'license_number': user_data.get('license_number', ''),
                        'languages_spoken': user_data.get('languages_spoken', []),
                        'education': user_data.get('education', ''),
                    })
                
                User.create(firebase_uid, email, **user_creation_data)
                user = User.find_by_firebase_uid(firebase_uid)
            
            # Store session data
            request.session['firebase_token'] = id_token
            request.session['firebase_uid'] = firebase_uid
            request.session['user_email'] = email
            
            # Update/create session in MongoDB
            refresh_token = data.get('refreshToken', '')
            UserSession.update_session(firebase_uid, id_token, refresh_token)
            
            return JsonResponse({
                'success': True,
                'user': {
                    'firebase_uid': firebase_uid,
                    'email': email,
                    'name': user.get('name', ''),
                    'user_type': user.get('user_type', 'user'),
                    'is_lawyer': user.get('user_type') == 'lawyer'
                },
                'redirect': '/dashboard/'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
        except Exception as e:
            print(f"Error in firebase_verify_token: {e}")
            return JsonResponse({'success': False, 'error': f'Server error: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@csrf_exempt
def firebase_password_reset(request):
    """Send password reset email via Firebase"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            
            result = FirebaseAuth.send_password_reset_email(email)
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


# Feature views
@firebase_login_required
def dashboard(request):
    return render(request, 'chatbot.html', {
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


@firebase_login_required
def user_profile(request):
    user = request.firebase_user
    
    if request.method == 'POST':
        # Handle profile update
        update_data = {
            'name': request.POST.get('name', user.get('name', '')),
            'phone': request.POST.get('phone', user.get('phone', '')),
            'location': request.POST.get('location', user.get('location', ''))
        }
        
        # Handle profile photo upload
        if 'profile_photo' in request.FILES:
            file = request.FILES['profile_photo']
            file_path = default_storage.save(f'profiles/{file.name}', file)
            update_data['profile_photo'] = file_path
        
        # Update lawyer-specific fields if user is a lawyer
        if user.get('user_type') == 'lawyer':
            update_data.update({
                'lawyer_type': request.POST.get('lawyer_type', user.get('lawyer_type', '')),
                'experience': int(request.POST.get('experience', user.get('experience', 0))),
                'license_number': request.POST.get('license_number', user.get('license_number', '')),
                'education': request.POST.get('education', user.get('education', '')),
            })
            # Handle languages (assuming it's a comma-separated string)
            languages_str = request.POST.get('languages_spoken', '')
            if languages_str:
                update_data['languages_spoken'] = [l.strip() for l in languages_str.split(',')]
        
        # Update in MongoDB
        User.update_profile(request.firebase_uid, update_data)
        
        # Refresh user data
        request.firebase_user = User.find_by_firebase_uid(request.firebase_uid)
    
    return render(request, 'profile.html', {
        'user': request.firebase_user
    })


def logout_view(request):
    """Logout user by clearing session"""
    firebase_uid = request.session.get('firebase_uid')
    
    # Invalidate session in MongoDB
    if firebase_uid:
        UserSession.invalidate_session(firebase_uid)
    
    # Clear Django session
    request.session.flush()
    
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
@firebase_login_required
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
@firebase_login_required  
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
@firebase_login_required
def find_lawyers_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            location = data.get('location', '')
            lawyer_type = data.get('lawyer_type', '')
            specialization = data.get('specialization', '')
            
            lawyers = User.find_lawyers(location, lawyer_type, specialization)
            
            lawyers_data = []
            for lawyer in lawyers:
                lawyers_data.append({
                    'firebase_uid': lawyer['firebase_uid'],
                    'name': lawyer.get('name', ''),
                    'lawyer_type': lawyer.get('lawyer_type', ''),
                    'experience': lawyer.get('experience', 0),
                    'location': lawyer.get('location', ''),
                    'email': lawyer.get('email', ''),
                    'languages_spoken': lawyer.get('languages_spoken', []),
                    'verified': lawyer.get('verified', False),
                    'rating': lawyer.get('rating', 0.0)
                })
            
            return JsonResponse({'lawyers': lawyers_data})
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
@firebase_login_required
def create_post_api(request):
    """API endpoint to create a new forum post"""
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        
        if not content:
            return JsonResponse({'error': 'Content is required'}, status=400)
        
        if len(content) > 5000:
            return JsonResponse({'error': 'Content too long. Maximum 5000 characters allowed.'}, status=400)
        
        image_path = ''
        if 'image' in request.FILES:
            file = request.FILES['image']
            
            if not file.content_type.startswith('image/'):
                return JsonResponse({'error': 'Invalid file type. Please upload an image.'}, status=400)
            
            if file.size > 5 * 1024 * 1024:
                return JsonResponse({'error': 'File too large. Maximum 5MB allowed.'}, status=400)
            
            try:
                file_path = default_storage.save(f'forum_images/{file.name}', file)
                image_path = file_path
            except Exception as e:
                return JsonResponse({'error': f'Error saving image: {str(e)}'}, status=500)
        
        try:
            result = ForumPost.create(
                firebase_uid=request.firebase_uid,
                content=content,
                image=image_path
            )
            
            return JsonResponse({
                'id': str(result.inserted_id),
                'content': content,
                'user': request.firebase_user.get('name', 'Unknown User'),
                'firebase_uid': request.firebase_uid,
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
@firebase_login_required
def like_post_api(request):
    """API endpoint to like/unlike a forum post"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            post_id = data.get('post_id')
            
            if not post_id:
                return JsonResponse({'error': 'Post ID is required'}, status=400)
            
            try:
                post_object_id = ObjectId(post_id)
            except Exception:
                return JsonResponse({'error': 'Invalid post ID format'}, status=400)
            
            post = ForumPost.get_by_id(post_object_id)
            if not post:
                return JsonResponse({'error': 'Post not found'}, status=404)
            
            likes = post.get('likes', [])
            firebase_uid = request.firebase_uid
            
            if firebase_uid in likes:
                result = ForumPost.unlike(post_object_id, firebase_uid)
                if result and result.modified_count > 0:
                    liked = False
                    likes_count = len(likes) - 1
                else:
                    return JsonResponse({'error': 'Failed to remove like'}, status=500)
            else:
                result = ForumPost.like(post_object_id, firebase_uid)
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
@firebase_login_required
def reply_post_api(request):
    """API endpoint to reply to a forum post"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            post_id = data.get('post_id')
            content = data.get('content', '').strip()
            
            if not post_id or not content:
                return JsonResponse({'error': 'Post ID and content are required'}, status=400)
            
            if len(content) > 1000:
                return JsonResponse({'error': 'Reply too long. Maximum 1000 characters allowed.'}, status=400)
            
            try:
                post_object_id = ObjectId(post_id)
            except Exception:
                return JsonResponse({'error': 'Invalid post ID format'}, status=400)
            
            post = ForumPost.get_by_id(post_object_id)
            if not post:
                return JsonResponse({'error': 'Post not found'}, status=404)
            
            result = ForumReply.create(post_object_id, request.firebase_uid, content)
            
            if result and result.modified_count > 0:
                return JsonResponse({
                    'content': content,
                    'user': request.firebase_user.get('name', 'Unknown User'),
                    'firebase_uid': request.firebase_uid,
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
