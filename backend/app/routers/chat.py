# backend/app/routers/chat.py

from fastapi import APIRouter, Depends, HTTPException, status
# FIXED: Imported get_current_active_user, as it's used throughout the file.
from app.security import get_current_active_user
from pydantic import BaseModel
from pymongo.collection import Collection
from bson import ObjectId, errors
from datetime import datetime
from typing import Optional, List

# NOTE: Your imports seem to be a mix of the new session-based logic and older logic.
# This corrected file will make them all work, but you may want to integrate them further later.
from app.services import ai_service, redis_cache, nlu, pinecone_service
from app.database import get_user_profile_collection, get_chat_log_collection, get_tasks_collection, get_sessions_collection

# -----------------------------------------------------
# Router & Security
# -----------------------------------------------------
router = APIRouter(prefix="/api/chat", tags=["Chat"])

# -----------------------------------------------------
# Pydantic Models
# -----------------------------------------------------
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
# Chat Endpoints (Session-Based)
# =====================================================

@router.post("/new", response_model=NewChatResponse)
async def start_new_chat(
    request: NewChatRequest,
    current_user: dict = Depends(get_current_active_user),
    sessions: Collection = Depends(get_sessions_collection)
):
    """
    Starts a new chat session:
    1. Runs semantic search over past session summaries for context.
    2. Generates AI response using that context.
    3. Creates a new MongoDB session document.
    """
    # 1. Retrieve relevant context via Pinecone semantic search
    context_summary = pinecone_service.query_relevant_summary(request.message)

    # 2. Generate AI response using context
    ai_response_text = ai_service.get_response(
        prompt=request.message,
        context=context_summary
    )

    # 3. Build initial messages and create session in DB
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

    return {"session_id": str(result.inserted_id), "response_text": ai_response_text}


@router.post("/{session_id}", response_model=ContinueChatResponse)
async def continue_chat(
    session_id: str,
    chat_msg: ChatMessage,
    current_user: dict = Depends(get_current_active_user),
    sessions: Collection = Depends(get_sessions_collection)
):
    """
    Continues an existing chat session:
    - Fetches recent messages for context
    - Generates AI response
    - Updates MongoDB document atomically
    """
    # ADDED: Validate the ObjectId format for better security and error handling.
    try:
        session_obj_id = ObjectId(session_id)
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session ID format.")

    # Validate session ownership
    session = sessions.find_one({"_id": session_obj_id, "userId": current_user["_id"]})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Limit context to last 10 messages
    recent_history = session.get("messages", [])[-10:]

    # Generate AI response with recent context
    ai_response_text = ai_service.get_response(
        prompt=chat_msg.message,
        history=recent_history
    )
    
    # Build message objects and push atomically
    user_message = {"sender": "user", "text": chat_msg.message}
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
# Task Management (Legacy - Not session-based)
# =====================================================

@router.post("/tasks")
async def create_task(
    task: TaskCreate,
    current_user: dict = Depends(get_current_active_user), # FIXED: Correct dependency name
    tasks: Collection = Depends(get_tasks_collection)
):
    """
    Creates a new task for the current user.
    """
    user_email = current_user["email"] # FIXED: Access email from the user dictionary
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
    current_user: dict = Depends(get_current_active_user), # FIXED: Correct dependency name
    tasks: Collection = Depends(get_tasks_collection)
):
    """
    Updates content and/or due_date of a task.
    """
    user_email = current_user["email"] # FIXED: Access email from the user dictionary
    update_data = task.model_dump(exclude_unset=True) # More efficient way to get update data
    
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
    current_user: dict = Depends(get_current_active_user), # FIXED: Correct dependency name
    tasks: Collection = Depends(get_tasks_collection)
):
    """
    Marks a specific task as done.
    """
    user_email = current_user["email"] # FIXED: Access email from the user dictionary
    try:
        result = tasks.update_one({"_id": ObjectId(task_id), "email": user_email}, {"$set": {"status": "done"}})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"status": "success"}
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid task ID.")


@router.get("/tasks")
async def get_tasks(
    current_user: dict = Depends(get_current_active_user), # FIXED: Correct dependency name
    tasks: Collection = Depends(get_tasks_collection)
):
    """
    Returns all pending tasks for the current user.
    """
    user_email = current_user["email"] # FIXED: Access email from the user dictionary
    cursor = tasks.find({"email": user_email, "status": "pending"}).sort("created_at", -1)
    return [{"id": str(t["_id"]), "content": t["content"], "due_date": t.get("due_date_str")} for t in cursor]


@router.get("/tasks/history")
async def get_task_history(
    current_user: dict = Depends(get_current_active_user), # FIXED: Correct dependency name
    tasks: Collection = Depends(get_tasks_collection)
):
    """
    Returns last 10 completed tasks for the current user.
    """
    user_email = current_user["email"] # FIXED: Access email from the user dictionary
    cursor = tasks.find({"email": user_email, "status": "done"}).sort("created_at", -1).limit(10)
    return [{"id": str(t["_id"]), "content": t["content"], "due_date": t.get("due_date_str")} for t in cursor]


# =====================================================
# Chat History (Legacy - Not session-based)
# =====================================================

@router.get("/history")
async def get_chat_history(
    current_user: dict = Depends(get_current_active_user), # FIXED: Correct dependency name
    chat_logs: Collection = Depends(get_chat_log_collection),
    limit: int = 50
):
    """
    NOTE: This endpoint uses an older 'chat_logs' collection and is not
    part of the new session-based system. It's kept for legacy purposes.
    """
    user_email = current_user["email"] # FIXED: Access email from the user dictionary
    cursor = chat_logs.find({"email": user_email}).sort("timestamp", 1).limit(limit)
    return [{"sender": m["sender"], "text": m["text"]} for m in cursor]


@router.delete("/history/clear")
async def clear_chat_history(
    current_user: dict = Depends(get_current_active_user), # FIXED: Correct dependency name
    chat_logs: Collection = Depends(get_chat_log_collection)
):
    """
    NOTE: This endpoint clears the older 'chat_logs' collection.
    It does NOT delete the new chat sessions.
    """
    user_email = current_user["email"] # FIXED: Access email from the user dictionary
    result = chat_logs.delete_many({"email": user_email})
    # Also clear the old redis cache key if it exists
    redis_cache.redis_client.delete(user_email)
    return {"status": "success", "message": f"Deleted {result.deleted_count} messages from legacy chat log."}