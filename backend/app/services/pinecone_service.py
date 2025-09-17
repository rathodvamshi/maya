# backend/app/services/pinecone_service.py

import logging
from pinecone import Pinecone, ServerlessSpec
from app.config import settings
from app.services.embedding_service import create_embedding

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 Singleton Pinecone Client & Index
# =====================================================
pc: Pinecone | None = None
index = None
PINECONE_INDEX_NAME = "maya2-session-memory"
REQUIRED_DIMENSION = 1536

# =====================================================
# 🔹 Initialize Pinecone
# =====================================================
def initialize_pinecone():
    """
    Initializes the Pinecone client and index.
    Call this once at app startup (e.g., in main.py).
    """
    global pc, index
    if not settings.PINECONE_API_KEY:
        logger.warning("⚠️ Pinecone API key not found. Pinecone service disabled.")
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
        logger.error(f"❌ Error initializing Pinecone: {e}")
        pc = None
        index = None

# =====================================================
# 🔹 Internal Helper: Ensure Index Ready
# =====================================================
def _ensure_index_ready():
    if index is None:
        logger.warning("⚠️ Pinecone index not initialized. Attempting initialization...")
        initialize_pinecone()
    return index is not None

# =====================================================
# 🔹 Upsert Session Summary
# =====================================================
def upsert_session_summary(session_id: str, summary: str):
    """
    Upserts a session summary embedding into Pinecone.
    """
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
    """
    Finds the most relevant summary for a given text.
    Returns None if no sufficiently relevant match.
    """
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
            if best.get("score", 0) > 0.75:  # Only return high-confidence matches
                return best["metadata"]["summary"]
        return None
    except Exception as e:
        logger.error(f"❌ Query to Pinecone failed: {e}")
        return None
