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
import re
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


with open("legal_app\prompts\system_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()

import google.generativeai as genai

# Configure Gemini API key (best: from Django settings or environment variable)
client = genai.configure(api_key=settings.GEMINI_API_KEY)  # Replace with your key or os.getenv


        

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
    try:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512)
        with torch.no_grad():
            outputs = model(**inputs)
        # Use [CLS] token embedding
        embedding = outputs.last_hidden_state[:, 0, :].numpy()
        return embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None


def search_faiss(query: str, top_k: int = 5):  # Increased to 5 for better context
    """Search FAISS index for top_k IPC sections"""
    try:
        query_vec = get_embedding(query)
        if query_vec is None:
            return []
        
        query_vec = query_vec.reshape(1, -1)
        distances, indices = index.search(query_vec, top_k)
        
        results = []
        seen_sections = set()  # Avoid duplicate sections
        
        for idx, distance in zip(indices[0], distances[0]):
            if idx != -1 and idx < len(id_mapping):
                doc_id = id_mapping[idx]
                doc = ipc_collection.find_one({"_id": ObjectId(doc_id)})
                
                if doc and doc.get("Section") not in seen_sections:
                    seen_sections.add(doc.get("Section"))
                    results.append({
                        "Section": doc.get("Section"),
                        "section_title": doc.get("section_title"),
                        "section_desc": doc.get("section_desc"),
                        "relevance_score": float(distance)  # Include similarity score
                    })
        
        return results
    except Exception as e:
        print(f"Error in FAISS search: {e}")
        return []
    
    
LEGAL_KEYWORDS = [
    "ipc", "section", "act", "law", "rights", "punishment", "bail", "crime", 
    "offence", "offense", "arrest", "case", "legal", "court", "judge", 
    "criminal", "civil", "constitution", "advocate", "lawyer", "police",
    "complaint", "fir", "chargesheet", "evidence", "witness", "trial",
    "sentence", "fine", "imprisonment", "appeal", "petition", "writ"
]

def is_legal_query(text: str) -> bool:
    """Enhanced legal query detection"""
    text_lower = text.lower()
    
    # Check for legal keywords
    keyword_matches = sum(1 for word in LEGAL_KEYWORDS if word in text_lower)
    
    # Check for legal patterns
    legal_patterns = [
        r'\bipc\s+\d+', r'section\s+\d+', r'article\s+\d+',
        r'criminal\s+law', r'civil\s+law', r'legal\s+advice',
        r'court\s+case', r'file\s+case', r'legal\s+action'
    ]
    
    pattern_matches = sum(1 for pattern in legal_patterns if re.search(pattern, text_lower))
    
    # Consider it legal if multiple keywords or patterns match
    return keyword_matches >= 2 or pattern_matches >= 1 or keyword_matches >= 1 and len(text.split()) <= 5

def preprocess_query(message: str) -> str:
    """Enhanced query preprocessing"""
    try:
        # Basic cleaning
        message = re.sub(r'[^\w\s]', ' ', message.lower())
        message = ' '.join(message.split())
        
        # NLP processing
        doc = nlp(message)
        
        # Extract meaningful tokens (avoid stopwords, keep legal terms)
        legal_stopwords = {'what', 'how', 'when', 'where', 'why', 'can', 'should', 'would'}
        processed_tokens = []
        
        for token in doc:
            if (token.pos_ in ['NOUN', 'VERB', 'ADJ'] or 
                token.text in LEGAL_KEYWORDS or
                token.ent_type_ in ['LAW', 'ORG', 'PERSON']):
                processed_tokens.append(token.lemma_)
        
        return ' '.join(processed_tokens) if processed_tokens else message
    
    except Exception as e:
        print(f"Error in preprocessing: {e}")
        return message.lower()

def format_rag_context(ipc_results: list) -> str:
    """Format retrieved context for better prompt structure"""
    if not ipc_results:
        return "No specific IPC sections found directly relevant to this query."
    
    context_parts = []
    for i, result in enumerate(ipc_results, 1):
        if isinstance(result, dict):
            section_info = (
                f"**IPC Section {result.get('Section', 'N/A')}** - {result.get('section_title', 'No title')}\n"
                f"Description: {result.get('section_desc', 'No description available')}\n"
            )
            context_parts.append(section_info)
    
    return "\n".join(context_parts)


@csrf_exempt
@login_required
def chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '').strip()
            language = data.get('language', 'english')

            if not message:
                return JsonResponse({
                    "response": "Please provide a legal question for assistance.",
                    "context": [],
                    "language": language
                })

            # Enhanced legal query detection
            if not is_legal_query(message):
                return JsonResponse({
                    "response": (
                        "I specialize in Indian legal matters and criminal law. "
                        f"Your query '{message}' doesn't appear to be law-related. "
                        "Please ask about IPC sections, criminal procedures, legal rights, "
                        "or other Indian legal topics."
                    ),
                    "context": [],
                    "language": language
                })

            # Enhanced preprocessing
            processed_message = preprocess_query(message)

            # Retrieve relevant IPC sections
            ipc_results = search_faiss(processed_message, top_k=5)

            # Format context for better prompt
            rag_context = format_rag_context(ipc_results)

            # Create structured prompt
            user_prompt = f"""
Legal Query: {message}

Relevant Legal Context:
{rag_context}

Please provide a comprehensive legal analysis addressing this query. Focus on:
1. Identifying the specific legal issues involved
2. Explaining relevant IPC sections and legal provisions
3. Analyzing how the law applies to this situation
4. Providing practical guidance and next steps
5. Including appropriate legal disclaimers

Ensure your response is well-structured, professional, and educational in nature.
"""

            full_prompt = system_prompt + "\n\n" + user_prompt

            # Call Gemini API with improved configuration
            gemini_model = genai.GenerativeModel(
                "models/gemini-1.5-flash",
                generation_config={
                    "temperature": 0.1,  # Lower for more consistent legal responses
                    "top_p": 0.85,
                    "top_k": 40,
                    "max_output_tokens": 2048,  # Increased for detailed responses
                    "stop_sequences": ["---END---"]
                }
            )
            
            response = gemini_model.generate_content(full_prompt)
            gemini_response = response.text

            # Add standard legal disclaimer if not present
            if "disclaimer" not in gemini_response.lower():
                gemini_response += (
                    "\n\n**Important Legal Disclaimer**: This information is provided for "
                    "educational purposes only and does not constitute legal advice. "
                    "Laws and their interpretations can vary based on specific circumstances. "
                    "For matters involving legal proceedings or specific legal advice, "
                    "please consult with a qualified legal professional."
                )

            return JsonResponse({
                'response': gemini_response,
                'context': ipc_results,
                'language': language,
                'query_processed': processed_message,
                'sections_found': len(ipc_results)
            })

        except json.JSONDecodeError:
            return JsonResponse({
                "error": "Invalid JSON format",
                "response": "Please ensure your request is properly formatted."
            }, status=400)
        
        except Exception as e:
            print(f"Error in chat_api: {e}")
            return JsonResponse({
                "error": "Internal server error",
                "response": "I'm experiencing technical difficulties. Please try again."
            }, status=500)

    return JsonResponse({"error": "Only POST requests allowed"}, status=405)

#document summerizer

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