# backend/app/services/pinecone_service.py

import logging
from pinecone import Pinecone, ServerlessSpec
from app.config import settings
from app.services.embedding_service import create_embedding

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 Global Pinecone state
# =====================================================
pc: Pinecone | None = None
index = None
PINECONE_INDEX_NAME = "maya2-session-memory"
# This dimension MUST match your embedding model. Gemini's text-embedding-004 is 768.
REQUIRED_DIMENSION = 768

# =====================================================
# 🔹 Initialize Pinecone
# =====================================================
def initialize_pinecone():
    """
    Initializes the Pinecone client and index. Called once on app startup.
    It will automatically delete and recreate the index if the dimension is wrong.
    """
    global pc, index
    if not settings.PINECONE_API_KEY:
        logger.warning("⚠️ Pinecone API key not found. Pinecone service will be disabled.")
        return

    try:
        # Modern Pinecone client initialization
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        
        # Check if the index exists and has the correct dimension
        if PINECONE_INDEX_NAME in pc.list_indexes().names():
            index_description = pc.describe_index(PINECONE_INDEX_NAME)
            if index_description.dimension != REQUIRED_DIMENSION:
                logger.warning(
                    f"Index '{PINECONE_INDEX_NAME}' has wrong dimension "
                    f"({index_description.dimension}). Deleting and recreating."
                )
                pc.delete_index(PINECONE_INDEX_NAME)
                create_new_index = True
            else:
                logger.info(f"✅ Pinecone index '{PINECONE_INDEX_NAME}' already exists with correct dimension.")
                create_new_index = False
        else:
            create_new_index = True

        if create_new_index:
            logger.info(f"📌 Creating Pinecone index '{PINECONE_INDEX_NAME}' with dimension {REQUIRED_DIMENSION}...")
            pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=REQUIRED_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=settings.PINECONE_ENVIRONMENT),
            )
            logger.info("✅ Index created successfully.")
        
        index = pc.Index(PINECONE_INDEX_NAME)
        logger.info(f"✅ Bound to Pinecone index '{PINECONE_INDEX_NAME}'.")

    except Exception as e:
        logger.error(f"❌ Error initializing Pinecone: {e}")
        pc = None
        index = None

# =====================================================
# 🔹 Internal Helper: Ensure Index Ready
# =====================================================
def _ensure_index_ready():
    """Internal helper to re-attempt initialization if the index is not ready."""
    if index is None:
        logger.warning("⚠️ Pinecone index was not initialized on startup, attempting again...")
        initialize_pinecone()
    return index is not None

# =====================================================
# 🔹 Upsert Session Summary
# =====================================================
def upsert_session_summary(session_id: str, summary: str):
    """Upserts a session summary embedding into Pinecone."""
    if not _ensure_index_ready():
        logger.error("❌ Pinecone index unavailable. Skipping upsert.")
        return
    try:
        embedding = create_embedding(summary)
        if embedding:
            index.upsert(vectors=[(session_id, embedding, {"summary": summary})])
            logger.info(f"✅ Upserted summary for session {session_id}.")
    except Exception as e:
        logger.error(f"❌ Failed to upsert summary: {e}")

# =====================================================
# 🔹 Query Relevant Summary
# =====================================================
def query_relevant_summary(text: str, top_k: int = 1) -> str | None:
    """Finds the most relevant summary for a given text."""
    if not _ensure_index_ready():
        logger.error("❌ Pinecone index unavailable. Cannot query.")
        return None
    try:
        embedding = create_embedding(text)
        if not embedding:
            logger.warning("⚠️ Failed to create embedding for query.")
            return None
        
        results = index.query(vector=embedding, top_k=top_k, include_metadata=True)
        matches = results.get("matches", [])
        if matches:
            best = matches[0]
            if best.get("score", 0) > 0.75:
                return best["metadata"]["summary"]
        return None
    except Exception as e:
        logger.error(f"❌ Query to Pinecone failed: {e}")
        return None

# =====================================================
# 🔹 Singleton-like Export for Compatibility
# =====================================================
class PineconeService:
    initialize_pinecone = staticmethod(initialize_pinecone)
    upsert_session_summary = staticmethod(upsert_session_summary)
    query_relevant_summary = staticmethod(query_relevant_summary)

pinecone_service = PineconeService()
