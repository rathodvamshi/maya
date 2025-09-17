# backend/app/routers/chat.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo.collection import Collection
from bson import ObjectId, errors
from datetime import datetime
from typing import Optional
import json
import re

# -----------------------------
# Security & Services Imports
# -----------------------------
from app.security import get_current_active_user
from app.services import ai_service, pinecone_service, redis_service
from app.services.neo4j_service import neo4j_service
from app.database import (
    get_sessions_collection,
    get_tasks_collection,
    get_chat_log_collection,
)
# NEW: Import BOTH Celery tasks
from app.celery_worker import prefetch_destination_info_task, extract_and_store_facts_task

# -----------------------------
# Router Setup
# -----------------------------
router = APIRouter(prefix="/api/chat", tags=["Chat"])

# -----------------------------
# Pydantic Models
# -----------------------------
class ChatMessage(BaseModel):
    message: str

class TaskCreate(BaseModel):
    content: str
    due_date: str

class TaskUpdate(BaseModel):
    content: Optional[str] = None
    due_date: Optional[str] = None

class NewChatRequest(BaseModel):
    message: str

class NewChatResponse(BaseModel):
    session_id: str
    response_text: str

class ContinueChatResponse(BaseModel):
    response_text: str

# =====================================================
# 🔹 Intent Detection (Simple Rule-Based)
# =====================================================
def _detect_intent_and_entities(message: str) -> dict:
    """
    Detects basic intents (e.g., planning trips) and extracts entities.
    Extendable to ML-based NLU in future.
    """
    trip_patterns = [
        r"(?:plan|organize|book|take)\s+(?:a\s+)?(?:trip|vacation|journey)\s+to\s+([\w\s]+)",
        r"(?:go|travel)\s+to\s+([\w\s]+)",
        r"let'?s\s+go\s+to\s+([\w\s]+)"
    ]
    for pattern in trip_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            destination = match.group(1).strip()
            return {"intent": "PLAN_TRIP", "entities": {"destination": destination}}
    return {"intent": "GENERAL_INQUIRY", "entities": {}}

# =====================================================
# 🔹 Unified Context Gathering
# =====================================================
async def _gather_context(user_id: str, message: str) -> dict:
    """
    Retrieves all relevant context for the AI:
    - Semantic context from Pinecone
    - Structured facts from Neo4j
    """
    pinecone_context = pinecone_service.query_relevant_summary(message)
    neo4j_facts = neo4j_service.get_user_facts(user_id)
    return {
        "pinecone_context": pinecone_context,
        "neo4j_facts": neo4j_facts
    }

# =====================================================
# 🔹 Start New Chat Session
# =====================================================
@router.post("/new", response_model=NewChatResponse)
async def start_new_chat(
    request: NewChatRequest,
    current_user: dict = Depends(get_current_active_user),
    sessions: Collection = Depends(get_sessions_collection),
):
    """
    Starts a new chat session:
    1️⃣ Ensures user exists in Neo4j.
    2️⃣ Gathers Pinecone and Neo4j context.
    3️⃣ Generates AI response using the master system prompt.
    4️⃣ Saves session in MongoDB & initializes Redis session state.
    """
    user_id = str(current_user["_id"])

    # Ensure user node exists in Neo4j
    neo4j_service.create_user_node(user_id)

    # Gather all context
    context = await _gather_context(user_id, request.message)

    # Initial state
    current_state = "initial_greeting"

    # Generate AI response
    ai_response_text = ai_service.get_response(
        prompt=request.message,
        state=current_state,
        pinecone_context=context["pinecone_context"],
        neo4j_facts=context["neo4j_facts"]
    )

    # Save session in MongoDB
    user_message = {"sender": "user", "text": request.message}
    ai_message = {"sender": "assistant", "text": ai_response_text}
    session_data = {
        "userId": current_user["_id"],  # Keep as ObjectId for MongoDB
        "title": request.message[:50],
        "createdAt": datetime.utcnow(),
        "lastUpdatedAt": datetime.utcnow(),
        "isArchived": False,
        "messages": [user_message, ai_message],
    }
    result = sessions.insert_one(session_data)
    session_id = str(result.inserted_id)

    # Initialize Redis session state
    redis_service.set_session_state(session_id, "general_conversation")

    # --- NEW: Dispatch real-time fact extraction task ---
    extract_and_store_facts_task.delay(
        user_message=request.message,
        assistant_message=ai_response_text,
        user_id=user_id
    )

    return {"session_id": session_id, "response_text": ai_response_text}

# =====================================================
# 🔹 Continue Existing Chat Session
# =====================================================
@router.post("/{session_id}", response_model=ContinueChatResponse)
async def continue_chat(
    session_id: str,
    request: ChatMessage,
    current_user: dict = Depends(get_current_active_user),
    sessions: Collection = Depends(get_sessions_collection),
):
    """
    Continues a chat session with full context:
    - Short-term history (last 10 messages)
    - Redis session state
    - Pinecone & Neo4j memory
    - Intent detection & proactive prefetch tasks
    """
    user_id = str(current_user["_id"])

    # Validate session ID
    try:
        session_obj_id = ObjectId(session_id)
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session ID format.")

    # Fetch session & validate ownership
    session = sessions.find_one({"_id": session_obj_id, "userId": current_user["_id"]})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Retrieve Redis state
    current_state = redis_service.get_session_state(session_id)

    # Recent chat history (short-term memory)
    recent_history = session.get("messages", [])[-10:]

    # Prefetched context (if planning trip)
    prefetched_context = None
    if current_state == "planning_trip":
        cache_key = f"prefetched_info:{session_id}"
        prefetched_data = redis_service.get_prefetched_data(cache_key)
        if prefetched_data:
            prefetched_context = f"Here is some relevant information: {json.dumps(prefetched_data)}"

    # Gather all context from memory sources
    context = await _gather_context(user_id, request.message)

    # Generate AI response using full context
    ai_response_text = ai_service.get_response(
        prompt=request.message,
        history=recent_history,
        state=current_state,
        pinecone_context=context["pinecone_context"] or prefetched_context,
        neo4j_facts=context["neo4j_facts"]
    )

    # Intent detection & proactive prefetch
    detected = _detect_intent_and_entities(request.message)
    next_state = current_state
    if detected["intent"] == "PLAN_TRIP":
        next_state = "planning_trip"
        destination = detected["entities"].get("destination")
        if destination:
            prefetch_destination_info_task.delay(destination, session_id)

    # Update Redis session state
    redis_service.set_session_state(session_id, next_state)

    # Save messages in MongoDB
    user_message = {"sender": "user", "text": request.message}
    ai_message = {"sender": "assistant", "text": ai_response_text}
    sessions.update_one(
        {"_id": session_obj_id},
        {
            "$push": {"messages": {"$each": [user_message, ai_message]}},
            "$set": {"lastUpdatedAt": datetime.utcnow()},
        },
    )

    # --- NEW: Dispatch real-time fact extraction task ---
    extract_and_store_facts_task.delay(
        user_message=request.message,
        assistant_message=ai_response_text,
        user_id=user_id
    )

    return {"response_text": ai_response_text}

# =====================================================
# 🔹 Task Management Endpoints
# =====================================================
@router.post("/tasks")
async def create_task(
    task: TaskCreate,
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection),
):
    """Create a new pending task for the user."""
    new_task = {
        "email": current_user["email"],
        "content": task.content,
        "due_date_str": task.due_date,
        "status": "pending",
        "created_at": datetime.utcnow(),
    }
    result = tasks.insert_one(new_task)
    return {"status": "success", "task_id": str(result.inserted_id)}

@router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    task: TaskUpdate,
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection),
):
    """Update task content or due date."""
    update_data = task.model_dump(exclude_unset=True)
    if "due_date" in update_data:
        update_data["due_date_str"] = update_data.pop("due_date")
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided to update.")
    try:
        result = tasks.update_one(
            {"_id": ObjectId(task_id), "email": current_user["email"]},
            {"$set": update_data},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"status": "success"}
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid task ID.")

@router.put("/tasks/{task_id}/done")
async def mark_task_done(
    task_id: str,
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection),
):
    """Mark a pending task as completed."""
    try:
        result = tasks.update_one(
            {"_id": ObjectId(task_id), "email": current_user["email"]},
            {"$set": {"status": "done"}},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"status": "success"}
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid task ID.")

@router.get("/tasks")
async def get_tasks(
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection),
):
    """Fetch all pending tasks for the user."""
    cursor = tasks.find({"email": current_user["email"], "status": "pending"}).sort(
        "created_at", -1
    )
    return [
        {"id": str(t["_id"]), "content": t["content"], "due_date": t.get("due_date_str")}
        for t in cursor
    ]

@router.get("/tasks/history")
async def get_task_history(
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection),
):
    """Fetch recently completed tasks (limit 10)."""
    cursor = tasks.find({"email": current_user["email"], "status": "done"}).sort(
        "created_at", -1
    ).limit(10)
    return [
        {"id": str(t["_id"]), "content": t["content"], "due_date": t.get("due_date_str")}
        for t in cursor
    ]

# =====================================================
# 🔹 Legacy Chat History Endpoints
# =====================================================
@router.get("/history")
async def get_chat_history(
    current_user: dict = Depends(get_current_active_user),
    chat_logs: Collection = Depends(get_chat_log_collection),
    limit: int = 50,
):
    """Retrieve the last `limit` chat messages from the user's legacy chat log."""
    cursor = chat_logs.find({"email": current_user["email"]}).sort("timestamp", -1).limit(limit)
    return [{"sender": m["sender"], "text": m["text"]} for m in cursor]

@router.delete("/history/clear")
async def clear_chat_history(
    current_user: dict = Depends(get_current_active_user),
    chat_logs: Collection = Depends(get_chat_log_collection),
):
    """Clear all legacy chat history for the user and delete Redis session state."""
    result = chat_logs.delete_many({"email": current_user["email"]})
    redis_service.redis_client.delete(current_user["email"])
    return {
        "status": "success",
        "message": f"Deleted {result.deleted_count} messages from legacy chat log.",
    }