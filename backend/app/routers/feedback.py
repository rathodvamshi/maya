# backend/app/routers/feedback.py

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from pymongo.collection import Collection
from datetime import datetime
from typing import List

from app.security import get_current_active_user
from app.database import get_feedback_collection

router = APIRouter(
    prefix="/api/feedback",
    tags=["Feedback"],
    dependencies=[Depends(get_current_active_user)] # Protect this endpoint
)

# --- Pydantic Models for Validation ---

class MessageModel(BaseModel):
    sender: str
    text: str

class FeedbackCreate(BaseModel):
    session_id: str = Field(..., alias="sessionId")
    chat_history: List[MessageModel] = Field(..., alias="chatHistory")
    rated_message: MessageModel = Field(..., alias="ratedMessage")
    rating: str # 'good' or 'bad'

# --- API Endpoint ---

@router.post("/", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    feedback_data: FeedbackCreate,
    current_user: dict = Depends(get_current_active_user),
    feedback_collection: Collection = Depends(get_feedback_collection)
):
    """
    Receives and stores user feedback for an AI message.
    """
    feedback_document = {
        "userId": current_user["_id"],
        "sessionId": feedback_data.session_id,
        "rating": feedback_data.rating,
        "ratedMessage": feedback_data.rated_message.model_dump(),
        "chatHistory": [msg.model_dump() for msg in feedback_data.chat_history],
        "createdAt": datetime.utcnow(),
        "reviewed": False # A flag for your future admin dashboard
    }

    feedback_collection.insert_one(feedback_document)
    
    return {"status": "success", "message": "Feedback received successfully."}