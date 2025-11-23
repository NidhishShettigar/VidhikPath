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
import re
from typing import List, Dict, Tuple
from textblob import TextBlob  # For spell correction
from spellchecker import SpellChecker  # Alternative spell checker

logger = logging.getLogger(__name__)

# Load system prompt
with open("legal_app/prompts/system_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()

# Load keywords
with open("legal_app/prompts/legal_keywords.txt", "r", encoding="utf-8") as f:
    LEGAL_KEYWORDS = set(line.strip().lower() for line in f if line.strip())

# Configure Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)

# Load MongoDB collections
bns_collection = db["bns"]
ipc_collection = db["ipc"]

# Use SAME model as indexing (CRITICAL!)
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

try:
    embedding_model = SentenceTransformer(MODEL_NAME)
    embedding_model.max_seq_length = 512
    logger.info(f"Embedding model loaded: {MODEL_NAME}")
except Exception as e:
    logger.error(f"Failed to load embedding model: {e}")
    embedding_model = None

# Initialize spell checker
spell = SpellChecker()

# Load FAISS index
try:
    index = faiss.read_index("legal_combined_index.faiss")
    with open("legal_id_mapping.json", "r", encoding="utf-8") as f:
        id_mapping = json.load(f)
    with open("legal_metadata.json", "r", encoding="utf-8") as f:
        metadata_list = json.load(f)
    logger.info(f"FAISS index loaded: {index.ntotal} vectors")
except Exception as e:
    logger.error(f"Failed to load FAISS index: {e}")
    index = None
    id_mapping = []
    metadata_list = []

# Legal term normalization (MUST match indexing!)
LEGAL_TERM_MAPPING = {
    'ipc': 'indian penal code',
    'bns': 'bharatiya nyaya sanhita',
    'sec': 'section',
    'sub-sec': 'subsection',
    'cr.p.c': 'criminal procedure code',
    'bnss': 'bharatiya nagarik suraksha sanhita',
    'crpc': 'criminal procedure code',
    'offence': 'offense',
    'offences': 'offenses',
}

# Legal terms that should NOT be spell-corrected
LEGAL_PROTECTED_TERMS = {
    'bns', 'ipc', 'crpc', 'bnss', 'bharatiya', 'nyaya', 'sanhita', 
    'penal', 'cognizable', 'bailable', 'compoundable', 'imprisonment',
    'theft', 'murder', 'assault', 'rape', 'kidnapping', 'fraud',
    'dacoity', 'culpable', 'homicide', 'defamation', 'extortion'
}

# Query expansion terms for better retrieval
QUERY_EXPANSION = {
    'murder': ['murder', 'killing', 'homicide', 'death'],
    'theft': ['theft', 'stealing', 'larceny', 'robbery'],
    'rape': ['rape', 'sexual assault', 'sexual violence'],
    'kidnapping': ['kidnapping', 'abduction', 'taking away'],
    'fraud': ['fraud', 'cheating', 'deception', 'dishonesty'],
    'assault': ['assault', 'violence', 'battery', 'attack'],
}

def correct_spelling(text: str) -> str:
    """
    Advanced spell correction with legal term protection
    """
    if not text or not isinstance(text, str):
        return ""
    
    try:
        words = text.split()
        corrected_words = []
        
        for word in words:
            # Remove punctuation for checking
            clean_word = re.sub(r'[^\w\s]', '', word.lower())
            
            # Skip if it's a legal term or number
            if (clean_word in LEGAL_PROTECTED_TERMS or 
                clean_word.isdigit() or 
                len(clean_word) <= 2):
                corrected_words.append(word)
                continue
            
            # Check if word is misspelled
            misspelled = spell.unknown([clean_word])
            
            if misspelled:
                # Get correction
                correction = spell.correction(clean_word)
                
                # Only apply if correction is confident (not None)
                if correction and correction != clean_word:
                    # Preserve original capitalization
                    if word[0].isupper():
                        correction = correction.capitalize()
                    corrected_words.append(correction)
                    logger.info(f"Corrected '{word}' to '{correction}'")
                else:
                    corrected_words.append(word)
            else:
                corrected_words.append(word)
        
        corrected_text = ' '.join(corrected_words)
        
        # Alternative: Use TextBlob for more aggressive correction
        # blob = TextBlob(text)
        # corrected_text = str(blob.correct())
        
        return corrected_text
        
    except Exception as e:
        logger.error(f"Spell correction error: {e}")
        return text  # Return original if correction fails

def advanced_query_preprocessing(query: str) -> str:
    """
    Advanced query preprocessing with spell correction and legal context
    """
    if not query or not isinstance(query, str):
        return ""
    
    # Step 1: Correct spelling FIRST
    query = correct_spelling(query)
    logger.info(f"After spell correction: {query}")
    
    # Step 2: Convert to lowercase
    query = query.lower()
    
    # Step 3: Normalize legal terms
    for abbr, full in LEGAL_TERM_MAPPING.items():
        query = re.sub(r'\b' + re.escape(abbr) + r'\b', full, query)
    
    # Step 4: Normalize section references
    query = re.sub(r'\bsec\.?\s*(\d+)', r'section \1', query)
    query = re.sub(r'\bsection\s*\.?\s*(\d+)', r'section \1', query)
    
    # Step 5: Remove extra whitespace
    query = ' '.join(query.split())
    
    # Step 6: Remove special characters (keep important ones)
    query = re.sub(r'[^\w\s\-\.\,\;\:\(\)\[\]/]', ' ', query)
    
    return query.strip()

def expand_query(query: str) -> str:
    """
    Expand query with synonyms for better retrieval
    """
    expanded_terms = []
    words = query.lower().split()
    
    for word in words:
        if word in QUERY_EXPANSION:
            expanded_terms.extend(QUERY_EXPANSION[word])
        else:
            expanded_terms.append(word)
    
    # Combine original query with expanded terms
    return query + " " + " ".join(set(expanded_terms))

def get_embedding(text: str) -> np.ndarray:
    """
    Generate embeddings (MUST match indexing model!)
    """
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

def retrieve_relevant_sections(query: str, top_k: int = 20) -> List[Dict]:
    """
    Advanced retrieval with spell correction, query expansion and reranking
    """
    if index is None:
        logger.error("FAISS index not loaded")
        return []
    
    if not query or not query.strip():
        logger.warning("Empty query provided")
        return []
    
    try:
        # Step 1: Preprocess query (includes spell correction)
        processed_query = advanced_query_preprocessing(query)
        logger.info(f"Original query: {query}")
        logger.info(f"Processed query: {processed_query}")
        
        # Step 2: Expand query
        expanded_query = expand_query(processed_query)
        logger.info(f"Expanded query: {expanded_query}")
        
        # Step 3: Generate embedding
        query_vec = get_embedding(expanded_query)
        
        if query_vec is None:
            logger.error("Failed to generate query embedding")
            return []
        
        # Step 4: Search FAISS (retrieve more for reranking)
        search_k = top_k * 2  # Retrieve 2x for reranking
        distances, indices = index.search(query_vec, search_k)
        
        # Step 5: Fetch documents and prepare results
        results = []
        seen_sections = set()  # Avoid duplicates
        
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx >= len(metadata_list):
                continue
            
            meta = metadata_list[idx]
            doc_id = meta["id"]
            source = meta["source"]
            section = meta.get("section", "")
            
            # Create unique key to avoid duplicates
            unique_key = f"{source}_{section}"
            if unique_key in seen_sections:
                continue
            seen_sections.add(unique_key)
            
            try:
                # Fetch full document
                if source == "bns":
                    doc = bns_collection.find_one({"_id": ObjectId(doc_id)})
                    if doc:
                        results.append({
                            "source": "BNS",
                            "section": doc.get("Section", ""),
                            "section_name": doc.get("Section_name", ""),
                            "description": doc.get("Description", ""),
                            "chapter": doc.get("Chapter", ""),
                            "chapter_name": doc.get("Chapter_name", ""),
                            "similarity": float(dist)
                        })
                else:  # ipc
                    doc = ipc_collection.find_one({"_id": ObjectId(doc_id)})
                    if doc:
                        results.append({
                            "source": "IPC",
                            "section": doc.get("Section", ""),
                            "section_name": doc.get("section_title", ""),
                            "description": doc.get("section_desc", ""),
                            "chapter": doc.get("chapter", ""),
                            "chapter_name": doc.get("chapter_title", ""),
                            "similarity": float(dist)
                        })
            except Exception as e:
                logger.error(f"Error fetching document {doc_id}: {e}")
                continue
            
            # Stop when we have enough results
            if len(results) >= top_k:
                break
        
        logger.info(f"Retrieved {len(results)} relevant sections")
        
        # Step 6: Simple reranking based on similarity scores
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        return results[:top_k]
        
    except Exception as e:
        logger.error(f"Error in retrieval: {e}")
        return []

def format_context_for_llm(sections: List[Dict]) -> str:
    """
    Format retrieved sections for LLM with clear structure
    """
    if not sections:
        return "No relevant legal sections found in the database."
    
    context_parts = []
    
    for i, sec in enumerate(sections, 1):
        source = sec.get('source', 'UNKNOWN')
        section_num = sec.get('section', 'N/A')
        section_name = sec.get('section_name', 'N/A')
        description = sec.get('description', 'N/A')
        chapter = sec.get('chapter', '')
        chapter_name = sec.get('chapter_name', '')
        
        section_text = f"""
### {i}. [{source}] Section {section_num}: {section_name}
**Chapter:** {chapter} - {chapter_name}
**Details:** {description[:500]}...
**Relevance Score:** {sec.get('similarity', 0):.3f}
"""
        context_parts.append(section_text)
    
    return "\n".join(context_parts)

def format_chat_history(history: list) -> str:
    """
    Enhanced chat history formatting with better context preservation
    """
    if not history:
        return ""
    
    # Take more messages for better context (last 10 instead of 5)
    formatted = "\n\n### Previous Conversation:\n"
    recent_history = history[-10:] if len(history) > 10 else history
    
    for msg in recent_history:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        formatted += f"\n**{role.capitalize()}:** {content}\n"
    
    formatted += "\n---\n"
    return formatted

# Language configurations
LANGUAGE_CONFIG = {
    'english': {
        'name': 'English',
        'instruction': 'Respond in clear, professional English.'
    },
    'hindi': {
        'name': 'हिन्दी',
        'instruction': 'कृपया स्पष्ट और व्यावसायिक हिन्दी में जवाब दें। सभी कानूनी जानकारी हिन्दी में प्रदान करें।'
    },
    'kannada': {
        'name': 'ಕನ್ನಡ',
        'instruction': 'ದಯವಿಟ್ಟು ಸ್ಪಷ್ಟ ಮತ್ತು ವೃತ್ತಿಪರ ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ। ಎಲ್ಲಾ ಕಾನೂನು ಮಾಹಿತಿಯನ್ನು ಕನ್ನಡದಲ್ಲಿ ನೀಡಿ।'
    }
}

@csrf_exempt
@firebase_login_required
def chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '').strip()
            language = data.get('language', 'english').lower()
            chat_history = data.get('history', [])

            if not message:
                return JsonResponse({
                    'error': 'Empty message provided',
                    'response': 'Please enter a question.',
                    'context': [],
                    'language': language
                }, status=400)

            # Validate language
            if language not in LANGUAGE_CONFIG:
                language = 'english'

            # Step 1: Retrieve relevant sections (with spell correction)
            relevant_sections = retrieve_relevant_sections(message, top_k=20)
            
            # Step 2: Format context
            rag_context = format_context_for_llm(relevant_sections)
            
            # Step 3: Format chat history (enhanced for better context)
            history_context = format_chat_history(chat_history)
            
            # Step 4: Get language instruction
            lang_instruction = LANGUAGE_CONFIG[language]['instruction']
            
            # Step 5: Build enhanced prompt with explicit context awareness
            user_input = f"""
{history_context}

### Current User Question:
{message}

### Relevant Legal Sections (BNS 2023 & IPC):
{rag_context}

### LANGUAGE INSTRUCTION:
{lang_instruction}

### CRITICAL INSTRUCTIONS FOR CONTEXT AWARENESS:
-3. **If current user question is greeting just respond that greet dont provide any ipc and bns sections 
-2. **If there is now related ipc and bns dont tell any statement like this I cannot provide a definition of "divorce" based on the provided sections to user 
-1. **If user asking the defination of some legal word like bns, ipc, divorce etc provide its defination 
0. **If user question is legal like how to file divorce or how to file case or complaint or etc answer that question and dont provide any bns and ipc sections
1. **Analyze the conversation history carefully** - If the current question refers to previous topics (e.g., "example", "more details", "explain that"), you MUST connect it to the previous context
2. **If the user asks for "example", "more", "explain that", etc.**, refer back to what was discussed earlier in the conversation
3. **Answer based on the provided legal sections above**
4. **Cite specific section numbers** (e.g., "According to BNS Section 302...")
5. **If multiple sections are relevant**, explain each one
6. **If the sections don't fully answer the question**, say so clearly
7. **Use {LANGUAGE_CONFIG[language]['name']} language exclusively** for the entire response
8. **Be precise, professional, and helpful**
9. **When the user's question seems vague** (like "example", "more info"), look at the previous messages to understand what they're referring to

### EXAMPLE OF GOOD CONTEXT AWARENESS:
User: "What is BNS?"
Assistant: "BNS stands for Bharatiya Nyaya Sanhita 2023..."

User: "example"
Assistant: "Based on our previous discussion about BNS, here's an example: [provides example related to BNS]..."
"""

            gemini_prompt = system_prompt + "\n\n" + user_input

            # Step 6: Call Gemini with enhanced configuration
            try:
                gemini_model = genai.GenerativeModel(
                    "models/gemini-2.0-flash",
                    generation_config={
                        "temperature": 0.4,  # Balanced for context + creativity
                        "top_p": 0.9,
                        "top_k": 40,
                        "max_output_tokens": 2048,
                        "candidate_count": 1,
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
                    gemini_response = get_error_message(language, "no_response")
                    logger.warning("No candidates in Gemini response")
                elif response.candidates[0].finish_reason == 2:
                    gemini_response = get_error_message(language, "need_details")
                    logger.warning("Response blocked by safety filters")
                else:
                    try:
                        gemini_response = response.text
                    except ValueError as e:
                        logger.error(f"Error extracting response text: {e}")
                        gemini_response = get_error_message(language, "rephrase")
                        
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                gemini_response = get_error_message(language, "error")

            # Return top 5 sections for display
            context_for_display = relevant_sections[:5]
            
            return JsonResponse({
                'response': gemini_response,
                'context': context_for_display,
                'language': language,
                'retrieved_count': len(relevant_sections),
                'corrected_query': correct_spelling(message)  # Show corrected query
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
                'response': get_error_message(language if 'language' in locals() else 'english', 'error'),
                'context': [],
                'language': language if 'language' in locals() else 'english'
            }, status=500)
    
    return JsonResponse({'error': 'Only POST method allowed'}, status=405)

def get_error_message(language: str, error_type: str) -> str:
    """Get error messages in the appropriate language"""
    messages = {
        'english': {
            'no_response': 'Unable to generate a response. Please rephrase your question.',
            'need_details': 'This query requires more context. Please provide additional details.',
            'rephrase': 'Unable to generate a response. Please try rephrasing.',
            'error': 'An error occurred while processing your request. Please try again.'
        },
        'hindi': {
            'no_response': 'प्रतिक्रिया उत्पन्न करने में असमर्थ। कृपया अपने प्रश्न को दोबारा लिखें।',
            'need_details': 'इस प्रश्न के लिए अधिक संदर्भ की आवश्यकता है। कृपया अतिरिक्त विवरण प्रदान करें।',
            'rephrase': 'प्रतिक्रिया उत्पन्न करने में असमर्थ। कृपया दोबारा प्रयास करें।',
            'error': 'आपके अनुरोध को संसाधित करते समय एक त्रुटि हुई। कृपया पुनः प्रयास करें।'
        },
        'kannada': {
            'no_response': 'ಪ್ರತಿಕ್ರಿಯೆಯನ್ನು ರಚಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಮರುಹೊಂದಿಸಿ.',
            'need_details': 'ಈ ಪ್ರಶ್ನೆಗೆ ಹೆಚ್ಚಿನ ಸಂದರ್ಭ ಅಗತ್ಯವಿದೆ. ದಯವಿಟ್ಟು ಹೆಚ್ಚುವರಿ ವಿವರಗಳನ್ನು ನೀಡಿ.',
            'rephrase': 'ಪ್ರತಿಕ್ರಿಯೆಯನ್ನು ರಚಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
            'error': 'ನಿಮ್ಮ ವಿನಂತಿಯನ್ನು ಪ್ರಕ್ರಿಯೆಗೊಳಿಸುವಾಗ ದೋಷ ಸಂಭವಿಸಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.'
        }
    }
    
    lang_messages = messages.get(language, messages['english'])
    return lang_messages.get(error_type, lang_messages['error'])