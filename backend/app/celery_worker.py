
import eventlet
eventlet.monkey_patch()

import asyncio
import logging
from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta
from bson import ObjectId

from app.config import settings
from app.database import db_client
from app.services import pinecone_service, ai_service, neo4j_service, redis_service


logger = logging.getLogger(__name__)
def run_async(func, *args, **kwargs):
    return asyncio.run(func(*args, **kwargs))

celery_app = Celery("maya_tasks", broker=f"redis://{settings.REDIS_HOST}...")
#... (rest of celery config)

# =====================================================
# Periodic Task Setup
# =====================================================
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Example: run every 5 minutes
    sender.add_periodic_task(300.0, check_inactive_sessions.s(), name="Check inactive sessions")
    logger.info("Configured periodic task: check inactive sessions every 300 seconds")

# =====================================================
# Task Definitions
# =====================================================

celery_app = Celery(
    "maya_tasks",
    # FIXED: The typo `.../` is corrected to `{...}` for the database index.
    # This was causing the UnicodeError crash.
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    # Tell Celery where to find the task definitions.
    include=['app.celery_worker']
)

celery_app.conf.timezone = "UTC"


@celery_app.task(name="summarize_and_archive_task")
def summarize_and_archive_task(session_id: str):
    """
    Summarize session data and archive it.
    Calls async Neo4j operations via run_async.
    """
    try:
        logger.info(f"Summarizing and archiving session {session_id}")
        # Example: fetch session transcript
        # transcript = db_client.get_session_transcript(session_id)
        # Perform AI summarization
        # summary = ai_service.summarize_text(transcript)
        # Store summary in Neo4j
        run_async(neo4j_service.store_session_summary, session_id, "summary_placeholder")
    except Exception as e:
        logger.error(f"Error summarizing session {session_id}: {e}")


@celery_app.task(name="extract_and_store_facts")
def extract_and_store_facts_task(user_message: str, assistant_message: str, user_id: str):
    logger.info(f"REAL-TIME EXTRACTION: Analyzing messages for user {user_id}.")
    transcript = f"Human: {user_message}\nAssistant: {assistant_message}"
    try:
        # Step 1: Initialize Neo4j connection within the task process
        run_async(neo4j_service.connect)
        
        # Step 2: Extract facts using the AI
        facts = ai_service.extract_facts_from_text(transcript)
        
        if facts and ("entities" in facts or "relationships" in facts):
            # Step 3: Add user info and relationships to the facts
            user_node_name = f"User_{user_id}"
            facts.setdefault("entities", []).append({"name": user_node_name, "label": "User", "id": user_id})
            
            person_entity = next((e for e in facts.get("entities", []) if e.get("label") == "PERSON"), None)
            if person_entity:
                facts.setdefault("relationships", []).append({
                    "source": user_node_name,
                    "target": person_entity["name"],
                    "type": "IS_NAMED"
                })
            
            # Step 4: Add facts to the graph
            run_async(neo4j_service.add_entities_and_relationships, facts)
            logger.info(f"Successfully stored facts for user {user_id}.")
            
    except Exception as e:
        logger.error(f"REAL-TIME EXTRACTION: Failed for user {user_id}. Error: {e}")


@celery_app.task(name="prefetch_destination_info")
def prefetch_destination_info_task(destination: str, session_id: str):
    """
    Preload information about a destination for faster response.
    """
    try:
        logger.info(f"Prefetching info for destination {destination}, session {session_id}")
        # Example pseudo-code:
        # info = ai_service.fetch_destination_info(destination)
        # cache in Redis
        # redis_service.set(f"dest_info:{destination}", info, ex=3600)
    except Exception as e:
        logger.error(f"Error prefetching destination info for {destination}: {e}")
