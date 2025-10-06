import faiss
import numpy as np
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
import json
import re
from typing import List, Dict, Optional
import logging
from tqdm import tqdm
import pickle
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB Connection
try:
    client = MongoClient("mongodb+srv://vidhikpath:vidhikpath@cluster0.m2j80to.mongodb.net/")
    db = client["vidhikpath"]
    bns_collection = db["bns"]
    logger.info("Connected to MongoDB")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    exit(1)

# Load efficient embedding model
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # Best balance

try:
    model = SentenceTransformer(MODEL_NAME)
    model.max_seq_length = 256  # Reduce from default 512 for speed
    logger.info(f"Loaded model: {MODEL_NAME}")
except Exception as e:
    logger.error(f"Model loading failed: {e}")
    exit(1)

CACHE_DIR = Path("./cache")
CACHE_DIR.mkdir(exist_ok=True)
EMBEDDINGS_CACHE = CACHE_DIR / "embeddings_cache.pkl"

def clean_text(text: str) -> str:
    """Optimized text cleaning"""
    if not text:
        return ""
    text = ' '.join(text.split())  # Faster than regex for whitespace
    text = re.sub(r'[^\w\s\-\.\,\;\:\(\)\[\]]', ' ', text)
    text = text.lower()
    text = text.replace('sec.', 'section').replace('sec ', 'section ')
    return text.strip()

def create_text_representation(doc: Dict) -> str:
    """Create text representation matching BNS schema"""
    # BNS schema fields (matching your data)
    chapter = str(doc.get('Chapter', '')).strip()
    chapter_name = str(doc.get('Chapter_name', '')).strip()
    section = str(doc.get('Section', '')).strip()
    section_name = str(doc.get('Section_name', '')).strip()
    description = str(doc.get('Description', '')).strip()
    
    # Build comprehensive text representation
    parts = []
    
    # Add section info (most important)
    if section:
        parts.append(f"BNS Section {section}")
    
    if section_name:
        parts.append(section_name)
    
    # Add chapter context
    if chapter and chapter_name:
        parts.append(f"Chapter {chapter} {chapter_name}")
    
    # Add description (truncated for efficiency)
    if description:
        # Truncate to first 300 chars for better balance
        parts.append(description[:300])
    
    return ' '.join(filter(None, parts))

def load_or_create_embeddings(bns_docs: List[Dict]) -> tuple:
    """Cache embeddings to disk for faster subsequent runs"""
    
    # Check if cache exists and is valid
    if EMBEDDINGS_CACHE.exists():
        logger.info("Loading cached embeddings...")
        try:
            with open(EMBEDDINGS_CACHE, 'rb') as f:
                cached_data = pickle.load(f)
                if len(cached_data['embeddings']) == len(bns_docs):
                    logger.info(f"Loaded {len(cached_data['embeddings'])} cached embeddings")
                    return cached_data['embeddings'], cached_data['metadata']
        except Exception as e:
            logger.warning(f"Cache load failed: {e}, regenerating...")
    
    # Generate new embeddings
    logger.info("Generating embeddings...")
    texts = []
    metadata = []
    
    for doc in bns_docs:
        text = create_text_representation(doc)
        if text:
            texts.append(clean_text(text))
            metadata.append({
                "id": str(doc["_id"]),
                "section": doc.get("Section", ""),
                "section_name": doc.get("Section_name", ""),
                "chapter": doc.get("Chapter", ""),
                "chapter_name": doc.get("Chapter_name", "")
            })
    
    # Batch encoding (much faster than one-by-one)
    logger.info(f"Encoding {len(texts)} documents in batches...")
    embeddings = model.encode(
        texts,
        batch_size=32,  # Adjust based on your RAM
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True  # Pre-normalize for cosine similarity
    )
    
    # Cache for next time
    try:
        with open(EMBEDDINGS_CACHE, 'wb') as f:
            pickle.dump({'embeddings': embeddings, 'metadata': metadata}, f)
        logger.info("Embeddings cached successfully")
    except Exception as e:
        logger.warning(f"Failed to cache embeddings: {e}")
    
    return embeddings, metadata

def create_optimized_faiss_index():
    """Create optimized FAISS index with faster search"""
    logger.info("Starting optimized FAISS index creation...")
    
    # Fetch documents
    try:
        bns_docs = list(bns_collection.find({}))
        logger.info(f"Found {len(bns_docs)} BNS documents")
        
        if not bns_docs:
            logger.error("No documents found in BNS collection")
            return False
        
        # Log sample document structure
        if bns_docs:
            sample = bns_docs[0]
            logger.info(f"Sample document structure:")
            logger.info(f"  - Section: {sample.get('Section')}")
            logger.info(f"  - Section_name: {sample.get('Section_name')}")
            logger.info(f"  - Chapter: {sample.get('Chapter')}")
            logger.info(f"  - Description length: {len(str(sample.get('Description', '')))}")
            
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        return False
    
    # Get or generate embeddings
    embeddings, metadata = load_or_create_embeddings(bns_docs)
    
    if len(embeddings) == 0:
        logger.error("No valid embeddings generated")
        return False
    
    embeddings_array = embeddings.astype('float32')
    d = embeddings_array.shape[1]
    n = embeddings_array.shape[0]
    
    logger.info(f"Embeddings shape: {embeddings_array.shape}")
    
    # Choose index type based on dataset size
    if n < 1000:
        # Small dataset: use exact search
        index = faiss.IndexFlatIP(d)
        logger.info("Using IndexFlatIP (exact search)")
    elif n < 10000:
        # Medium dataset: use IVF with small number of clusters
        nlist = min(100, n // 10)  # Number of clusters
        quantizer = faiss.IndexFlatIP(d)
        index = faiss.IndexIVFFlat(quantizer, d, nlist, faiss.METRIC_INNER_PRODUCT)
        index.train(embeddings_array)
        logger.info(f"Using IndexIVFFlat with {nlist} clusters")
    else:
        # Large dataset: use HNSW for fast approximate search
        index = faiss.IndexHNSWFlat(d, 32, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = 40
        index.hnsw.efSearch = 16
        logger.info("Using IndexHNSWFlat (fast approximate search)")
    
    # Add vectors
    index.add(embeddings_array)
    logger.info(f"Index created with {index.ntotal} vectors")
    
    # Save index and metadata
    try:
        faiss.write_index(index, "bns_index.faiss")
        
        id_mapping = [meta["id"] for meta in metadata]
        with open("bns_id_mapping.json", "w", encoding="utf-8") as f:
            json.dump(id_mapping, f, ensure_ascii=False, indent=2)
        
        with open("bns_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        logger.info("Index and metadata saved successfully")
        logger.info(f"Statistics:")
        logger.info(f"  - Documents indexed: {len(metadata)}")
        logger.info(f"  - Embedding dimension: {d}")
        logger.info(f"  - Index type: {type(index).__name__}")
        
        # Log some section numbers for verification
        sections = [m['section'] for m in metadata[:10] if m['section']]
        logger.info(f"  - Sample sections: {', '.join(sections)}")
        
        return True
    except Exception as e:
        logger.error(f"Error saving index: {e}")
        return False

def test_search_speed():
    """Test search performance"""
    try:
        logger.info("\nTesting search performance...")
        index = faiss.read_index("bns_index.faiss")
        
        with open("bns_id_mapping.json", "r") as f:
            id_mapping = json.load(f)
        
        test_queries = [
            "murder and death penalty",
            "theft of property",
            "kidnapping children",
            "fraud and cheating",
            "assault and violence",
            "preliminary provisions",
            "short title and commencement"
        ]
        
        import time
        total_time = 0
        
        for query in test_queries:
            start = time.time()
            
            # Generate query embedding
            query_emb = model.encode([query], normalize_embeddings=True)[0]
            query_vec = query_emb.reshape(1, -1).astype('float32')
            
            # Search
            distances, indices = index.search(query_vec, 5)
            
            elapsed = time.time() - start
            total_time += elapsed
            
            logger.info(f"\nQuery: '{query}' ({elapsed*1000:.2f}ms)")
            for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                if idx != -1 and idx < len(id_mapping):
                    from bson import ObjectId
                    doc_id = id_mapping[idx]
                    doc = bns_collection.find_one({"_id": ObjectId(doc_id)})
                    if doc:
                        section = doc.get("Section", "N/A")
                        section_name = doc.get("Section_name", "N/A")
                        logger.info(f"  {i+1}. BNS Sec {section}: {section_name[:60]}... (sim: {dist:.3f})")
        
        avg_time = (total_time / len(test_queries)) * 1000
        logger.info(f"\nAverage search time: {avg_time:.2f}ms")
        
    except Exception as e:
        logger.error(f"Error testing index: {e}")

if __name__ == "__main__":
    success = create_optimized_faiss_index()
    
    if success:
        logger.info("\nFAISS index creation completed successfully!")
        try:
            test_search_speed()
        except ImportError:
            logger.info("Skipping test (missing dependencies)")
    else:
        logger.error("FAISS index creation failed")
        exit(1)