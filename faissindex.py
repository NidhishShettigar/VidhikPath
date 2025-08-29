import faiss
import torch
import numpy as np
from pymongo import MongoClient
from transformers import AutoTokenizer, AutoModel
import json
import re
from typing import List, Dict, Optional
import logging
from tqdm import tqdm

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Connect to MongoDB
try:
    client = MongoClient("mongodb+srv://vidhikpath:vidhikpath@cluster0.m2j80to.mongodb.net/")
    db = client["vidhikpath"]
    ipc_collection = db["ipc"]
    logger.info("Connected to MongoDB")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    exit(1)

# 2. Load LegalBERT
try:
    tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
    model = AutoModel.from_pretrained("nlpaueb/legal-bert-base-uncased")
    model.eval()  # Set to evaluation mode
    logger.info("LegalBERT model loaded")
except Exception as e:
    logger.error(f"Model loading failed: {e}")
    exit(1)

def clean_text(text: str) -> str:
    """Clean and normalize text for better embeddings"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text.strip())
    text = re.sub(r'[^\w\s\-\.\,\;\:\(\)\[\]]', ' ', text)
    text = re.sub(r'\b(sec|section)\b', 'section', text, flags=re.IGNORECASE)
    text = re.sub(r'\bipc\b', 'indian penal code', text, flags=re.IGNORECASE)
    return text.strip()

def get_embedding(text: str, max_length: int = 512) -> Optional[np.ndarray]:
    """Generate LegalBERT embeddings with error handling"""
    try:
        if not text or len(text.strip()) == 0:
            logger.warning("Empty text provided for embedding")
            return None
        clean_txt = clean_text(text)
        inputs = tokenizer(
            clean_txt, 
            return_tensors="pt", 
            truncation=True, 
            padding=True,
            max_length=max_length
        )
        with torch.no_grad():
            outputs = model(**inputs)
        embedding = outputs.last_hidden_state[:, 0, :].numpy()
        return embedding[0]
    except Exception as e:
        logger.error(f"Error generating embedding for text: {text[:50]}... Error: {e}")
        return None

def create_enhanced_text_representation(doc: Dict) -> str:
    """Create better text representation for each IPC section"""
    try:
        chapter = str(doc.get('chapter', '') or '').strip()
        chapter_title = str(doc.get('chapter_title', '') or '').strip()
        section = str(doc.get('Section', '') or '').strip()
        section_title = str(doc.get('section_title', '') or '').strip()
        section_desc = str(doc.get('section_desc', '') or '').strip()
        text_parts = []
        if section:
            text_parts.append(f"Section {section}")
        if section_title:
            text_parts.append(section_title)
        if chapter and chapter_title:
            text_parts.append(f"Chapter {chapter} {chapter_title}")
        elif chapter_title:
            text_parts.append(chapter_title)
        if section_desc:
            text_parts.append(section_desc)
        combined_text = f"IPC Section {section} {section_title}. " + " ".join(text_parts)
        return combined_text
    except Exception as e:
        logger.error(f"Error creating text representation for doc {doc.get('_id')}: {e}")
        return ""

def validate_embeddings(embeddings: List[np.ndarray]) -> List[int]:
    """Validate embeddings and return indices of valid ones"""
    valid_indices = []
    for i, emb in enumerate(embeddings):
        if emb is not None and emb.shape[0] > 0:
            if not (np.isnan(emb).any() or np.isinf(emb).any()):
                valid_indices.append(i)
            else:
                logger.warning(f"Invalid embedding at index {i} (NaN/Inf values)")
        else:
            logger.warning(f"None or empty embedding at index {i}")
    return valid_indices

def create_faiss_index():
    """Create optimized FAISS index with error handling"""
    logger.info("Starting FAISS index creation...")
    try:
        ipc_docs = list(ipc_collection.find({}))
        logger.info(f"Found {len(ipc_docs)} IPC documents")
        if len(ipc_docs) == 0:
            logger.error("No documents found in IPC collection")
            return False
    except Exception as e:
        logger.error(f"Error fetching IPC documents: {e}")
        return False

    logger.info("Generating embeddings...")
    embeddings = []
    doc_metadata = []
    for doc in tqdm(ipc_docs, desc="Processing documents"):
        try:
            text = create_enhanced_text_representation(doc)
            if not text:
                logger.warning(f"Empty text for document {doc.get('_id')}")
                continue
            embedding = get_embedding(text)
            if embedding is not None:
                embeddings.append(embedding)
                doc_metadata.append({
                    "id": str(doc["_id"]),
                    "section": doc.get("Section", ""),
                    "title": doc.get("section_title", ""),
                    "chapter": doc.get("chapter", ""),
                    "text_length": len(text)
                })
            else:
                logger.warning(f"Failed to generate embedding for document {doc.get('_id')}")
        except Exception as e:
            logger.error(f"Error processing document {doc.get('_id')}: {e}")
            continue
    if len(embeddings) == 0:
        logger.error("No valid embeddings generated")
        return False
    logger.info(f"Generated {len(embeddings)} valid embeddings")

    valid_indices = validate_embeddings(embeddings)
    if len(valid_indices) != len(embeddings):
        logger.warning(f"Filtering out {len(embeddings) - len(valid_indices)} invalid embeddings")
        embeddings = [embeddings[i] for i in valid_indices]
        doc_metadata = [doc_metadata[i] for i in valid_indices]

    try:
        embeddings_array = np.array(embeddings).astype("float32")
        logger.info(f"Embeddings shape: {embeddings_array.shape}")
    except Exception as e:
        logger.error(f"Error converting embeddings to numpy array: {e}")
        return False

    try:
        d = embeddings_array.shape[1]
        faiss.normalize_L2(embeddings_array)
        index = faiss.IndexFlatIP(d)
        index.add(embeddings_array)
        logger.info(f"FAISS index created with {index.ntotal} vectors")
    except Exception as e:
        logger.error(f"Error creating FAISS index: {e}")
        return False

    try:
        faiss.write_index(index, "ipc_index.faiss")
        id_mapping = [meta["id"] for meta in doc_metadata]
        with open("ipc_id_mapping.json", "w", encoding="utf-8") as f:
            json.dump(id_mapping, f, ensure_ascii=False, indent=2)
        with open("ipc_metadata.json", "w", encoding="utf-8") as f:
            json.dump(doc_metadata, f, ensure_ascii=False, indent=2)
        logger.info("FAISS index and metadata saved successfully")
        sections = [meta["section"] for meta in doc_metadata if meta["section"]]
        logger.info("Index Statistics:")
        logger.info(f"   - Total documents indexed: {len(doc_metadata)}")
        logger.info(f"   - Sections with numbers: {len(sections)}")
        logger.info(f"   - Average text length: {np.mean([meta['text_length'] for meta in doc_metadata]):.1f} chars")
        logger.info(f"   - Embedding dimension: {d}")
        return True
    except Exception as e:
        logger.error(f"Error saving FAISS index: {e}")
        return False

def test_index():
    """Test the created index with sample queries"""
    try:
        logger.info("Testing the created index...")
        index = faiss.read_index("ipc_index.faiss")
        with open("ipc_id_mapping.json", "r", encoding="utf-8") as f:
            id_mapping = json.load(f)
        test_queries = [
            "murder",
            "theft",
            "section 302",
            "kidnapping",
            "fraud"
        ]
        for query in test_queries:
            query_embedding = get_embedding(query)
            if query_embedding is not None:
                query_vec = query_embedding.reshape(1, -1)
                faiss.normalize_L2(query_vec)
                distances, indices = index.search(query_vec, 3)
                logger.info(f"\nQuery: '{query}'")
                for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                    if idx != -1 and idx < len(id_mapping):
                        doc_id = id_mapping[idx]
                        doc = ipc_collection.find_one({"_id": ObjectId(doc_id)}) if ObjectId else None
                        section = doc.get("Section", "N/A") if doc else "N/A"
                        title = doc.get("section_title", "N/A") if doc else "N/A"
                        logger.info(f"   {i+1}. Section {section}: {title} (similarity: {dist:.3f})")
        logger.info("Index testing completed")
    except Exception as e:
        logger.error(f"Error testing index: {e}")

if __name__ == "__main__":
    success = create_faiss_index()
    if success:
        logger.info("FAISS index creation completed successfully")
        try:
            from bson import ObjectId
            test_index()
        except ImportError:
            logger.info("Skipping index test (bson not available)")
    else:
        logger.error("FAISS index creation failed")
        exit(1)
