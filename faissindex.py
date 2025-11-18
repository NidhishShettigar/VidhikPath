import faiss
import numpy as np
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
import json
import re
from typing import List, Dict, Tuple
import logging
from tqdm import tqdm
import pickle
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MongoDB Connection
try:
    client = MongoClient("mongodb+srv://vidhikpath:vidhikpath@cluster0.m2j80to.mongodb.net/")
    db = client["vidhikpath"]
    bns_collection = db["bns"]
    ipc_collection = db["ipc"]
    logger.info("Connected to MongoDB")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    exit(1)

# Use best multilingual model for Indian legal context
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
# Alternative: "BAAI/bge-m3" (better quality, slightly slower)

try:
    model = SentenceTransformer(MODEL_NAME)
    model.max_seq_length = 512  # Longer context for legal text
    logger.info(f"Loaded model: {MODEL_NAME}")
except Exception as e:
    logger.error(f"Model loading failed: {e}")
    exit(1)

CACHE_DIR = Path("./cache")
CACHE_DIR.mkdir(exist_ok=True)
EMBEDDINGS_CACHE = CACHE_DIR / "embeddings_cache_v2.pkl"

# Legal term normalization dictionary
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

def advanced_text_preprocessing(text: str) -> str:
    """
    Advanced preprocessing specifically for legal text
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Normalize legal terms
    for abbr, full in LEGAL_TERM_MAPPING.items():
        text = re.sub(r'\b' + re.escape(abbr) + r'\b', full, text)
    
    # Normalize section references (e.g., "Sec. 302" -> "section 302")
    text = re.sub(r'\bsec\.?\s*(\d+)', r'section \1', text)
    text = re.sub(r'\bsection\s*\.?\s*(\d+)', r'section \1', text)
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Remove special characters but keep legal punctuation
    text = re.sub(r'[^\w\s\-\.\,\;\:\(\)\[\]/]', ' ', text)
    
    # Normalize numbers in parentheses (common in legal text)
    text = re.sub(r'\(\s*(\d+)\s*\)', r'(\1)', text)
    
    return text.strip()

def create_hierarchical_text_representation(doc: Dict, source: str) -> str:
    """
    Create rich text representation with hierarchical structure
    Optimized for both BNS and IPC schemas
    """
    parts = []
    
    # Handle BNS schema
    if source == "bns":
        chapter = str(doc.get('Chapter', '')).strip()
        chapter_name = str(doc.get('Chapter_name', '')).strip()
        section = str(doc.get('Section', '')).strip()
        section_name = str(doc.get('Section_name', '')).strip()
        description = str(doc.get('Description', '')).strip()
        
        # Build structured representation
        if section:
            parts.append(f"BNS Section {section}")
        if section_name:
            parts.append(section_name)
        if chapter and chapter_name:
            parts.append(f"Chapter {chapter}: {chapter_name}")
        if description:
            # Include full description for better context
            parts.append(description[:1000])  # Increased from 300
    
    # Handle IPC schema
    elif source == "ipc":
        chapter = str(doc.get('chapter', '')).strip()
        chapter_title = str(doc.get('chapter_title', '')).strip()
        section = str(doc.get('Section', '')).strip()
        section_title = str(doc.get('section_title', '')).strip()
        section_desc = str(doc.get('section_desc', '')).strip()
        
        if section:
            parts.append(f"IPC Section {section}")
        if section_title:
            parts.append(section_title)
        if chapter and chapter_title:
            parts.append(f"Chapter {chapter}: {chapter_title}")
        if section_desc:
            parts.append(section_desc[:1000])
    
    return ' '.join(filter(None, parts))

def create_embeddings_with_chunking(texts: List[str], batch_size: int = 16) -> np.ndarray:
    """
    Create embeddings with proper batching and error handling
    """
    embeddings = []
    
    for i in tqdm(range(0, len(texts), batch_size), desc="Encoding batches"):
        batch = texts[i:i + batch_size]
        try:
            batch_embeddings = model.encode(
                batch,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            embeddings.append(batch_embeddings)
        except Exception as e:
            logger.error(f"Error encoding batch {i}: {e}")
            # Fallback: encode one by one
            for text in batch:
                try:
                    emb = model.encode([text], normalize_embeddings=True)[0]
                    embeddings.append(emb.reshape(1, -1))
                except:
                    # If still fails, use zero vector
                    embeddings.append(np.zeros((1, model.get_sentence_embedding_dimension())))
    
    return np.vstack(embeddings)

def load_or_create_embeddings(docs: List[Dict], source: str) -> Tuple[np.ndarray, List[Dict]]:
    """
    Load cached embeddings or create new ones
    """
    cache_file = CACHE_DIR / f"embeddings_{source}_v2.pkl"
    
    # Check cache
    if cache_file.exists():
        logger.info(f"Loading cached embeddings for {source}...")
        try:
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
                if len(cached_data['embeddings']) == len(docs):
                    logger.info(f"Loaded {len(cached_data['embeddings'])} cached embeddings")
                    return cached_data['embeddings'], cached_data['metadata']
        except Exception as e:
            logger.warning(f"Cache load failed: {e}, regenerating...")
    
    # Generate new embeddings
    logger.info(f"Generating embeddings for {source}...")
    texts = []
    metadata = []
    
    for doc in docs:
        text = create_hierarchical_text_representation(doc, source)
        if text:
            # Apply advanced preprocessing
            preprocessed_text = advanced_text_preprocessing(text)
            texts.append(preprocessed_text)
            
            # Create metadata based on source
            if source == "bns":
                metadata.append({
                    "id": str(doc["_id"]),
                    "source": "bns",
                    "section": doc.get("Section", ""),
                    "section_name": doc.get("Section_name", ""),
                    "chapter": doc.get("Chapter", ""),
                    "chapter_name": doc.get("Chapter_name", ""),
                    "description": doc.get("Description", "")[:200]
                })
            else:  # ipc
                metadata.append({
                    "id": str(doc["_id"]),
                    "source": "ipc",
                    "section": doc.get("Section", ""),
                    "section_title": doc.get("section_title", ""),
                    "chapter": doc.get("chapter", ""),
                    "chapter_title": doc.get("chapter_title", ""),
                    "description": doc.get("section_desc", "")[:200]
                })
    
    # Create embeddings with batching
    embeddings = create_embeddings_with_chunking(texts)
    
    # Cache for next time
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump({'embeddings': embeddings, 'metadata': metadata}, f)
        logger.info(f"Embeddings cached to {cache_file}")
    except Exception as e:
        logger.warning(f"Failed to cache embeddings: {e}")
    
    return embeddings, metadata

def create_combined_faiss_index():
    """
    Create combined FAISS index for both BNS and IPC
    """
    logger.info("="*60)
    logger.info("Starting Combined FAISS Index Creation")
    logger.info("="*60)
    
    # Fetch documents from both collections
    try:
        bns_docs = list(bns_collection.find({}))
        ipc_docs = list(ipc_collection.find({}))
        logger.info(f"Found {len(bns_docs)} BNS documents")
        logger.info(f"Found {len(ipc_docs)} IPC documents")
        
        if not bns_docs and not ipc_docs:
            logger.error("No documents found in either collection")
            return False
            
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        return False
    
    # Generate embeddings for both datasets
    all_embeddings = []
    all_metadata = []
    
    if bns_docs:
        bns_embeddings, bns_metadata = load_or_create_embeddings(bns_docs, "bns")
        all_embeddings.append(bns_embeddings)
        all_metadata.extend(bns_metadata)
        logger.info(f"Processed {len(bns_metadata)} BNS sections")
    
    if ipc_docs:
        ipc_embeddings, ipc_metadata = load_or_create_embeddings(ipc_docs, "ipc")
        all_embeddings.append(ipc_embeddings)
        all_metadata.extend(ipc_metadata)
        logger.info(f"Processed {len(ipc_metadata)} IPC sections")
    
    # Combine embeddings
    if not all_embeddings:
        logger.error("No valid embeddings generated")
        return False
    
    combined_embeddings = np.vstack(all_embeddings).astype('float32')
    d = combined_embeddings.shape[1]
    n = combined_embeddings.shape[0]
    
    logger.info(f"Combined embeddings shape: {combined_embeddings.shape}")
    
    # Choose optimal index type based on dataset size
    if n < 1000:
        index = faiss.IndexFlatIP(d)
        logger.info("Using IndexFlatIP (exact search)")
    elif n < 10000:
        nlist = min(int(np.sqrt(n)), 100)
        quantizer = faiss.IndexFlatIP(d)
        index = faiss.IndexIVFFlat(quantizer, d, nlist, faiss.METRIC_INNER_PRODUCT)
        index.train(combined_embeddings)
        index.nprobe = min(10, nlist // 2)  # Search more clusters for better recall
        logger.info(f"Using IndexIVFFlat with {nlist} clusters, nprobe={index.nprobe}")
    else:
        index = faiss.IndexHNSWFlat(d, 32, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = 200  # Higher for better quality
        index.hnsw.efSearch = 50  # Higher for better recall
        logger.info("Using IndexHNSWFlat (fast approximate search)")
    
    # Add vectors
    index.add(combined_embeddings)
    logger.info(f"Index created with {index.ntotal} vectors")
    
    # Save index and metadata
    try:
        faiss.write_index(index, "legal_combined_index.faiss")
        
        id_mapping = [meta["id"] for meta in all_metadata]
        with open("legal_id_mapping.json", "w", encoding="utf-8") as f:
            json.dump(id_mapping, f, ensure_ascii=False, indent=2)
        
        with open("legal_metadata.json", "w", encoding="utf-8") as f:
            json.dump(all_metadata, f, ensure_ascii=False, indent=2)
        
        logger.info("="*60)
        logger.info("Index Creation Successful")
        logger.info(f"  - Total documents: {len(all_metadata)}")
        logger.info(f"  - BNS sections: {len([m for m in all_metadata if m['source'] == 'bns'])}")
        logger.info(f"  - IPC sections: {len([m for m in all_metadata if m['source'] == 'ipc'])}")
        logger.info(f"  - Embedding dimension: {d}")
        logger.info(f"  - Index type: {type(index).__name__}")
        logger.info(f"  - Model: {MODEL_NAME}")
        logger.info("="*60)
        
        return True
    except Exception as e:
        logger.error(f"Error saving index: {e}")
        return False

def test_search_quality():
    """
    Test search performance with diverse queries
    """
    try:
        logger.info("\n" + "="*60)
        logger.info("Testing Search Quality")
        logger.info("="*60)
        
        index = faiss.read_index("legal_combined_index.faiss")
        
        with open("legal_id_mapping.json", "r") as f:
            id_mapping = json.load(f)
        
        with open("legal_metadata.json", "r") as f:
            metadata = json.load(f)
        
        test_queries = [
            "murder and death penalty punishment",
            "theft of property",
            "kidnapping children",
            "fraud cheating deception",
            "assault violence physical harm",
            "defamation reputation damage",
            "preliminary provisions definitions",
            "short title commencement",
            "rape sexual assault women",
            "dowry death harassment"
        ]
        
        import time
        total_time = 0
        
        for query in test_queries:
            start = time.time()
            
            # Preprocess query
            processed_query = advanced_text_preprocessing(query)
            
            # Generate query embedding
            query_emb = model.encode([processed_query], normalize_embeddings=True)[0]
            query_vec = query_emb.reshape(1, -1).astype('float32')
            
            # Search
            distances, indices = index.search(query_vec, 5)
            
            elapsed = time.time() - start
            total_time += elapsed
            
            logger.info(f"\nQuery: '{query}' ({elapsed*1000:.2f}ms)")
            logger.info(f"Processed: '{processed_query}'")
            
            for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                if idx != -1 and idx < len(metadata):
                    meta = metadata[idx]
                    source = meta.get('source', 'unknown').upper()
                    section = meta.get('section', 'N/A')
                    
                    if source == "BNS":
                        section_name = meta.get('section_name', 'N/A')
                    else:
                        section_name = meta.get('section_title', 'N/A')
                    
                    logger.info(f"  {i+1}. [{source}] Sec {section}: {section_name[:70]}... (sim: {dist:.3f})")
        
        avg_time = (total_time / len(test_queries)) * 1000
        logger.info(f"\n{'='*60}")
        logger.info(f"Average search time: {avg_time:.2f}ms")
        logger.info(f"{'='*60}")
        
    except Exception as e:
        logger.error(f"Error testing index: {e}")

if __name__ == "__main__":
    success = create_combined_faiss_index()
    
    if success:
        logger.info("\nFAISS index creation completed successfully!")
        test_search_quality()
    else:
        logger.error("\nFAISS index creation failed")
        exit(1)