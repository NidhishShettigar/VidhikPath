from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import os
import re
import tempfile
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Import dependencies with error handling
try:
    import cv2
    import pdfplumber
    import pytesseract
    from pdf2image import convert_from_path
    import google.generativeai as genai
except ImportError as e:
    logger.error(f"Missing required dependency: {e}")
    raise

try:
    from .base_views import firebase_login_required
    from ..db_connection import db
except ImportError:
    def firebase_login_required(view_func):
        return view_func
    db = None

# Initialize Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

# Language configuration
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'hi': 'Hindi', 
    'kn': 'Kannada'
}

def clean_image(image_path):
    """Apply image preprocessing for better OCR results."""
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Could not read image from {image_path}")
    
    _, thresh = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cleaned_path = image_path.replace(".png", "_cleaned.png")
    cv2.imwrite(cleaned_path, thresh)
    return cleaned_path

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF if it has embedded text."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

def ocr_pdf(pdf_path, language='eng'):
    """OCR scanned PDF by converting pages to images."""
    pages = convert_from_path(pdf_path, dpi=300)
    text = ""
    
    lang_config = get_tesseract_lang(language)
    
    for i, page in enumerate(pages):
        img_path = f"{pdf_path}_page_{i}.png"
        page.save(img_path, "PNG")
        
        try:
            cleaned = clean_image(img_path)
            text += pytesseract.image_to_string(cleaned, lang=lang_config) + "\n"
            
            # Cleanup temp files
            os.remove(cleaned)
            os.remove(img_path)
        except Exception as e:
            logger.error(f"Error processing page {i}: {e}")
            if os.path.exists(img_path):
                os.remove(img_path)
            continue
            
    return text.strip()

def ocr_image(image_path, language='eng'):
    """OCR single image file."""
    cleaned = clean_image(image_path)
    lang_config = get_tesseract_lang(language)
    text = pytesseract.image_to_string(cleaned, lang=lang_config)
    
    os.remove(cleaned)
    return text.strip()

def get_tesseract_lang(lang_code):
    """Map language codes to Tesseract language codes."""
    lang_mapping = {
        'en': 'eng',
        'hi': 'hin',
        'kn': 'kan',
        'auto': 'eng+hin+kan'
    }
    return lang_mapping.get(lang_code, 'eng')

def detect_language(text):
    """Detect primary language based on script analysis."""
    devanagari_count = len(re.findall(r'[\u0900-\u097F]', text))
    kannada_count = len(re.findall(r'[\u0C80-\u0CFF]', text))
    english_count = len(re.findall(r'[a-zA-Z]', text))
    
    total_chars = len(re.sub(r'\s', '', text))
    
    if total_chars == 0:
        return 'en'
    
    if devanagari_count / total_chars > 0.3:
        return 'hi'
    elif kannada_count / total_chars > 0.3:
        return 'kn'
    else:
        return 'en'

def chunk_text(text, max_len=3000):
    """Split text into manageable chunks for summarization."""
    # Split by sentence boundaries
    sentences = re.split(r'(?<=[.!?।॥])\s+', text)
    
    if len(sentences) <= 1:
        sentences = text.split('\n\n')
    
    chunks = []
    current = ""
    
    for sentence in sentences:
        if len(current) + len(sentence) < max_len:
            current += " " + sentence
        else:
            if current:
                chunks.append(current.strip())
            current = sentence
            
    if current:
        chunks.append(current.strip())
        
    return chunks if chunks else [text[:max_len]]

def get_summary_prompt(language_code, chunk):
    """Get language-specific prompts for summarization."""
    prompts = {
        'en': f"""
        Summarize the following legal document text clearly and concisely.
        
        Provide:
        1. **Plain summary** - explain in simple terms
        2. **Key points** - important laws, rights, duties, or penalties

        Text: {chunk}
        """,
        
        'hi': f"""
        निम्नलिखित कानूनी दस्तावेज़ पाठ का सारांश हिंदी में करें।
        
        प्रदान करें:
        1. **सरल सारांश** - सरल शब्दों में स्पष्ट रूप से समझाएं
        2. **मुख्य बिंदु** - महत्वपूर्ण कानून, अधिकार, कर्तव्य या दंड

        पाठ: {chunk}
        """,
        
        'kn': f"""
        ಈ ಕಾನೂನು ದಾಖಲೆಯ ಪಠ್ಯವನ್ನು ಕನ್ನಡದಲ್ಲಿ ಸಾರಾಂಶಗೊಳಿಸಿ.
        
        ಒದಗಿಸಿ:
        1. **ಸರಳ ಸಾರಾಂಶ** - ಸರಳ ಪದಗಳಲ್ಲಿ ಸ್ಪಷ್ಟವಾಗಿ ವಿವರಿಸಿ
        2. **ಮುಖ್ಯ ಅಂಶಗಳು** - ಪ್ರಮುಖ ಕಾನೂನುಗಳು, ಹಕ್ಕುಗಳು, ಕರ್ತವ್ಯಗಳು ಅಥವಾ ದಂಡಗಳು

        ಪಠ್ಯ: {chunk}
        """
    }
    
    return prompts.get(language_code, prompts['en'])

def summarize_chunk(chunk, language_code='en'):
    """Summarize one text chunk using Gemini."""
    try:
        prompt = get_summary_prompt(language_code, chunk)
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error summarizing chunk: {e}")
        return f"Summary unavailable: {str(e)}"

@csrf_exempt
@firebase_login_required
def summarize_api(request):
    """Main API endpoint for document summarization."""
    
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)
    
    if "document" not in request.FILES:
        return JsonResponse({"error": "No document provided"}, status=400)
    
    document = request.FILES["document"]
    target_language = request.POST.get('language', 'auto')
    
    if target_language not in ['auto'] + list(SUPPORTED_LANGUAGES.keys()):
        return JsonResponse({"error": f"Unsupported language: {target_language}"}, status=400)

    temp_path = None
    
    try:
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=document.name) as tmp_file:
            for chunk in document.chunks():
                tmp_file.write(chunk)
            temp_path = tmp_file.name

        # Extract text based on file type
        ext = os.path.splitext(document.name)[1].lower()
        raw_text = ""

        if ext == ".pdf":
            raw_text = extract_text_from_pdf(temp_path)
            if not raw_text.strip():  # Fallback to OCR for scanned PDFs
                logger.info("No text found in PDF, trying OCR")
                ocr_lang = target_language if target_language != 'auto' else 'auto'
                raw_text = ocr_pdf(temp_path, ocr_lang)
                
        elif ext in [".png", ".jpg", ".jpeg"]:
            ocr_lang = target_language if target_language != 'auto' else 'auto'
            raw_text = ocr_image(temp_path, ocr_lang)
            
        else:
            return JsonResponse({
                "error": f"Unsupported file type: {ext}. Supported: PDF, PNG, JPG, JPEG"
            }, status=400)

        if not raw_text.strip():
            return JsonResponse({"error": "No readable text found in document"}, status=400)

        # Auto-detect language if needed
        if target_language == 'auto':
            target_language = detect_language(raw_text)

        # Process text in chunks
        chunks = chunk_text(raw_text)
        summaries = []
        
        for i, chunk in enumerate(chunks):
            try:
                summary = summarize_chunk(chunk, target_language)
                summaries.append(summary)
                logger.info(f"Processed chunk {i+1}/{len(chunks)}")
            except Exception as e:
                logger.error(f"Error summarizing chunk {i+1}: {e}")
                summaries.append(f"Error processing section: {str(e)}")
        
        final_summary = "\n\n---\n\n".join(summaries)

        # Store in database if available
        if db:
            try:
                user_id = getattr(request.user, 'uid', 'anonymous') if hasattr(request, 'user') else 'anonymous'
                summary_doc = {
                    "user_id": user_id,
                    "filename": document.name,
                    "summary": final_summary,
                    "language": target_language,
                    "language_name": SUPPORTED_LANGUAGES.get(target_language, target_language),
                    "chunks_processed": len(chunks),
                    "file_type": ext,
                    "created_at": datetime.utcnow()
                }
                db["summaries"].insert_one(summary_doc)
            except Exception as e:
                logger.error(f"Failed to save to database: {e}")

        return JsonResponse({
            "status": "success",
            "summary": final_summary,
            "chunks_processed": len(chunks),
            "detected_language": target_language,
            "language_name": SUPPORTED_LANGUAGES.get(target_language, target_language),
            "file_type": ext
        })

    except Exception as e:
        logger.error(f"Error in summarize_api: {e}")
        return JsonResponse({"error": f"Processing failed: {str(e)}"}, status=500)

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.error(f"Failed to cleanup temp file: {e}")

@csrf_exempt
def get_supported_languages(request):
    """Get list of supported languages."""
    return JsonResponse({
        "supported_languages": SUPPORTED_LANGUAGES,
        "tesseract_languages": {
            'en': 'eng',
            'hi': 'hin',
            'kn': 'kan',
            'auto': 'eng+hin+kan'
        }
    })

def health_check(request):
    """Check API health status."""
    dependencies = {
        "gemini_model": gemini_model is not None,
        "db": db is not None
    }
    
    return JsonResponse({
        "status": "healthy" if dependencies["gemini_model"] else "error",
        "dependencies": dependencies,
        "supported_languages": SUPPORTED_LANGUAGES
    })