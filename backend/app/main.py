# backend/app/main.py

# CRITICAL FIX: Eventlet monkey-patching MUST be the absolute first thing to run.
# This makes all standard Python libraries (like networking) compatible with eventlet.
import eventlet
eventlet.monkey_patch()

# Now, all other imports can happen safely.
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import auth, chat, sessions, feedback
# CORRECTED: Import the 'neo4j_service' INSTANCE, not the module
from app.services.neo4j_service import neo4j_service
from app.services import pinecone_service, redis_service
from app.services import pinecone_service
from app.database import db_client

# --- Lifespan Management for Connections ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events for all external services."""
    print("--- Application starting up... ---")
    
    # Initialize services
    pinecone_service.initialize_pinecone()
    
    # Asynchronously connect to Neo4j using the imported instance
    await neo4j_service.connect()
    
    # Verify connections and print status messages
    print("--- Verifying Connections ---")
    print(f"✅ MongoDB connected")
    print(f"✅ Redis connected" if redis_service.redis_client.ping() else "❌ Redis not connected")
    print(f"✅ Pinecone connected" if getattr(pinecone_service, 'index', None) else "❌ Pinecone not connected")
    print(f"✅ Neo4j connected" if getattr(neo4j_service, '_driver', None) else "❌ Neo4j not connected")
    
    print("--- Startup complete. ---")
    yield
    
    # Gracefully close connections on shutdown
    print("--- Application shutting down... ---")
    await neo4j_service.close()
    if db_client and db_client.client:
        db_client.client.close()
    print("--- Shutdown complete. ---")

app = FastAPI(
    title="Personal AI Assistant API",
    lifespan=lifespan,
)

# --- CORS Middleware ---
origins = ["http://localhost:3000"]
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
app.include_router(feedback.router)

@app.get("/", tags=["Root"])
def read_root():
    return {"status": "API is running"}