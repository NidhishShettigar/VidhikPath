from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import os
import re
import tempfile
from datetime import datetime
import logging
import google.generativeai as genai
import pytesseract
import os

if os.name == 'nt':  # Windows
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

logger = logging.getLogger(__name__)

# Import dependencies with error handling
try:
    import cv2
    import pdfplumber
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
gemini_model = genai.GenerativeModel("gemini-2.5-flash")

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
    # Split by sentence boundaries including Indic punctuation
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
        IF : UPLODED DOCUMENT IS NOT LEGAL THEN JUST TELL 'SORRY THIS IS NOT LEGAL DOCUMENT SO I CAN'T SUMMERIZE' 
        
        ELSE DO THIS:
        Analyze this legal document excerpt and provide a clear summary in simple language.
        
        
        Provide:
        1. **Plain Language Summary** (2-3 sentences)
           - What this document is about in simple terms
        
        2. **Key Legal Points**
           - Important rights, obligations, or restrictions
           - Any deadlines or time limits mentioned
           - Relevant laws or sections cited
        
        3. **Action Items** (if any)
           - What the reader should do or be aware of
        
        Keep language accessible for non-lawyers. Avoid legal jargon where possible.
        
        Text: {chunk}
        """,
        
        'hi': f"""
        अगर : अपलोड किया गया दस्तावेज़ कानूनी नहीं है, तो सिर्फ इतना कहें:
        "सॉरी, यह कानूनी दस्तावेज़ नहीं है, इसलिए मैं इसका सारांश नहीं बना सकता।"
        
        अगर नहीं है तो यह करो :
        इस कानूनी दस्तावेज़ अंश का विश्लेषण करें और सरल भाषा में स्पष्ट सारांश प्रदान करें।
        
        प्रदान करें:
        1. **सरल भाषा सारांश** (2-3 वाक्य)
           - यह दस्तावेज़ किस बारे में है, सरल शब्दों में
        
        2. **प्रमुख कानूनी बिंदु**
           - महत्वपूर्ण अधिकार, दायित्व या प्रतिबंध
           - उल्लिखित कोई समय सीमा
           - संबंधित कानून या धाराएं
        
        3. **कार्य आइटम** (यदि कोई हो)
           - पाठक को क्या करना चाहिए या किस बात का ध्यान रखना चाहिए
        
        भाषा को गैर-वकीलों के लिए सुलभ रखें।

        पाठ: {chunk}
        """,
        
        'kn': f"""
        ಒಂದು ವೇಳೆ : ಅಪ್‌ಲೋಡ್ ಮಾಡಿದ ದಾಖಲೆ ಕಾನೂನು ಸಂಬಂಧಿತದಲ್ಲದಿದ್ದರೆ, ಈ ವಾಕ್ಯವನ್ನು ಮಾತ್ರ ಹೇಳಿ:
        "ಕ್ಷಮಿಸಿ, ಇದು ಕಾನೂನು ಸಂಬಂಧಿತ ದಾಖಲೆ ಅಲ್ಲ, ಆದ್ದರಿಂದ ನಾನು ಇದರ ಸಾರಾಂಶವನ್ನು ನೀಡಲು ಸಾಧ್ಯವಿಲ್ಲ."
        
        ಇಲ್ಲದಿದ್ದರೆ ಇದನ್ನು ಮಾಡು :
        ಈ ಕಾನೂನು ದಾಖಲೆಯ ಭಾಗವನ್ನು ವಿಶ್ಲೇಷಿಸಿ ಮತ್ತು ಸರಳ ಭಾಷೆಯಲ್ಲಿ ಸ್ಪಷ್ಟ ಸಾರಾಂಶವನ್ನು ಒದಗಿಸಿ.
        
        ಒದಗಿಸಿ:
        1. **ಸರಳ ಭಾಷೆ ಸಾರಾಂಶ** (2-3 ವಾಕ್ಯಗಳು)
           - ಈ ದಾಖಲೆ ಯಾವುದರ ಬಗ್ಗೆ, ಸರಳ ಪದಗಳಲ್ಲಿ
        
        2. **ಪ್ರಮುಖ ಕಾನೂನು ಅಂಶಗಳು**
           - ಪ್ರಮುಖ ಹಕ್ಕುಗಳು, ಕಟ್ಟುಪಾಡುಗಳು ಅಥವಾ ನಿರ್ಬಂಧಗಳು
           - ಉಲ್ಲೇಖಿಸಿದ ಯಾವುದೇ ಕಾಲಮಿತಿಗಳು
           - ಸಂಬಂಧಿತ ಕಾನೂನುಗಳು ಅಥವಾ ವಿಭಾಗಗಳು
        
        3. **ಕ್ರಿಯಾ ಅಂಶಗಳು** (ಯಾವುದಾದರೂ ಇದ್ದರೆ)
           - ಓದುಗರು ಏನು ಮಾಡಬೇಕು ಅಥವಾ ಗಮನಿಸಬೇಕು
        
        ವಕೀಲರಲ್ಲದವರಿಗೆ ಭಾಷೆಯನ್ನು ಸುಲಭವಾಗಿಸಿ.

        ಪಠ್ಯ: {chunk}
        """
    }
    
    return prompts.get(language_code, prompts['en'])

def summarize_chunk(chunk, language_code='en'):
    """Summarize one text chunk using Gemini."""
    try:
        prompt = get_summary_prompt(language_code, chunk)
        response = gemini_model.generate_content(prompt)
        clean_text = re.sub(r'#+\s*', '', response.text)  # removes ### or #### etc.
        return clean_text.strip()

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
        "gemini_model": gemini_model is not None
    }
    
    return JsonResponse({
        "status": "healthy" if dependencies["gemini_model"] else "error",
        "dependencies": dependencies,
        "supported_languages": SUPPORTED_LANGUAGES
    })