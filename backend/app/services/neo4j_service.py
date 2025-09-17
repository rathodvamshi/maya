# backend/app/services/neo4j_service.py

from neo4j import GraphDatabase, Driver
from app.config import settings
import logging
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 Neo4j Service Class
# =====================================================
class Neo4jService:
    """
    Service to manage Neo4j connections and operations.
    Provides safe methods for creating nodes and running queries.
    """

    def __init__(self, uri: str, user: str, password: str):
        try:
            self._driver: Optional[Driver] = GraphDatabase.driver(uri, auth=(user, password))
            # Verify connectivity immediately
            self._driver.verify_connectivity()
            logger.info("✅ Successfully connected to Neo4j.")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Neo4j: {e}")
            self._driver = None

    def close(self):
        """Closes the Neo4j driver connection."""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j connection closed.")

    # -----------------------------
    # Generic Query Execution
    # -----------------------------
    def run_query(self, query: str, parameters: Optional[Dict] = None) -> Optional[List[Dict]]:
        """
        Executes a Cypher query.
        Returns a list of record dictionaries or None on failure.
        """
        if not self._driver:
            logger.error("Neo4j driver not initialized. Cannot run query.")
            return None

        try:
            with self._driver.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            return None

    # -----------------------------
    # User Operations
    # -----------------------------
    def create_user_node(self, user_id: str):
        """Create a User node if it doesn't exist."""
        query = "MERGE (u:User {id: $user_id}) RETURN u"
        self.run_query(query, {"user_id": user_id})
        logger.info(f"Ensured User node exists for id: {user_id}")

    def get_user_node(self, user_id: str) -> Optional[Dict]:
        """Retrieve a User node by ID."""
        query = "MATCH (u:User {id: $user_id}) RETURN u LIMIT 1"
        result = self.run_query(query, {"user_id": user_id})
        return result[0] if result else None

    # -----------------------------
    # Session Operations
    # -----------------------------
    def create_session_node(self, session_id: str, user_id: str):
        """
        Create a Session node and link it to a User node.
        Useful for tracking chat sessions in Neo4j.
        """
        query = """
        MATCH (u:User {id: $user_id})
        MERGE (s:Session {id: $session_id})
        MERGE (u)-[:HAS_SESSION]->(s)
        RETURN s
        """
        self.run_query(query, {"user_id": user_id, "session_id": session_id})
        logger.info(f"Session node created and linked to User {user_id}: {session_id}")


# =====================================================
# 🔹 Singleton Instance
# =====================================================
neo4j_service = Neo4jService(
    uri=settings.NEO4J_URI,
    user=settings.NEO4J_USER,
    password=settings.NEO4J_PASSWORD
)
