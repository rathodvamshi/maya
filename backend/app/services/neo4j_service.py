# backend/app/services/neo4j_service.py

import logging
from typing import List, Optional, Dict, Any
from neo4j import AsyncGraphDatabase, AsyncDriver
from app.config import settings

logger = logging.getLogger(__name__)

class Neo4jService:
    _driver: Optional[AsyncDriver] = None

    async def connect(self):
        if self._driver: return
        try:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI, 
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            await self._driver.verify_connectivity()
        except Exception as e:
            logger.error(f"❌ Initial Neo4j connection failed: {e}")
            self._driver = None

    async def close(self):
        if self._driver:
            await self._driver.close()

    async def run_query(self, query: str, parameters: Optional[Dict] = None) -> Optional[List[Dict]]:
        if not self._driver:
            logger.error("Neo4j driver not available. Cannot run query.")
            return None
        try:
            async with self._driver.session() as session:
                result = await session.run(query, parameters or {})
                return [record.data() async for record in result]
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            return None

    # =====================================================
    # 🔹 RESTORED: User Operations
    # =====================================================
    async def create_user_node(self, user_id: str):
        """Creates a User node if it doesn't already exist."""
        await self.run_query("MERGE (u:User {id: $user_id})", {"user_id": user_id})

    async def get_user_facts(self, user_id: str) -> Optional[str]:
        """Retrieves all known facts connected to a user."""
        query = """
        MATCH (u:User {id: $user_id})-[r]->(n)
        WHERE NOT n:User AND n.name IS NOT NULL
        RETURN type(r) AS relationship, n.name AS entity_name
        """
        results = await self.run_query(query, {"user_id": user_id})
        if not results:
            return "No specific facts are known about this user yet."
        facts = [f"- The user's {r['relationship'].lower().replace('_', ' ')} is '{r['entity_name']}'." for r in results]
        return "\n".join(facts)
        
    async def add_entities_and_relationships(self, facts: Dict[str, Any]):
        """Adds structured facts to the knowledge graph."""
        entities = facts.get("entities", [])
        relationships = facts.get("relationships", [])
        if not entities and not relationships: return

        async with self._driver.session() as session:
            async with session.begin_transaction() as tx:
                for entity in entities:
                    label = "".join(filter(str.isalnum, entity.get("label", "Thing")))
                    await tx.run(f"MERGE (n:{label} {{name: $name}})", name=entity.get("name"))
                for rel in relationships:
                    rel_type = "".join(filter(str.isalnum, rel.get("type", "RELATED_TO")))
                    await tx.run(
                        f"MATCH (source {{name: $source_name}}), (target {{name: $target_name}}) "
                        f"MERGE (source)-[r:{rel_type}]->(target)",
                        source_name=rel.get("source"), target_name=rel.get("target")
                    )

neo4j_service = Neo4jService()