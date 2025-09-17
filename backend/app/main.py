# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import auth, chat, sessions
from app.services import pinecone_service, neo4j_service # Import both services

# --- Lifespan Management for Connections ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on application startup
    print("--- Application starting up... ---")
    pinecone_service.initialize_pinecone()
    # The neo4j_service is already initialized when imported, so it's ready.
    print("--- Startup complete. ---")
    yield
    # Code to run on application shutdown
    print("--- Application shutting down... ---")
    neo4j_service.close() # Gracefully close the Neo4j connection

app = FastAPI(
    title="Personal AI Assistant API",
    lifespan=lifespan
)

# ... (Keep your CORS CONFIGURATION, ROUTERS, and ROOT ENDPOINT exactly the same) ...
origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(sessions.router)

@app.get("/", tags=["Root"])
def read_root():
    return {"status": "API is running"}