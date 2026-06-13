from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from bson import ObjectId
from ..db_connection import db
from .base_views import firebase_login_required
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import json
import logging
import re
import os
from typing import List, Dict

logger = logging.getLogger(__name__)

# Load system prompt
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_system_prompt_path = os.path.join(_base_dir, "prompts", "system_prompt.txt")
with open(_system_prompt_path, "r", encoding="utf-8") as f:
    system_prompt = f.read()

# Load legal keywords
_keywords_path = os.path.join(_base_dir, "prompts", "legal_keywords.txt")
with open(_keywords_path, "r", encoding="utf-8") as f:
    LEGAL_KEYWORDS = set(line.strip().lower() for line in f if line.strip())

# Configure Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)

# Load MongoDB collections
bns_collection = db["bns"]
ipc_collection = db["ipc"]

# Legal term normalization
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


def normalize_query(query: str) -> str:
    """Normalize legal terms in query."""
    query = query.lower()
    for abbr, full in LEGAL_TERM_MAPPING.items():
        query = re.sub(r'\b' + re.escape(abbr) + r'\b', full, query)
    query = re.sub(r'\bsec\.?\s*(\d+)', r'section \1', query)
    query = re.sub(r'\bsection\s*\.?\s*(\d+)', r'section \1', query)
    query = ' '.join(query.split())
    return query.strip()


def retrieve_relevant_sections_via_gemini(query: str, top_k: int = 10) -> List[Dict]:
    """
    Use Gemini to identify relevant legal section numbers from the query,
    then fetch those sections from MongoDB.
    Falls back to a keyword-based MongoDB text search.
    """
    results = []

    try:
        # Step 1: Ask Gemini to extract relevant BNS/IPC section numbers from the query
        extraction_prompt = f"""You are a legal assistant. Given the user query below, identify the most relevant 
Indian Penal Code (IPC) and Bharatiya Nyaya Sanhita (BNS) section numbers that are likely to be relevant.

User query: "{query}"

Respond ONLY with a valid JSON object in this exact format (no markdown, no explanation):
{{
  "bns_sections": ["101", "103"],
  "ipc_sections": ["302", "304"],
  "keywords": ["murder", "culpable homicide"]
}}

If no specific sections are clearly relevant, return empty lists and provide keywords only.
"""
        extraction_model = genai.GenerativeModel(
            "models/gemini-2.5-flash",
            generation_config={"temperature": 0.1, "max_output_tokens": 300}
        )
        extraction_response = extraction_model.generate_content(extraction_prompt)
        raw = extraction_response.text.strip()

        # Strip markdown code fences if present
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        extracted = json.loads(raw)
        bns_sections = extracted.get("bns_sections", [])
        ipc_sections = extracted.get("ipc_sections", [])
        keywords = extracted.get("keywords", [])

        # Step 2: Fetch BNS sections from MongoDB
        for sec_num in bns_sections[:5]:
            try:
                doc = bns_collection.find_one({"Section": sec_num})
                if doc:
                    results.append({
                        "source": "BNS",
                        "section": doc.get("Section", ""),
                        "section_name": doc.get("Section_name", ""),
                        "description": doc.get("Description", ""),
                        "chapter": doc.get("Chapter", ""),
                        "chapter_name": doc.get("Chapter_name", ""),
                    })
            except Exception as e:
                logger.error(f"Error fetching BNS section {sec_num}: {e}")

        # Step 3: Fetch IPC sections from MongoDB
        for sec_num in ipc_sections[:5]:
            try:
                doc = ipc_collection.find_one({"Section": sec_num})
                if doc:
                    results.append({
                        "source": "IPC",
                        "section": doc.get("Section", ""),
                        "section_name": doc.get("section_title", ""),
                        "description": doc.get("section_desc", ""),
                        "chapter": doc.get("chapter", ""),
                        "chapter_name": doc.get("chapter_title", ""),
                    })
            except Exception as e:
                logger.error(f"Error fetching IPC section {sec_num}: {e}")

        # Step 4: If not enough results, do keyword-based fallback search in MongoDB
        if len(results) < 3 and keywords:
            keyword_str = " ".join(keywords[:3])
            try:
                bns_docs = bns_collection.find(
                    {"$text": {"$search": keyword_str}},
                    {"score": {"$meta": "textScore"}}
                ).sort([("score", {"$meta": "textScore"})]).limit(5)
                for doc in bns_docs:
                    sec = doc.get("Section", "")
                    if not any(r["source"] == "BNS" and r["section"] == sec for r in results):
                        results.append({
                            "source": "BNS",
                            "section": sec,
                            "section_name": doc.get("Section_name", ""),
                            "description": doc.get("Description", ""),
                            "chapter": doc.get("Chapter", ""),
                            "chapter_name": doc.get("Chapter_name", ""),
                        })
            except Exception as e:
                logger.warning(f"BNS text search failed (text index may not exist): {e}")
                # Regex fallback
                try:
                    pattern = re.compile("|".join(re.escape(k) for k in keywords[:3]), re.IGNORECASE)
                    bns_docs = bns_collection.find(
                        {"$or": [{"Section_name": pattern}, {"Description": pattern}]}
                    ).limit(5)
                    for doc in bns_docs:
                        sec = doc.get("Section", "")
                        if not any(r["source"] == "BNS" and r["section"] == sec for r in results):
                            results.append({
                                "source": "BNS",
                                "section": sec,
                                "section_name": doc.get("Section_name", ""),
                                "description": doc.get("Description", ""),
                                "chapter": doc.get("Chapter", ""),
                                "chapter_name": doc.get("Chapter_name", ""),
                            })
                except Exception as e2:
                    logger.error(f"BNS regex fallback failed: {e2}")

            try:
                ipc_docs = ipc_collection.find(
                    {"$text": {"$search": keyword_str}},
                    {"score": {"$meta": "textScore"}}
                ).sort([("score", {"$meta": "textScore"})]).limit(5)
                for doc in ipc_docs:
                    sec = doc.get("Section", "")
                    if not any(r["source"] == "IPC" and r["section"] == sec for r in results):
                        results.append({
                            "source": "IPC",
                            "section": sec,
                            "section_name": doc.get("section_title", ""),
                            "description": doc.get("section_desc", ""),
                            "chapter": doc.get("chapter", ""),
                            "chapter_name": doc.get("chapter_title", ""),
                        })
            except Exception as e:
                logger.warning(f"IPC text search failed: {e}")
                try:
                    pattern = re.compile("|".join(re.escape(k) for k in keywords[:3]), re.IGNORECASE)
                    ipc_docs = ipc_collection.find(
                        {"$or": [{"section_title": pattern}, {"section_desc": pattern}]}
                    ).limit(5)
                    for doc in ipc_docs:
                        sec = doc.get("Section", "")
                        if not any(r["source"] == "IPC" and r["section"] == sec for r in results):
                            results.append({
                                "source": "IPC",
                                "section": sec,
                                "section_name": doc.get("section_title", ""),
                                "description": doc.get("section_desc", ""),
                                "chapter": doc.get("chapter", ""),
                                "chapter_name": doc.get("chapter_title", ""),
                            })
                except Exception as e2:
                    logger.error(f"IPC regex fallback failed: {e2}")

    except Exception as e:
        logger.error(f"Error in Gemini-based retrieval: {e}")

    logger.info(f"Retrieved {len(results)} relevant sections")
    return results[:top_k]


def format_context_for_llm(sections: List[Dict]) -> str:
    """Format retrieved sections for LLM."""
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
**Details:** {str(description)[:500]}...
"""
        context_parts.append(section_text)

    return "\n".join(context_parts)


def format_chat_history(history: list) -> str:
    """Format chat history for context."""
    if not history:
        return ""

    formatted = "\n\n### Previous Conversation:\n"
    recent_history = history[-10:] if len(history) > 10 else history

    for msg in recent_history:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        formatted += f"\n**{role.capitalize()}:** {content}\n"

    formatted += "\n---\n"
    return formatted


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

            if language not in LANGUAGE_CONFIG:
                language = 'english'

            # Step 1: Normalize query
            normalized_query = normalize_query(message)

            # Step 2: Retrieve relevant sections using Gemini + MongoDB
            relevant_sections = retrieve_relevant_sections_via_gemini(normalized_query, top_k=10)

            # Step 3: Format context
            rag_context = format_context_for_llm(relevant_sections)

            # Step 4: Format chat history
            history_context = format_chat_history(chat_history)

            # Step 5: Get language instruction
            lang_instruction = LANGUAGE_CONFIG[language]['instruction']

            # Step 6: Build prompt
            user_input = f"""
{history_context}

### Current User Question:
{message}

### Relevant Legal Sections (BNS 2023 & IPC):
{rag_context}

### LANGUAGE INSTRUCTION:
{lang_instruction}

### CRITICAL INSTRUCTIONS FOR CONTEXT AWARENESS:
-4. If current user question is a greeting, just respond to the greeting — do NOT provide any IPC/BNS sections.
-3. If there is no related IPC/BNS, do NOT say "I cannot provide..." or "I didn't find related sections".
-2. If no related IPC/BNS is found, answer based on your general legal knowledge and provide relevant sections you know.
-1. If user asks the definition of a legal word like BNS, IPC, divorce etc., provide its definition only.
0. If user asks a procedural question (how to file a case, how to file divorce etc.), answer the question — do NOT provide BNS/IPC sections.
1. Analyze the conversation history carefully. If the current question refers to previous topics (e.g., "example", "more details", "explain that"), connect it to the previous context.
2. If the user asks for "example", "more", "explain that", refer back to what was discussed earlier.
3. Answer based on the provided legal sections above.
4. Cite specific section numbers (e.g., "According to BNS Section 103...").
5. If multiple sections are relevant, explain each one.
6. If the sections don't fully answer the question, say so clearly.
7. Use {LANGUAGE_CONFIG[language]['name']} language exclusively for the entire response.
8. Be precise, professional, and helpful.
9. When the user's question seems vague (like "example", "more info"), look at the previous messages to understand context.
"""

            gemini_prompt = system_prompt + "\n\n" + user_input

            # Step 7: Call Gemini
            try:
                gemini_model = genai.GenerativeModel(
                    "models/gemini-2.5-flash",
                    generation_config={
                        "temperature": 0.4,
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

            context_for_display = relevant_sections[:5]

            return JsonResponse({
                'response': gemini_response,
                'context': context_for_display,
                'language': language,
                'retrieved_count': len(relevant_sections),
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
    """Get error messages in the appropriate language."""
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
