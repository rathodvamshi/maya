# backend/app/services/neo4j_service.py

from neo4j import GraphDatabase, Driver
from app.config import settings
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 Neo4j Service Class
# =====================================================
class Neo4jService:
    """
    Service to manage Neo4j connections and operations.
    Provides safe methods for creating nodes, running queries,
    and adding structured facts (entities & relationships) to the knowledge graph.
    """

    def __init__(self, uri: str, user: str, password: str):
        """
        Initializes the Neo4j driver and verifies connectivity.
        """
        try:
            self._driver: Optional[Driver] = GraphDatabase.driver(uri, auth=(user, password))
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
        """Creates a User node if it doesn't exist."""
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

    # -----------------------------
    # Fact / Knowledge Graph Operations
    # -----------------------------
    def add_entities_and_relationships(self, facts: Dict[str, Any]):
        """
        Adds structured facts (entities and relationships) to the Neo4j graph.
        Idempotent operation: MERGE avoids duplicates.
        Example facts format:
        {
            "entities": [{"name": "Alex", "label": "PERSON"}],
            "relationships": [{"source": "Alex", "target": "Paris", "type": "PLANS_TRIP_TO"}]
        }
        """
        entities = facts.get("entities", [])
        relationships = facts.get("relationships", [])

        if not entities and not relationships:
            logger.info("No new facts to add to the knowledge graph.")
            return

        if not self._driver:
            logger.error("Neo4j driver not initialized. Cannot add facts.")
            return

        try:
            with self._driver.session() as session:
                session.write_transaction(self._create_graph_nodes_and_edges, entities, relationships)
            logger.info(f"✅ Added {len(entities)} entities and {len(relationships)} relationships to the knowledge graph.")
        except Exception as e:
            logger.error(f"Failed to add facts to knowledge graph: {e}")

    @staticmethod
    def _create_graph_nodes_and_edges(tx, entities: List[Dict], relationships: List[Dict]):
        """
        Static method that executes Cypher queries in a transaction.
        Creates all entities first, then relationships between them.
        """
        # Create entities
        for entity in entities:
            query = f"MERGE (n:{entity['label']} {{name: $name}})"
            tx.run(query, name=entity['name'])

        # Create relationships
        for rel in relationships:
            query = (
                "MATCH (source {name: $source_name}), (target {name: $target_name}) "
                f"MERGE (source)-[r:{rel['type']}]->(target)"
            )
            tx.run(query, source_name=rel['source'], target_name=rel['target'])

# =====================================================
# 🔹 Singleton Instance
# =====================================================
neo4j_service = Neo4jService(
    uri=settings.NEO4J_URI,
    user=settings.NEO4J_USER,
    password=settings.NEO4J_PASSWORD
)
