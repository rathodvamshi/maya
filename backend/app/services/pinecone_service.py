# backend/app/services/pinecone_service.py

from pinecone import Pinecone, ServerlessSpec
from app.config import settings
from app.services import embedding_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- EFFICIENT SINGLETON PATTERN ---
try:
    if settings.PINECONE_API_KEY:
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        PINECONE_INDEX_NAME = "maya2-session-memory"
        index = None 
    else:
        pc = None
        index = None
        logger.warning("Pinecone API key not found. Pinecone service will be disabled.")
except Exception as e:
    pc = None
    index = None
    logger.error(f"Failed to initialize Pinecone client: {e}")
# ------------------------------------

def initialize_pinecone():
    """
    Initializes the Pinecone index on application startup.
    - Checks if the index exists.
    - If not, it creates a new index with the CORRECT dimensions.
    """
    global index
    if not pc:
        logger.error("Cannot initialize Pinecone index because client is not available.")
        return

    # FIXED: The dimension for 'text-embedding-3-small' is 1536.
    required_dimension = 1536

    try:
        if PINECONE_INDEX_NAME not in pc.list_indexes().names():
            logger.info(f"Creating Pinecone index: '{PINECONE_INDEX_NAME}' with dimension {required_dimension}...")
            
            pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=required_dimension, # Use the correct dimension
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=settings.PINECONE_ENVIRONMENT)
            )
            logger.info("Index created successfully.")
        else:
            logger.info(f"Pinecone index '{PINECONE_INDEX_NAME}' already exists.")
        
        index = pc.Index(PINECONE_INDEX_NAME)

    except Exception as e:
        logger.error(f"An error occurred during Pinecone index initialization: {e}")

# ... (The rest of the file remains the same as the previous version) ...

def upsert_session_summary(session_id: str, summary: str):
    """Upserts a session summary embedding into Pinecone."""
    if not index:
        logger.error("Pinecone index is not initialized. Cannot upsert.")
        return
        
    embedding = embedding_service.create_embedding(summary)
    metadata = {"summary": summary}
    index.upsert(vectors=[(session_id, embedding, metadata)])
    logger.info(f"Upserted summary for session {session_id} to Pinecone.")

def query_relevant_summary(text: str, top_k: int = 1) -> str | None:
    """Finds the most semantically similar summary from Pinecone."""
    if not index:
        logger.error("Pinecone index is not initialized. Cannot query.")
        return None

    query_embedding = embedding_service.create_embedding(text)
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )
    
    if results['matches']:
        best_match = results['matches'][0]
        if best_match['score'] > 0.75:
            logger.info(f"Found relevant summary with score: {best_match['score']:.2f}")
            return best_match['metadata']['summary']
            
    logger.info("No relevant summary found above the similarity threshold.")
    return None