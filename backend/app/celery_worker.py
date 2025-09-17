# backend/app/celery_worker.py

"""
Celery Worker Configuration for Maya Assistant

Features:
1. Celery app & broker/backend configuration (Redis)
2. Eventlet monkey-patching for async compatibility
3. Periodic tasks (Celery Beat) for session summarization
4. Background tasks:
    - Real-time fact extraction
    - Summarization & archiving
    - Sending reminder emails
    - Proactive prefetching of destination info
"""

# ==================================================
# 🔹 Eventlet Monkey Patch (MUST be first)
# ==================================================
import eventlet
eventlet.monkey_patch()

# ==================================================
# 🔹 Imports
# ==================================================
import logging
import smtplib
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from bson import ObjectId
from celery import Celery
from celery.schedules import crontab

from app.config import settings
from app.database import db_client
from app.services import pinecone_service, ai_service, neo4j_service, redis_service

# ==================================================
# 🔹 Logger Setup
# ==================================================
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ==================================================
# 🔹 Celery App Configuration
# ==================================================
celery_app = Celery(
    "maya_tasks",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
)
celery_app.conf.timezone = "UTC"

# ==================================================
# 🔹 Periodic Task Setup (Celery Beat)
# ==================================================
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Sets up periodic tasks for Celery Beat.
    Default interval is 5 minutes (configurable via settings.SESSION_CHECK_INTERVAL).
    """
    interval = getattr(settings, "SESSION_CHECK_INTERVAL", 300.0)  # seconds
    sender.add_periodic_task(
        interval,
        check_inactive_sessions.s(),
        name="Check and archive inactive sessions"
    )
    logger.info(f"Configured periodic task: check inactive sessions every {interval} seconds")


# ==================================================
# 🔹 Task: Check Inactive Sessions
# ==================================================
@celery_app.task(bind=True, name="check_inactive_sessions")
def check_inactive_sessions(self):
    """
    Detects sessions inactive for 30+ minutes and schedules summarization.
    """
    logger.info("CELERY: Checking for inactive sessions...")
    sessions_collection = db_client.get_sessions_collection()
    thirty_minutes_ago = datetime.utcnow() - timedelta(minutes=30)
    query = {"lastUpdatedAt": {"$lt": thirty_minutes_ago}, "isArchived": {"$ne": True}}

    try:
        inactive_sessions = list(sessions_collection.find(query))
    except Exception as e:
        logger.error(f"Failed to fetch inactive sessions: {e}")
        return

    if not inactive_sessions:
        logger.info("No inactive sessions found.")
        return

    for session in inactive_sessions:
        session_id = str(session["_id"])
        logger.info(f"Scheduling summarization for inactive session: {session_id}")
        summarize_and_archive_task.delay(session_id)


# ==================================================
# 🔹 Task: Summarize and Archive Session
# ==================================================
@celery_app.task(bind=True, name="summarize_and_archive_task")
def summarize_and_archive_task(self, session_id: str):
    """
    Consolidates a session's memory into long-term storage.
    Steps:
        1. Summarize the session for Pinecone
        2. Extract structured facts for Neo4j
        3. Mark the session as archived
    """
    logger.info(f"ARCHIVING: Processing session {session_id}")
    sessions_collection = db_client.get_sessions_collection()

    # Fetch session data
    session = sessions_collection.find_one({"_id": ObjectId(session_id)})
    if not session:
        logger.error(f"Session {session_id} not found.")
        return

    # Prepare full transcript
    full_transcript = " ".join([msg.get("text", "") for msg in session.get("messages", [])]).strip()
    if not full_transcript:
        logger.warning(f"Session {session_id} has no content to summarize.")
        summary = "No content to summarize."
    else:
        # Step 1: Summarize
        try:
            summary = ai_service.summarize_text(full_transcript)
            if not summary:
                summary = "Summary unavailable."
                logger.warning(f"AI returned empty summary for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to summarize session {session_id}: {e}")
            summary = "Failed to generate summary."

        # Step 2: Extract facts and update Neo4j
        try:
            facts = ai_service.extract_facts_from_text(full_transcript)
            if facts:
                user_entity = {"name": f"User_{session['userId']}", "label": "USER"}
                facts.setdefault("entities", []).append(user_entity)
                neo4j_service.add_entities_and_relationships(facts)
        except Exception as e:
            logger.error(f"Failed to extract/upsert facts to Neo4j for session {session_id}: {e}")

    # Step 3: Upsert summary to Pinecone
    try:
        pinecone_service.upsert_session_summary(session_id, summary)
    except Exception as e:
        logger.error(f"Pinecone upsert failed for session {session_id}: {e}")

    # Step 4: Mark session as archived
    try:
        sessions_collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"isArchived": True}}
        )
        logger.info(f"ARCHIVING SUCCESS: Session {session_id} archived.")
    except Exception as e:
        logger.error(f"Failed to mark session {session_id} as archived: {e}")


# ==================================================
# 🔹 Task: Real-time Fact Extraction
# ==================================================
@celery_app.task(name="extract_and_store_facts")
def extract_and_store_facts_task(user_message: str, assistant_message: str, user_id: str):
    """
    Lightweight task to extract and store facts from recent messages.
    """
    logger.info(f"REAL-TIME EXTRACTION: Analyzing messages for user {user_id}.")
    transcript_snippet = f"Human: {user_message}\nAssistant: {assistant_message}"

    try:
        facts = ai_service.extract_facts_from_text(transcript_snippet)
        if facts and ("entities" in facts or "relationships" in facts):
            # Ensure User node exists in facts
            user_entity = {"name": f"User_{user_id}", "label": "USER", "id": user_id}
            facts.setdefault("entities", []).append(user_entity)

            # Link PERSON entities to user
            person_entity = next((e for e in facts.get("entities", []) if e.get("label") == "PERSON"), None)
            if person_entity:
                new_relationship = {
                    "source": f"User_{user_id}",
                    "target": person_entity["name"],
                    "type": "IS_NAMED"
                }
                facts.setdefault("relationships", []).append(new_relationship)

            neo4j_service.add_entities_and_relationships(facts)

    except Exception as e:
        logger.error(f"REAL-TIME EXTRACTION: Failed for user {user_id}. Error: {e}")


# ==================================================
# 🔹 Task: Send Reminder Email
# ==================================================
@celery_app.task(
    bind=True,
    name="send_reminder_email",
    autoretry_for=(smtplib.SMTPException,),
    retry_kwargs={"max_retries": 3, "countdown": 60}
)
def send_reminder_email(self, recipient_email: str, task_content: str):
    """
    Sends reminder email with retries for SMTP errors.
    """
    logger.info(f"Sending reminder to {recipient_email} for task '{task_content}'")

    subject = f"Maya Reminder: {task_content}"
    body = (
        f"Hello!\n\n"
        f"This is a friendly reminder for your scheduled task:\n\n"
        f"'{task_content}'\n\n"
        f"- Maya Assistant"
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.MAIL_FROM
    msg["To"] = recipient_email

    try:
        with smtplib.SMTP_SSL(settings.MAIL_SERVER, settings.MAIL_PORT or 465) as server:
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email successfully sent to {recipient_email}")
        return f"Email sent to {recipient_email}"
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {e}. Retrying...")
        raise self.retry(exc=e)


# ==================================================
# 🔹 Task: Proactive Destination Prefetch
# ==================================================
@celery_app.task(name="prefetch_destination_info", rate_limit='10/m')
def prefetch_destination_info_task(destination: str, session_id: str):
    """
    Prefetches destination info and caches it in Redis for fast retrieval.
    """
    logger.info(f"PROACTIVE_FETCH: Prefetching info for '{destination}' (session {session_id})")

    try:
        # MOCK DATA (replace with real APIs)
        attractions = {
            "Paris": ["Eiffel Tower", "Louvre Museum", "Notre-Dame Cathedral"],
            "Rome": ["Colosseum", "Trevi Fountain", "Pantheon"],
            "Tokyo": ["Senso-ji Temple", "Shibuya Crossing", "Tokyo Skytree"]
        }
        weather_info = {
            "Paris": "Sunny, high 22°C",
            "Rome": "Clear skies, high 25°C",
            "Tokyo": "Partly cloudy, 28°C"
        }

        prefetched_data = {
            "attractions": attractions.get(destination, ["interesting local sights"]),
            "weather": weather_info.get(destination, "pleasant weather")
        }

        # Cache in Redis
        cache_key = f"prefetched_info:{session_id}"
        redis_service.set_prefetched_data(cache_key, prefetched_data)
        logger.info(f"PROACTIVE_FETCH: Cached info for '{destination}' successfully")

    except Exception as e:
        logger.error(f"PROACTIVE_FETCH: Failed for '{destination}'. Error: {e}")
