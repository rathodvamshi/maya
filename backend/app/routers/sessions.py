from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from pymongo.collection import Collection
from bson import ObjectId, errors
from datetime import datetime
from typing import List, Optional

from app.database import get_sessions_collection, get_user_profile_collection, get_tasks_collection
from app.security import get_current_active_user
from app.services import ai_service, nlu, redis_cache
from app.celery_worker import celery_app
import dateparser

router = APIRouter(
    prefix="/api/sessions",
    tags=["Sessions"],
    dependencies=[Depends(get_current_active_user)]
)

# -----------------------------
# Models
# -----------------------------

class Message(BaseModel):
    sender: str
    text: str

class ChatRequest(BaseModel):
    message: str

class TaskCreate(BaseModel):
    content: str
    due_date: str

class TaskUpdate(BaseModel):
    content: Optional[str] = None
    due_date: Optional[str] = None

# -----------------------------
# Session Management
# -----------------------------

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_session(messages: List[Message], current_user: dict = Depends(get_current_active_user),
                         sessions_collection: Collection = Depends(get_sessions_collection)):
    if not messages:
        raise HTTPException(status_code=400, detail="Cannot create an empty session.")
    
    first_user_msg = next((m.text for m in messages if m.sender == 'user'), "New Chat")
    title = (first_user_msg[:50] + "...") if len(first_user_msg) > 50 else first_user_msg
    
    new_session = {
        "userId": current_user["_id"],
        "title": title,
        "createdAt": datetime.utcnow(),
        "messages": [m.model_dump() for m in messages]
    }
    result = sessions_collection.insert_one(new_session)
    return {"id": str(result.inserted_id), "title": title, "createdAt": new_session["createdAt"]}


@router.get("/", response_model=List[dict])
async def get_sessions(current_user: dict = Depends(get_current_active_user),
                       sessions_collection: Collection = Depends(get_sessions_collection)):
    cursor = sessions_collection.find({"userId": current_user["_id"]}, {"messages": 0}).sort("createdAt", -1)
    sessions = [{"id": str(s["_id"]), "title": s["title"], "createdAt": s["createdAt"]} for s in cursor]
    return sessions


@router.get("/{session_id}")
async def get_session_messages(session_id: str,
                               page: int = Query(1, gt=0),
                               limit: int = Query(30, gt=0),
                               current_user: dict = Depends(get_current_active_user),
                               sessions_collection: Collection = Depends(get_sessions_collection)):
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID.")
    
    skip = (page - 1) * limit
    
    pipeline = [
        {"$match": {"_id": ObjectId(session_id), "userId": current_user["_id"]}},
        {"$project": {
            "title": 1,
            "createdAt": 1,
            "totalMessages": {"$size": "$messages"},
            "messages": {"$slice": ["$messages", - (skip + limit), limit]}
        }}
    ]
    result = list(sessions_collection.aggregate(pipeline))
    if not result:
        raise HTTPException(status_code=404, detail="Session not found.")
    
    session_data = result[0]
    session_data["_id"] = str(session_data["_id"])
    return session_data


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str,
                         current_user: dict = Depends(get_current_active_user),
                         sessions_collection: Collection = Depends(get_sessions_collection)):
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID.")
    
    result = sessions_collection.delete_one({"_id": ObjectId(session_id), "userId": current_user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found or permission denied.")


# -----------------------------
# Chat Messaging within a Session
# -----------------------------

@router.post("/{session_id}/chat")
async def send_message(session_id: str,
                       chat_req: ChatRequest,
                       current_user: dict = Depends(get_current_active_user),
                       sessions_collection: Collection = Depends(get_sessions_collection),
                       user_profiles: Collection = Depends(get_user_profile_collection),
                       tasks: Collection = Depends(get_tasks_collection)):
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID.")

    # Verify session ownership
    session = sessions_collection.find_one({"_id": ObjectId(session_id), "userId": current_user["_id"]})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or permission denied.")
    
    user_email = current_user["email"] if "email" in current_user else current_user.get("sub", "")
    user_message = {"sender": "user", "text": chat_req.message}
    
    # --- NLU Processing ---
    ai_response_text = ""
    nlu_result = nlu.get_structured_intent(chat_req.message)
    action = nlu_result.get("action")
    
    if action == "create_task":
        data = nlu_result.get("data", {})
        title = data.get("title")
        datetime_str = data.get("datetime")
        if title and datetime_str:
            due_date = dateparser.parse(datetime_str)
            if due_date:
                formatted_due_date = due_date.strftime("%Y-%m-%d %H:%M")
                tasks.insert_one({"email": user_email, "content": title, "due_date_str": formatted_due_date,
                                  "status": "pending", "created_at": datetime.utcnow()})
                delay = (due_date - datetime.utcnow()).total_seconds()
                if delay > 0:
                    celery_app.send_task("send_reminder_email", args=[user_email, title], countdown=delay)
                ai_response_text = f"Task '{title}' scheduled for {formatted_due_date}."
            else:
                ai_response_text = f"Task '{title}' scheduled but due date parsing failed."
        else:
            ai_response_text = "Incomplete task details. Please try again."
    
    elif action == "fetch_tasks":
        cursor = tasks.find({"email": user_email, "status": "pending"}).sort("created_at", 1)
        task_list = [f"- {t['content']} (Due: {t['due_date_str']})" for t in cursor]
        ai_response_text = "Your pending tasks:\n" + "\n".join(task_list) if task_list else "No pending tasks."
    
    elif action == "save_fact":
        data = nlu_result.get("data", {})
        key, value = data.get("key"), data.get("value")
        if key and value:
            key = key.lower().replace("_", " ")
            user_profiles.update_one({"email": user_email, "facts.key": key},
                                     {"$set": {"facts.$.value": value}}, upsert=False)
            if user_profiles.find_one({"email": user_email, "facts.key": key}) is None:
                user_profiles.update_one({"email": user_email}, {"$push": {"facts": {"key": key, "value": value}},
                                                                  "$setOnInsert": {"email": user_email}}, upsert=True)
            ai_response_text = f"Got it. I will remember that your {key} is {value}."
        else:
            ai_response_text = "Could not understand the fact. Please rephrase."
    
    else:
        # Default AI response with facts and conversation context
        profile = user_profiles.find_one({"email": user_email})
        facts_text = "\n".join([f"- {f['key']}: {f['value']}" for f in profile.get("facts", [])]) if profile else ""
        conversation_history = redis_cache.get_conversation_context(user_email)
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in conversation_history])
        prompt = f"""You are a friendly assistant. User facts: {facts_text if facts_text else 'None'}.
Conversation history: {history_text if history_text else 'New conversation.'}
User Message: "{chat_req.message}".
Respond appropriately."""
        ai_response_text = ai_service.generate_ai_response(prompt)
    
    ai_message = {"sender": "assistant", "text": ai_response_text}

    # Push both messages atomically to session
    sessions_collection.update_one(
        {"_id": ObjectId(session_id), "userId": current_user["_id"]},
        {"$push": {"messages": {"$each": [user_message, ai_message]}}}
    )

    # Update Redis conversation memory
    redis_cache.set_conversation_context(user_email, {"role": "user", "content": chat_req.message})
    redis_cache.set_conversation_context(user_email, {"role": "assistant", "content": ai_response_text})

    return ai_message
