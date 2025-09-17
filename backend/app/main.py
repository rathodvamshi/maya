# backend/app/main.py

# CRITICAL FIX: Eventlet monkey-patching must be the absolute first thing to run.
# This makes all standard Python libraries (like networking) compatible with eventlet.
import eventlet
eventlet.monkey_patch()

# Now, all other imports can happen safely.
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import auth, chat, sessions, feedback   # ✅ include feedback
from app.services import pinecone_service, neo4j_service
from app.database import db_client


# --- Lifespan Management for Connections ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events for all external services."""
    print("--- Application starting up... ---")
    
    # Initialize Pinecone
    try:
        pinecone_service.initialize_pinecone()
    except Exception as e:
        print(f"❌ Error initializing Pinecone: {e}")
    
    # Neo4j and Redis are initialized on import, so nothing extra
    print("--- Startup complete. ---")
    yield
    
    # Gracefully close connections on shutdown
    print("--- Application shutting down... ---")
    try:
        neo4j_service.close()
    except Exception as e:
        print(f"❌ Error closing Neo4j: {e}")
    try:
        db_client.client.close()
    except Exception as e:
        print(f"❌ Error closing MongoDB: {e}")
    print("--- Shutdown complete. ---")


# --- FastAPI App ---
app = FastAPI(
    title="Personal AI Assistant API",
    lifespan=lifespan,
)


# --- CORS Middleware ---
origins = ["http://localhost:3000"]  # Add production origins as needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Routers ---
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(feedback.router)   # ✅ add feedback API


# --- Root Endpoint ---
@app.get("/", tags=["Root"])
def read_root():
    return {"status": "API is running"}
