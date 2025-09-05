from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import os
import re
import tempfile
from datetime import datetime
import cv2
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import google.generativeai as genai
from .base_views import firebase_login_required
from ..db_connection import db   

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