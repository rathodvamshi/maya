# backend/app/routers/chat.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo.collection import Collection
from bson import ObjectId, errors
from datetime import datetime
from typing import Optional, List

# -----------------------------------------------------
# Security & Services Imports
# -----------------------------------------------------
from app.security import get_current_active_user
from app.services import ai_service, pinecone_service
from app.services.neo4j_service import neo4j_service
from app.services.redis_cache import redis_service
from app.database import (
    get_sessions_collection,
    get_tasks_collection,
    get_chat_log_collection
)

# -----------------------------------------------------
# Router Setup
# -----------------------------------------------------
router = APIRouter(prefix="/api/chat", tags=["Chat"])

# =====================================================
# Pydantic Models
# =====================================================
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
# Session-Based Chat Endpoints
# =====================================================
@router.post("/new", response_model=NewChatResponse)
async def start_new_chat(
    request: NewChatRequest,
    current_user: dict = Depends(get_current_active_user),
    sessions: Collection = Depends(get_sessions_collection)
):
    # 1️⃣ Ensure user exists in the Neo4j knowledge graph
    neo4j_service.create_user_node(user_id=current_user["_id"])

    # 2️⃣ Retrieve context via semantic search
    context_summary = pinecone_service.query_relevant_summary(request.message)

    # 3️⃣ Initialize state
    current_state = "initial_greeting"

    # 4️⃣ Generate AI response
    ai_response_text = ai_service.get_response(
        prompt=request.message,
        context=context_summary,
        state=current_state
    )

    # 5️⃣ Save session in MongoDB
    user_message = {"sender": "user", "text": request.message}
    ai_message = {"sender": "assistant", "text": ai_response_text}
    new_session_data = {
        "userId": current_user["_id"],
        "title": request.message[:50],
        "createdAt": datetime.utcnow(),
        "lastUpdatedAt": datetime.utcnow(),
        "isArchived": False,
        "messages": [user_message, ai_message]
    }
    result = sessions.insert_one(new_session_data)
    session_id = str(result.inserted_id)

    # 6️⃣ Set next state in Redis
    next_state = "general_conversation"
    redis_service.set_session_state(session_id, next_state)

    return {"session_id": session_id, "response_text": ai_response_text}


@router.post("/{session_id}", response_model=ContinueChatResponse)
async def continue_chat(
    session_id: str,
    request: ChatMessage,
    current_user: dict = Depends(get_current_active_user),
    sessions: Collection = Depends(get_sessions_collection)
):
    # Validate session ID
    try:
        session_obj_id = ObjectId(session_id)
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session ID format.")

    # Fetch session and validate ownership
    session = sessions.find_one({"_id": session_obj_id, "userId": current_user["_id"]})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Retrieve current state from Redis
    current_state = redis_service.get_session_state(session_id)

    # Get last 10 messages for short-term context
    recent_history = session.get("messages", [])[-10:]

    # Generate AI response
    ai_response_text = ai_service.get_response(
        prompt=request.message,
        history=recent_history,
        state=current_state
    )

    # Determine next state
    next_state = "general_conversation"
    redis_service.set_session_state(session_id, next_state)

    # Save messages to MongoDB atomically
    user_message = {"sender": "user", "text": request.message}
    ai_message = {"sender": "assistant", "text": ai_response_text}
    sessions.update_one(
        {"_id": session_obj_id},
        {
            "$push": {"messages": {"$each": [user_message, ai_message]}},
            "$set": {"lastUpdatedAt": datetime.utcnow()}
        }
    )

    return {"response_text": ai_response_text}


# =====================================================
# Task Management Endpoints
# =====================================================
@router.post("/tasks")
async def create_task(
    task: TaskCreate,
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection)
):
    user_email = current_user["email"]
    new_task = {
        "email": user_email,
        "content": task.content,
        "due_date_str": task.due_date,
        "status": "pending",
        "created_at": datetime.utcnow()
    }
    result = tasks.insert_one(new_task)
    return {"status": "success", "task_id": str(result.inserted_id)}


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    task: TaskUpdate,
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection)
):
    user_email = current_user["email"]
    update_data = task.model_dump(exclude_unset=True)
    if "due_date" in update_data:
        update_data["due_date_str"] = update_data.pop("due_date")
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided to update.")

    try:
        result = tasks.update_one({"_id": ObjectId(task_id), "email": user_email}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"status": "success"}
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid task ID.")


@router.put("/tasks/{task_id}/done")
async def mark_task_done(
    task_id: str,
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection)
):
    user_email = current_user["email"]
    try:
        result = tasks.update_one({"_id": ObjectId(task_id), "email": user_email}, {"$set": {"status": "done"}})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"status": "success"}
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid task ID.")


@router.get("/tasks")
async def get_tasks(
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection)
):
    user_email = current_user["email"]
    cursor = tasks.find({"email": user_email, "status": "pending"}).sort("created_at", -1)
    return [{"id": str(t["_id"]), "content": t["content"], "due_date": t.get("due_date_str")} for t in cursor]


@router.get("/tasks/history")
async def get_task_history(
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection)
):
    user_email = current_user["email"]
    cursor = tasks.find({"email": user_email, "status": "done"}).sort("created_at", -1).limit(10)
    return [{"id": str(t["_id"]), "content": t["content"], "due_date": t.get("due_date_str")} for t in cursor]


# =====================================================
# Legacy Chat History Endpoints
# =====================================================
@router.get("/history")
async def get_chat_history(
    current_user: dict = Depends(get_current_active_user),
    chat_logs: Collection = Depends(get_chat_log_collection),
    limit: int = 50
):
    user_email = current_user["email"]
    cursor = chat_logs.find({"email": user_email}).sort("timestamp", 1).limit(limit)
    return [{"sender": m["sender"], "text": m["text"]} for m in cursor]


@router.delete("/history/clear")
async def clear_chat_history(
    current_user: dict = Depends(get_current_active_user),
    chat_logs: Collection = Depends(get_chat_log_collection)
):
    user_email = current_user["email"]
    result = chat_logs.delete_many({"email": user_email})
    redis_service.redis_client.delete(user_email)
    return {"status": "success", "message": f"Deleted {result.deleted_count} messages from legacy chat log."}
