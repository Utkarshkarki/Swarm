import os
import re
from pathlib import Path
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest")

DATA_DIR = Path(__file__).parent.parent / "data"
LEGAL_DOCS_DIR = DATA_DIR / "legal_docs"
CHROMA_DB_DIR = DATA_DIR / "legal_chroma_db"

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into chunks of `chunk_size` characters with `overlap` characters of overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if not chunk.strip():
            break
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

def extract_clauses(text: str) -> list[str]:
    """Try to split by CLAUSE or SECTION to get semantic chunks."""
    # A basic regex to split by SECTION or CLAUSE, keeping the header
    parts = re.split(r'\n(?=(?:SECTION|CLAUSE|Clause)\s+\d+)', text)
    chunks = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) > 1000:
             # Further chunk long sections
             chunks.extend(chunk_text(p, 800, 100))
        else:
             chunks.append(p)
    return chunks

def main():
    if not LEGAL_DOCS_DIR.exists():
        logger.error(f"Legal docs directory not found at {LEGAL_DOCS_DIR}")
        return

    # Initialize ChromaDB
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    
    # Recreate collection to avoid duplicates during testing
    try:
        chroma_client.delete_collection(name="legal_docs")
    except Exception:
        pass
        
    collection = chroma_client.create_collection(
        name="legal_docs",
        metadata={"hnsw:space": "cosine"}
    )
    
    # Initialize Embedding Model
    logger.info("Loading embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    total_chunks = 0
    
    for txt_file in LEGAL_DOCS_DIR.glob("*.txt"):
        logger.info(f"Processing {txt_file.name}...")
        with open(txt_file, "r", encoding="utf-8") as f:
            content = f.read()
            
        doc_id = txt_file.stem
        
        # Split into semantic chunks
        chunks = extract_clauses(content)
        if not chunks:
            chunks = chunk_text(content, 600, 100)
            
        logger.info(f"  Extracted {len(chunks)} chunks.")
        
        # Prepare for Chroma
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": doc_id, "chunk_index": i} for i in range(len(chunks))]
        
        # Compute embeddings
        logger.info(f"  Computing embeddings for {len(chunks)} chunks...")
        embeddings = model.encode(chunks).tolist()
        
        # Add to Chroma
        collection.add(
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )
        
        total_chunks += len(chunks)
        
    logger.info(f"Successfully ingested {total_chunks} chunks into ChromaDB at {CHROMA_DB_DIR}")

if __name__ == "__main__":
    main()
