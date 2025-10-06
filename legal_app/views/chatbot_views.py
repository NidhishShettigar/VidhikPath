from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from bson import ObjectId
from ..db_connection import db
from .base_views import firebase_login_required
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import google.generativeai as genai
import json
import logging

logger = logging.getLogger(__name__)

# Load system prompt
with open("legal_app/prompts/system_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()

# Load keywords from file once at startup
with open("legal_app/prompts/legal_keywords.txt", "r", encoding="utf-8") as f:
    LEGAL_KEYWORDS = set(line.strip().lower() for line in f if line.strip())

# Configure Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)

# Load MongoDB collection
bns_collection = db["bns"]

# Load efficient embedding model (matches indexing model)
try:
    embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    embedding_model.max_seq_length = 256
    logger.info("Embedding model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load embedding model: {e}")
    embedding_model = None

# Load FAISS index + mapping
try:
    index = faiss.read_index("bns_index.faiss")
    with open("bns_id_mapping.json", "r", encoding="utf-8") as f:
        id_mapping = json.load(f)
    logger.info(f"FAISS index loaded: {index.ntotal} vectors, dimension: {index.d}")
except Exception as e:
    logger.error(f"Failed to load FAISS index: {e}")
    index = None
    id_mapping = []

def get_embedding(text: str):
    """Generate embeddings using sentence-transformers (matches indexing model)"""
    if not text or not text.strip():
        logger.warning("Empty text provided for embedding")
        return None
    
    if embedding_model is None:
        logger.error("Embedding model not loaded")
        return None
    
    try:
        embedding = embedding_model.encode(
            [text], 
            normalize_embeddings=True,
            convert_to_numpy=True
        )[0]
        return embedding.reshape(1, -1).astype('float32')
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None

def search_faiss(query: str, top_k: int = 20):
    """Search FAISS index with comprehensive error handling"""
    if index is None:
        logger.error("FAISS index not loaded")
        return []
    
    if not query or not query.strip():
        logger.warning("Empty query provided")
        return []
    
    try:
        query_vec = get_embedding(query)
        
        if query_vec is None:
            logger.error("Failed to generate query embedding")
            return []
        
        # Verify dimensions match
        if query_vec.shape[1] != index.d:
            logger.error(f"Dimension mismatch: query {query_vec.shape[1]} vs index {index.d}")
            logger.error("Please regenerate FAISS index with matching model")
            return []
        
        distances, indices = index.search(query_vec, top_k)
        
        results = []
        for idx in indices[0]:
            if idx != -1 and idx < len(id_mapping):
                doc_id = id_mapping[idx]
                try:
                    doc = bns_collection.find_one({"_id": ObjectId(doc_id)})
                    if doc:
                        results.append({
                            "Section": doc.get("Section", ""),
                            "Section_name": doc.get("Section_name", ""),
                            "Description": doc.get("Description", ""),
                            "Chapter": doc.get("Chapter", ""),
                            "Chapter_name": doc.get("Chapter_name", "")
                        })
                except Exception as e:
                    logger.error(f"Error fetching document {doc_id}: {e}")
                    continue
        
        logger.info(f"Found {len(results)} relevant BNS sections for query")
        return results
        
    except Exception as e:
        logger.error(f"Error in FAISS search: {e}")
        return []

def is_legal_query(text: str) -> bool:
    """Check if the query contains any legal-related keyword."""
    text_lower = text.lower()
    words = text_lower.split() 
    return any(word in LEGAL_KEYWORDS for word in words)

@csrf_exempt
@firebase_login_required
def chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '').strip()
            language = data.get('language', 'english')

            if not message:
                return JsonResponse({
                    'error': 'Empty message provided',
                    'response': 'Please enter a question.',
                    'context': [],
                    'language': language
                }, status=400)

            # Simple preprocessing (no SpaCy needed - saves 500MB RAM and latency)
            processed_message = message.lower().strip()

            # Search FAISS for relevant BNS sections
            bns_results = search_faiss(processed_message, top_k=20)

            # Prepare RAG context with BNS schema fields
            if bns_results:
                rag_context = "\n\n".join([
                    f"**BNS Section {sec['Section']}** - {sec['Section_name']}\n"
                    f"Chapter: {sec.get('Chapter', 'N/A')} - {sec.get('Chapter_name', '')}\n"
                    f"Description: {sec['Description']}"
                    for sec in bns_results if isinstance(sec, dict) and sec.get('Section')
                ])
            else:
                rag_context = "No relevant Bharatiya Nyaya Sanhita (BNS) sections found."

            # Build prompt for Gemini
            user_input = (
                f"User Question: {message}\n\n"
                f"Relevant BNS 2023 Context:\n{rag_context}\n\n"
                f"Provide a detailed answer based on the Bharatiya Nyaya Sanhita 2023 (Indian Penal Code replacement)."
            )

            gemini_prompt = system_prompt + "\n\n" + user_input

            # Call Gemini API with safety settings disabled for legal content
            try:
                gemini_model = genai.GenerativeModel(
                    "models/gemini-2.5-flash",
                    generation_config={
                        "temperature": 0.2,
                        "top_p": 0.8,
                        "top_k": 40,
                        "max_output_tokens": 1024
                    },
                    safety_settings={
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    }
                )
                
                response = gemini_model.generate_content(gemini_prompt)

                # Handle response
                if not response.candidates:
                    gemini_response = "Unable to generate a response. Please rephrase your question."
                    logger.warning("No candidates in Gemini response")
                elif response.candidates[0].finish_reason == 2:
                    gemini_response = "This query requires legal context. Please provide more details."
                    logger.warning("Response blocked by safety filters despite BLOCK_NONE")
                else:
                    try:
                        gemini_response = response.text
                    except ValueError as e:
                        logger.error(f"Error extracting response text: {e}")
                        gemini_response = "Unable to generate a response. Please try rephrasing."
                        
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                gemini_response = "An error occurred while processing your request. Please try again."

            # Return JSON response with top 5 most relevant sections
            return JsonResponse({
                'response': gemini_response,
                'context': bns_results[:5],  # Limit context in response for performance
                'language': language
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON in request body',
                'response': 'Invalid request format.',
                'context': [],
                'language': 'english'
            }, status=400)
            
        except Exception as e:
            logger.error(f"Unexpected error in chat_api: {e}")
            return JsonResponse({
                'error': str(e),
                'response': 'An unexpected error occurred. Please try again.',
                'context': [],
                'language': language if 'language' in locals() else 'english'
            }, status=500)
    
    return JsonResponse({'error': 'Only POST method allowed'}, status=405)