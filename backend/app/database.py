import certifi
from pymongo import MongoClient
from pymongo.collection import Collection
from app.config import settings


class Database:
    """Singleton-style database client wrapper for MongoDB Atlas."""

    def __init__(self):
        # Connect to MongoDB Atlas (TLS required)
        self.client = MongoClient(
            settings.DATABASE_URL,
            tls=True,
            tlsCAFile=certifi.where(),
        )

        db_name = getattr(settings, "MONGO_DB_NAME", "assistant_db")
        self.db = self.client[db_name]

    # --- Collections ---
    def get_user_collection(self) -> Collection:
        return self.db["users"]

    def get_user_profile_collection(self) -> Collection:
        return self.db["user_profiles"]

    def get_chat_log_collection(self) -> Collection:
        return self.db["chat_logs"]

    def get_tasks_collection(self) -> Collection:
        return self.db["tasks"]

    def get_sessions_collection(self) -> Collection:
        return self.db["sessions"]

    def get_feedback_collection(self) -> Collection:
        """Returns a reference to the 'feedback' collection."""
        return self.db["feedback"]


# Shared DB client (singleton)
db_client = Database()


# --- Dependency functions for FastAPI ---
def get_user_collection() -> Collection:
    return db_client.get_user_collection()

def get_user_profile_collection() -> Collection:
    return db_client.get_user_profile_collection()

def get_chat_log_collection() -> Collection:
    return db_client.get_chat_log_collection()

def get_tasks_collection() -> Collection:
    return db_client.get_tasks_collection()

def get_sessions_collection() -> Collection:
    return db_client.get_sessions_collection()

def get_feedback_collection() -> Collection:
    """Dependency function for the feedback collection."""
    return db_client.get_feedback_collection()
