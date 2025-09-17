# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import auth, chat, sessions
from app.services import pinecone_service # Import the service

# --- NEW: Lifespan Management ---
# This is the modern way to handle startup and shutdown events in FastAPI.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on application startup
    print("--- Application starting up... ---")
    pinecone_service.initialize_pinecone()
    print("--- Startup complete. ---")
    yield
    # Code to run on application shutdown
    print("--- Application shutting down... ---")

# Pass the lifespan manager to the FastAPI app
app = FastAPI(
    title="Personal AI Assistant API",
    lifespan=lifespan
)

# ======================================================
# CORS CONFIGURATION
# ======================================================
origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================
# ROUTERS
# ======================================================
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(sessions.router)

# ======================================================
# ROOT ENDPOINT
# ======================================================
@app.get("/", tags=["Root"])
def read_root():
    """Simple endpoint to confirm API is running."""
    return {"status": "API is running"}