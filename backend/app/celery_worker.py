# backend/app/celery_worker.py
"""
Celery Worker Configuration for Maya Assistant.

Features:
1. Celery app & broker/backend configuration
2. Periodic tasks (Celery Beat) for session summarization
3. Background task for sending email reminders with retries
"""

import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from bson import ObjectId
from celery import Celery
from celery.schedules import crontab

from app.config import settings
from app.database import db_client  # MongoDB client
from app.services import pinecone_service, ai_service  # Pinecone & AI services

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
# 🔹 Periodic Task: Session Summarization
# ==================================================
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Sets up periodic tasks (interval configurable via settings)."""
    interval = getattr(settings, "SESSION_CHECK_INTERVAL", 300.0)  # default 5 minutes
    sender.add_periodic_task(
        interval,
        find_inactive_sessions.s(),
        name="Check and archive inactive sessions"
    )
    logger.info(f"Configured periodic task: inactive session check every {interval} seconds")


@celery_app.task(bind=True, name="find_inactive_sessions")
def find_inactive_sessions(self):
    """Detects sessions inactive for 30+ mins and schedules summarization."""
    logger.info("CELERY BEAT: Checking for inactive sessions...")
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


@celery_app.task(bind=True, name="summarize_and_archive_task")
def summarize_and_archive_task(self, session_id: str):
    """Fetch chat history, summarize via AI, upsert to Pinecone, archive session."""
    logger.info(f"ARCHIVING: Processing session {session_id}")
    sessions_collection = db_client.get_sessions_collection()

    session = sessions_collection.find_one({"_id": ObjectId(session_id)})
    if not session:
        logger.error(f"Session {session_id} not found.")
        return

    full_transcript = " ".join([msg.get("text", "") for msg in session.get("messages", [])]).strip()
    if not full_transcript:
        logger.warning(f"Session {session_id} has no content. Archiving without summary.")
        summary = "No content to summarize."
    else:
        try:
            summary = ai_service.summarize_text(full_transcript)
            if not summary:
                summary = "Summary unavailable."
                logger.warning(f"AI returned empty summary for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to summarize session {session_id}: {e}")
            return

    try:
        pinecone_service.upsert_session_summary(session_id, summary)
    except Exception as e:
        logger.error(f"Pinecone upsert failed for session {session_id}: {e}")
        return

    try:
        sessions_collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"isArchived": True}}
        )
        logger.info(f"ARCHIVING SUCCESS: Session {session_id} archived.")
    except Exception as e:
        logger.error(f"Failed to update session {session_id} as archived: {e}")


# ==================================================
# 🔹 Celery Task: Email Reminder
# ==================================================
@celery_app.task(
    bind=True,
    name="send_reminder_email",
    autoretry_for=(smtplib.SMTPException,),
    retry_kwargs={"max_retries": 3, "countdown": 60}
)
def send_reminder_email(self, recipient_email: str, task_content: str):
    """Sends reminder email with retry on failure."""
    logger.info(f"Sending reminder to {recipient_email} for task '{task_content}'")

    subject = f"Maya Reminder: {task_content}"
    body = f"Hello!\n\nThis is a friendly reminder for your scheduled task:\n\n'{task_content}'\n\n- Maya Assistant"

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
