import faiss
import torch
import numpy as np
from pymongo import MongoClient
from transformers import AutoTokenizer, AutoModel

# 1. Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["vidhikpath"]
ipc_collection = db["ipc"]

# 2. Load LegalBERT
tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
model = AutoModel.from_pretrained("nlpaueb/legal-bert-base-uncased")

def get_embedding(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    # Use [CLS] token embedding
    return outputs.last_hidden_state[:,0,:].numpy()

# 3. Fetch IPC data
ipc_docs = list(ipc_collection.find({}))
embeddings = []
id_mapping = []

for doc in ipc_docs:
    text = f"{doc['section_title']} - {doc['section_desc']}"
    embedding = get_embedding(text)
    embeddings.append(embedding[0])
    id_mapping.append(str(doc["_id"]))  # store MongoDB ID

embeddings = np.array(embeddings).astype("float32")

# 4. Create FAISS index
d = embeddings.shape[1]  # embedding dimension
index = faiss.IndexFlatL2(d)  # L2 distance
index.add(embeddings)

# 5. Save FAISS index + ID mapping
faiss.write_index(index, "ipc_index.faiss")

import json
with open("ipc_id_mapping.json", "w") as f:
    json.dump(id_mapping, f)

print("✅ FAISS index created and saved!")
