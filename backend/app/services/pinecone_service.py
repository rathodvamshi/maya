# backend/app/services/pinecone_service.py

import logging
from pinecone import Pinecone, ServerlessSpec
from app.config import settings
# We need to import the function here to avoid circular dependencies
from app.services.embedding_service import create_embedding

logger = logging.getLogger(__name__)

# --- EFFICIENT SINGLETON PATTERN ---
# Global variables to hold the single client and index instance.
pc: Pinecone | None = None
index = None
PINECONE_INDEX_NAME = "maya2-session-memory"
REQUIRED_DIMENSION = 1536
# ------------------------------------

def initialize_pinecone():
    """
    Initializes the Pinecone client and index. This function is called
    once on application startup from main.py.
    """
    global pc, index
    if not settings.PINECONE_API_KEY:
        logger.warning("⚠️ Pinecone API key not found. Pinecone service will be disabled.")
        return

    try:
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        
        if PINECONE_INDEX_NAME not in pc.list_indexes().names():
            logger.info(f"📌 Creating Pinecone index '{PINECONE_INDEX_NAME}'...")
            pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=REQUIRED_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=settings.PINECONE_ENVIRONMENT),
            )
            logger.info("✅ Index created successfully.")
        else:
            logger.info(f"✅ Pinecone index '{PINECONE_INDEX_NAME}' already exists.")
        
        index = pc.Index(PINECONE_INDEX_NAME)
        logger.info(f"✅ Bound to Pinecone index '{PINECONE_INDEX_NAME}'.")

    except Exception as e:
        logger.error(f"❌ Error initializing Pinecone index: {e}")
        pc = None
        index = None

def upsert_session_summary(session_id: str, summary: str):
    """Upserts a session summary embedding into Pinecone."""
    if not index:
        logger.warning("⚠️ Pinecone index not initialized. Skipping upsert.")
        return
    try:
        embedding = create_embedding(summary)
        if embedding:
            index.upsert(vectors=[(session_id, embedding, {"summary": summary})])
            logger.info(f"✅ Upserted summary for session {session_id}.")
    except Exception as e:
        logger.error(f"❌ Failed to upsert summary: {e}")

def query_relevant_summary(text: str, top_k: int = 1) -> str | None:
    """Finds the most relevant summary for a given text."""
    if not index:
        logger.warning("⚠️ Pinecone index not initialized. Cannot query.")
        return None
    try:
        embedding = create_embedding(text)
        if not embedding: return None # Guard clause if embedding fails
        
        results = index.query(vector=embedding, top_k=top_k, include_metadata=True)
        if results.get("matches"):
            best = results["matches"][0]
            if best.get("score", 0) > 0.75:
                return best["metadata"]["summary"]
        return None
    except Exception as e:
        logger.error(f"❌ Query to Pinecone failed: {e}")
        return None