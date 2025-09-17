# backend/app/database.py

from pymongo import MongoClient
from pymongo.collection import Collection
from app.config import settings


class Database:
    def __init__(self):
        self.client = MongoClient(settings.DATABASE_URL)
        self.db = self.client["assistant_db"]

    def get_user_collection(self) -> Collection:
        return self.db.users

    def get_user_profile_collection(self) -> Collection:
        return self.db.user_profiles

    def get_chat_log_collection(self) -> Collection:
        """Returns a reference to the 'chat_logs' collection."""
        return self.db.chat_logs

    def get_tasks_collection(self) -> Collection:
        """Returns a reference to the 'tasks' collection."""
        return self.db.tasks

    def get_sessions_collection(self) -> Collection:
        """Returns a reference to the 'sessions' collection."""
        return self.db.sessions


# Create a single shared database client
db_client = Database()


# ======================================================
# Dependency Functions
# ======================================================

def get_user_collection() -> Collection:
    return db_client.get_user_collection()


def get_user_profile_collection() -> Collection:
    return db_client.get_user_profile_collection()


def get_chat_log_collection() -> Collection:
    """Dependency function for chat logs."""
    return db_client.get_chat_log_collection()


def get_tasks_collection() -> Collection:
    """Dependency function for tasks."""
    return db_client.get_tasks_collection()


def get_sessions_collection() -> Collection:
    """Dependency function for sessions."""
    return db_client.get_sessions_collection()
