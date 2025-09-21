from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from bson import ObjectId
from ..db_connection import db
from ..firebase_utils import FirebaseAuth
from .base_views import firebase_login_required
import faiss
import numpy as np
import torch
import spacy
from transformers import AutoTokenizer, AutoModel
import google.generativeai as genai
import json



with open("legal_app\prompts\system_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()

# Load keywords from file once at startup
with open("legal_app\prompts\legal_keywords.txt", "r", encoding="utf-8") as f:
    LEGAL_KEYWORDS = set(line.strip().lower() for line in f if line.strip())
    
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
    # print("Indices:", indices)
    results = []
    for idx in indices[0]:
        # print("Checking index:", idx)
        if idx != -1 and idx < len(id_mapping):
            doc_id = id_mapping[idx]
            # print("Mapped doc_id:", doc_id)
            doc = ipc_collection.find_one({"_id": ObjectId(doc_id)})
            if doc:
                results.append({
                    "Section": doc.get("Section"),
                    "section_title": doc.get("section_title"),
                    "section_desc": doc.get("section_desc"),
                })
            else:
                print("⚠️ No document found for:", doc_id)
    # print("Final Results:", results)
    return results

def is_legal_query(text: str) -> bool:
    """Check if the query contains any legal-related keyword."""
    text_lower = text.lower()
    words = text_lower.split() 
    return any(word in LEGAL_KEYWORDS for word in words)


@csrf_exempt
@firebase_login_required
def chat_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        language = data.get('language', 'english')

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
