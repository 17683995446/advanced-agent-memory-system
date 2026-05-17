"""
Knowledge Graph Memory Module for Agent Memory System.

This module provides a knowledge graph implementation using NetworkX,
enabling structured storage and retrieval of entity-relationship knowledge.
It supports fuzzy search, path finding, subgraph extraction, and persistence.
"""

from __future__ import annotations

import json
import re
import threading
from difflib import SequenceMatcher
from typing import Optional

import networkx as nx
from pydantic import BaseModel, Field


class Entity(BaseModel):
    """Represents a node in the knowledge graph.

    Attributes:
        name: Unique identifier for the entity.
        entity_type: Category or type of the entity (e.g., "person", "concept", "location").
        description: Human-readable description of the entity.
        properties: Arbitrary key-value metadata associated with the entity.
    """

    name: str
    entity_type: str = "concept"
    description: str = ""
    properties: dict = Field(default_factory=dict)


class Relation(BaseModel):
    """Represents a directed edge in the knowledge graph.

    Attributes:
        source: Name of the source entity.
        target: Name of the target entity.
        relation_type: Semantic type of the relationship (e.g., "is_a", "part_of").
        weight: Numerical strength or confidence of the relation (0.0 to 1.0+).
        metadata: Arbitrary key-value metadata associated with the relation.
    """

    source: str
    target: str
    relation_type: str
    weight: float = 1.0
    metadata: dict = Field(default_factory=dict)


class GraphSearchResult(BaseModel):
    """Result container for knowledge graph search operations.

    Attributes:
        entities: List of entities found in the search.
        relations: List of relations connecting the found entities.
        score: Relevance or similarity score for this result.
    """

    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    score: float = 0.0


class KnowledgeGraph:
    """A thread-safe knowledge graph backed by NetworkX DiGraph.

    This class provides methods for adding, removing, querying, and analyzing
    entities and relations in a directed graph structure. All public methods
    are thread-safe through the use of a reentrant lock.

    Attributes:
        graph: The underlying NetworkX directed graph.
    """

    def __init__(self) -> None:
        """Initialize an empty knowledge graph."""
        self.graph: nx.DiGraph = nx.DiGraph()
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Core methods
    # ------------------------------------------------------------------

    def add_entity(self, entity: Entity) -> str:
        """Add an entity to the knowledge graph.

        If an entity with the same name already exists, its attributes will
        be updated with the new values.

        Args:
            entity: The Entity object to add.

        Returns:
            The name of the added entity.
        """
        with self._lock:
            self.graph.add_node(
                entity.name,
                entity_type=entity.entity_type,
                description=entity.description,
                properties=entity.properties,
            )
        return entity.name

    def add_relation(self, relation: Relation) -> str:
        """Add a directed relation between two entities.

        If either the source or target entity does not yet exist in the graph,
        placeholder nodes are created automatically. If a relation of the same
        type already exists between the two entities, it is updated.

        Args:
            relation: The Relation object to add.

        Returns:
            A string identifier in the form ``"source -> target [relation_type]"``.
        """
        with self._lock:
            # Ensure both endpoints exist as nodes
            for node_name in (relation.source, relation.target):
                if not self.graph.has_node(node_name):
                    self.graph.add_node(
                        node_name,
                        entity_type="concept",
                        description="",
                        properties={},
                    )
            self.graph.add_edge(
                relation.source,
                relation.target,
                relation_type=relation.relation_type,
                weight=relation.weight,
                metadata=relation.metadata,
            )
        return f"{relation.source} -> {relation.target} [{relation.relation_type}]"

    def remove_entity(self, name: str) -> bool:
        """Remove an entity and all of its incoming and outgoing relations.

        Args:
            name: The name of the entity to remove.

        Returns:
            True if the entity was found and removed, False otherwise.
        """
        with self._lock:
            if self.graph.has_node(name):
                self.graph.remove_node(name)
                return True
            return False

    def remove_relation(
        self, source: str, target: str, relation_type: str
    ) -> bool:
        """Remove a specific directed relation.

        Args:
            source: Name of the source entity.
            target: Name of the target entity.
            relation_type: Type of the relation to remove.

        Returns:
            True if the relation was found and removed, False otherwise.
        """
        with self._lock:
            if self.graph.has_edge(source, target):
                edge_data = self.graph[source][target]
                if edge_data.get("relation_type") == relation_type:
                    self.graph.remove_edge(source, target)
                    return True
            return False

    def get_entity(self, name: str) -> Optional[Entity]:
        """Retrieve an entity by name.

        Args:
            name: The name of the entity to look up.

        Returns:
            An Entity object if found, otherwise None.
        """
        with self._lock:
            if not self.graph.has_node(name):
                return None
            node_data = self.graph.nodes[name]
            return Entity(
                name=name,
                entity_type=node_data.get("entity_type", "concept"),
                description=node_data.get("description", ""),
                properties=node_data.get("properties", {}),
            )

    def get_relations(
        self, entity_name: str, direction: str = "both"
    ) -> list[Relation]:
        """Get all relations connected to an entity.

        Args:
            entity_name: The name of the entity.
            direction: One of ``"outgoing"``, ``"incoming"``, or ``"both"``.

        Returns:
            A list of Relation objects matching the direction filter.
        """
        if direction not in ("outgoing", "incoming", "both"):
            raise ValueError(
                f"direction must be 'outgoing', 'incoming', or 'both', got '{direction}'"
            )

        relations: list[Relation] = []
        with self._lock:
            if direction in ("outgoing", "both"):
                for _, target, edge_data in self.graph.out_edges(
                    entity_name, data=True
                ):
                    relations.append(
                        Relation(
                            source=entity_name,
                            target=target,
                            relation_type=edge_data.get("relation_type", "related_to"),
                            weight=edge_data.get("weight", 1.0),
                            metadata=edge_data.get("metadata", {}),
                        )
                    )
            if direction in ("incoming", "both"):
                for source, _, edge_data in self.graph.in_edges(
                    entity_name, data=True
                ):
                    relations.append(
                        Relation(
                            source=source,
                            target=entity_name,
                            relation_type=edge_data.get("relation_type", "related_to"),
                            weight=edge_data.get("weight", 1.0),
                            metadata=edge_data.get("metadata", {}),
                        )
                    )
        return relations

    def get_neighbors(
        self, entity_name: str, max_depth: int = 1
    ) -> list[Entity]:
        """Get all entities connected to *entity_name* within *max_depth* hops.

        Args:
            entity_name: The center entity name.
            max_depth: Maximum number of hops to traverse (default 1).

        Returns:
            A list of Entity objects reachable within the given depth,
            excluding the center entity itself.
        """
        with self._lock:
            if not self.graph.has_node(entity_name):
                return []

            # Use ego_graph for efficient neighborhood extraction
            ego = nx.ego_graph(
                self.graph, entity_name, radius=max_depth, center=False
            )
            entities: list[Entity] = []
            for node_name in ego.nodes():
                node_data = self.graph.nodes[node_name]
                entities.append(
                    Entity(
                        name=node_name,
                        entity_type=node_data.get("entity_type", "concept"),
                        description=node_data.get("description", ""),
                        properties=node_data.get("properties", {}),
                    )
                )
        return entities

    # ------------------------------------------------------------------
    # Search methods
    # ------------------------------------------------------------------

    def search_entities(
        self, query: str, top_k: int = 5
    ) -> list[tuple[Entity, float]]:
        """Fuzzy-search entities by matching the query against names and descriptions.

        Scoring uses SequenceMatcher ratio. For each entity the higher of the
        name-match score and the description-match score is used.

        Args:
            query: The search string.
            top_k: Maximum number of results to return.

        Returns:
            A list of ``(Entity, score)`` tuples sorted by descending score.
        """
        results: list[tuple[Entity, float]] = []
        with self._lock:
            for node_name, node_data in self.graph.nodes(data=True):
                name_score = SequenceMatcher(None, query, node_name).ratio()
                desc = node_data.get("description", "")
                desc_score = (
                    SequenceMatcher(None, query, desc).ratio() if desc else 0.0
                )
                best_score = max(name_score, desc_score)
                if best_score > 0:
                    entity = Entity(
                        name=node_name,
                        entity_type=node_data.get("entity_type", "concept"),
                        description=desc,
                        properties=node_data.get("properties", {}),
                    )
                    results.append((entity, best_score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def find_path(self, source: str, target: str) -> Optional[list[str]]:
        """Find the shortest path between two entities.

        Args:
            source: Name of the starting entity.
            target: Name of the destination entity.

        Returns:
            A list of entity names representing the shortest path (inclusive
            of both endpoints), or None if no path exists.
        """
        with self._lock:
            if not self.graph.has_node(source) or not self.graph.has_node(target):
                return None
            try:
                path = nx.shortest_path(self.graph, source=source, target=target)
                return path
            except nx.NetworkXNoPath:
                return None

    def find_related(
        self, entity_name: str, top_k: int = 5
    ) -> list[GraphSearchResult]:
        """Find the most related entities to *entity_name* by graph structure.

        Relatedness is computed as a combination of:
        1. **Degree centrality** of the candidate entity (normalised).
        2. **Shared neighbors** with *entity_name* (Jaccard-like coefficient).

        Args:
            entity_name: The center entity.
            top_k: Number of top results to return.

        Returns:
            A list of GraphSearchResult objects sorted by descending score.
        """
        results: list[GraphSearchResult] = []
        with self._lock:
            if not self.graph.has_node(entity_name):
                return results

            # Precompute neighbor sets
            entity_neighbors = set(self.graph.predecessors(entity_name)) | set(
                self.graph.successors(entity_name)
            )

            # Degree centrality (normalised by max possible degree)
            n = self.graph.number_of_nodes()
            max_degree = n - 1 if n > 1 else 1
            centrality = nx.degree_centrality(self.graph)

            for candidate in self.graph.nodes():
                if candidate == entity_name:
                    continue

                candidate_neighbors = set(self.graph.predecessors(candidate)) | set(
                    self.graph.successors(candidate)
                )

                # Shared neighbors (Jaccard)
                intersection = entity_neighbors & candidate_neighbors
                union = entity_neighbors | candidate_neighbors
                jaccard = len(intersection) / len(union) if union else 0.0

                # Combined score: weighted sum
                score = 0.4 * centrality.get(candidate, 0.0) + 0.6 * jaccard

                if score > 0:
                    # Collect entities
                    entities = [self._node_to_entity(candidate)]
                    # Collect relations between center and candidate
                    relations = []
                    if self.graph.has_edge(entity_name, candidate):
                        relations.append(
                            self._edge_to_relation(entity_name, candidate)
                        )
                    if self.graph.has_edge(candidate, entity_name):
                        relations.append(
                            self._edge_to_relation(candidate, entity_name)
                        )
                    results.append(
                        GraphSearchResult(
                            entities=entities,
                            relations=relations,
                            score=round(score, 4),
                        )
                    )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def get_subgraph(self, center: str, radius: int = 1) -> KnowledgeGraph:
        """Extract a subgraph centered on *center* with the given radius.

        Args:
            center: The name of the center entity.
            radius: Number of hops to include around the center.

        Returns:
            A new KnowledgeGraph containing only the nodes and edges within
            the specified radius.
        """
        sub = KnowledgeGraph()
        with self._lock:
            if not self.graph.has_node(center):
                return sub

            ego = nx.ego_graph(self.graph, center, radius=radius)

            for node_name, node_data in ego.nodes(data=True):
                entity = Entity(
                    name=node_name,
                    entity_type=node_data.get("entity_type", "concept"),
                    description=node_data.get("description", ""),
                    properties=node_data.get("properties", {}),
                )
                sub.add_entity(entity)

            for source, target, edge_data in ego.edges(data=True):
                relation = Relation(
                    source=source,
                    target=target,
                    relation_type=edge_data.get("relation_type", "related_to"),
                    weight=edge_data.get("weight", 1.0),
                    metadata=edge_data.get("metadata", {}),
                )
                sub.add_relation(relation)

        return sub

    # ------------------------------------------------------------------
    # Graph analysis
    # ------------------------------------------------------------------

    def entity_count(self) -> int:
        """Return the number of entities in the graph."""
        with self._lock:
            return self.graph.number_of_nodes()

    def relation_count(self) -> int:
        """Return the number of directed relations in the graph."""
        with self._lock:
            return self.graph.number_of_edges()

    def get_entity_types(self) -> list[str]:
        """Return a sorted list of unique entity types present in the graph."""
        with self._lock:
            types: set[str] = set()
            for node_data in self.graph.nodes.values():
                t = node_data.get("entity_type", "concept")
                if t:
                    types.add(t)
            return sorted(types)

    def get_relation_types(self) -> list[str]:
        """Return a sorted list of unique relation types present in the graph."""
        with self._lock:
            types: set[str] = set()
            for edge_data in self.graph.edges.values():
                rt = edge_data.get("relation_type")
                if rt:
                    types.add(rt)
            return sorted(types)

    def most_connected_entities(
        self, top_k: int = 10
    ) -> list[tuple[str, int]]:
        """Return the entities with the highest total degree.

        Args:
            top_k: Number of top entities to return.

        Returns:
            A list of ``(entity_name, degree)`` tuples sorted by descending degree.
        """
        with self._lock:
            degree_list = sorted(
                self.graph.degree(), key=lambda x: x[1], reverse=True
            )
            return degree_list[:top_k]

    def get_statistics(self) -> dict:
        """Return a dictionary of summary statistics about the graph.

        Returns:
            A dict containing entity_count, relation_count, entity_types,
            relation_types, most_connected_entities, density, and
            is_connected (for the undirected projection).
        """
        with self._lock:
            n = self.graph.number_of_nodes()
            m = self.graph.number_of_edges()

            # 内联计算密度，避免重复获取锁
            if n > 1:
                max_edges = n * (n - 1)
                density = m / max_edges if self.graph.is_directed() else m / (max_edges / 2)
            else:
                density = 0.0

            # 内联计算实体类型和关系类型
            entity_types_set = set()
            relation_types_set = set()
            for _, data in self.graph.nodes(data=True):
                et = data.get("entity_type", "concept")
                if et:
                    entity_types_set.add(et)
            for _, _, data in self.graph.edges(data=True):
                rt = data.get("relation_type", "related_to")
                if rt:
                    relation_types_set.add(rt)

            # 内联计算最连接实体
            degree_pairs = sorted(self.graph.degree(), key=lambda x: x[1], reverse=True)[:10]

            # 连通性检查（仅在节点数较少时执行，大规模图跳过）
            if n > 0 and n <= 500:
                undirected = self.graph.to_undirected()
                is_connected = nx.is_connected(undirected)
            elif n > 0:
                # 大规模图：检查弱连通分量数
                is_connected = nx.number_weakly_connected_components(self.graph) <= 1
            else:
                is_connected = True

            return {
                "entity_count": n,
                "relation_count": m,
                "entity_types": sorted(entity_types_set),
                "relation_types": sorted(relation_types_set),
                "most_connected_entities": degree_pairs,
                "density": round(density, 4),
                "is_connected": is_connected,
            }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_to_json(self, path: str) -> None:
        """Export the knowledge graph to a JSON file.

        Args:
            path: Destination file path.
        """
        with self._lock:
            data: dict = {
                "nodes": [],
                "edges": [],
            }
            for node_name, node_data in self.graph.nodes(data=True):
                data["nodes"].append(
                    {
                        "name": node_name,
                        "entity_type": node_data.get("entity_type", "concept"),
                        "description": node_data.get("description", ""),
                        "properties": node_data.get("properties", {}),
                    }
                )
            for source, target, edge_data in self.graph.edges(data=True):
                data["edges"].append(
                    {
                        "source": source,
                        "target": target,
                        "relation_type": edge_data.get("relation_type", "related_to"),
                        "weight": edge_data.get("weight", 1.0),
                        "metadata": edge_data.get("metadata", {}),
                    }
                )

        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    def load_from_json(self, path: str) -> None:
        """Import a knowledge graph from a JSON file.

        This replaces the current graph contents with the loaded data.

        Args:
            path: Source file path.
        """
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        with self._lock:
            self.graph.clear()

        for node_info in data.get("nodes", []):
            entity = Entity(
                name=node_info["name"],
                entity_type=node_info.get("entity_type", "concept"),
                description=node_info.get("description", ""),
                properties=node_info.get("properties", {}),
            )
            self.add_entity(entity)

        for edge_info in data.get("edges", []):
            relation = Relation(
                source=edge_info["source"],
                target=edge_info["target"],
                relation_type=edge_info.get("relation_type", "related_to"),
                weight=edge_info.get("weight", 1.0),
                metadata=edge_info.get("metadata", {}),
            )
            self.add_relation(relation)

    def export_to_graphml(self, path: str) -> None:
        """Export the knowledge graph to GraphML format.

        GraphML is widely supported by graph visualisation tools such as
        Gephi, Cytoscape, and yEd.

        Args:
            path: Destination file path.
        """
        with self._lock:
            # NetworkX can serialise string and numeric attributes directly,
            # but dict attributes need special handling. We convert them to
            # JSON strings for safe serialisation.
            g = self.graph.copy()
            for node_name, node_data in g.nodes(data=True):
                props = node_data.get("properties", {})
                if isinstance(props, dict):
                    node_data["properties_json"] = json.dumps(props, ensure_ascii=False)
                    node_data["properties"] = ""
            for source, target, edge_data in g.edges(data=True):
                meta = edge_data.get("metadata", {})
                if isinstance(meta, dict):
                    edge_data["metadata_json"] = json.dumps(meta, ensure_ascii=False)
                    edge_data["metadata"] = ""

            nx.write_graphml(g, path)

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def add_entities(self, entities: list[Entity]) -> list[str]:
        """Add multiple entities to the graph in a single lock acquisition.

        Args:
            entities: A list of Entity objects.

        Returns:
            A list of entity names that were added.
        """
        names: list[str] = []
        with self._lock:
            for entity in entities:
                self.graph.add_node(
                    entity.name,
                    entity_type=entity.entity_type,
                    description=entity.description,
                    properties=entity.properties,
                )
                names.append(entity.name)
        return names

    def add_relations(self, relations: list[Relation]) -> list[str]:
        """Add multiple relations to the graph in a single lock acquisition.

        Args:
            relations: A list of Relation objects.

        Returns:
            A list of string identifiers for the added relations.
        """
        ids: list[str] = []
        with self._lock:
            for relation in relations:
                for node_name in (relation.source, relation.target):
                    if not self.graph.has_node(node_name):
                        self.graph.add_node(
                            node_name,
                            entity_type="concept",
                            description="",
                            properties={},
                        )
                self.graph.add_edge(
                    relation.source,
                    relation.target,
                    relation_type=relation.relation_type,
                    weight=relation.weight,
                    metadata=relation.metadata,
                )
                ids.append(
                    f"{relation.source} -> {relation.target} [{relation.relation_type}]"
                )
        return ids

    def merge(self, other: KnowledgeGraph) -> KnowledgeGraph:
        """Merge another knowledge graph into this one.

        Entities and relations from *other* are added to this graph. Where
        conflicts arise (same entity name), the attributes from *other*
        overwrite those in this graph.

        Args:
            other: Another KnowledgeGraph instance to merge in.

        Returns:
            This KnowledgeGraph instance (after merging).
        """
        with other._lock:
            other_nodes = list(other.graph.nodes(data=True))
            other_edges = list(other.graph.edges(data=True))

        with self._lock:
            for node_name, node_data in other_nodes:
                self.graph.add_node(
                    node_name,
                    entity_type=node_data.get("entity_type", "concept"),
                    description=node_data.get("description", ""),
                    properties=node_data.get("properties", {}),
                )
            for source, target, edge_data in other_edges:
                self.graph.add_edge(
                    source,
                    target,
                    relation_type=edge_data.get("relation_type", "related_to"),
                    weight=edge_data.get("weight", 1.0),
                    metadata=edge_data.get("metadata", {}),
                )

        return self

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _node_to_entity(self, node_name: str) -> Entity:
        """Convert a graph node to an Entity object (caller must hold lock)."""
        node_data = self.graph.nodes[node_name]
        return Entity(
            name=node_name,
            entity_type=node_data.get("entity_type", "concept"),
            description=node_data.get("description", ""),
            properties=node_data.get("properties", {}),
        )

    def _edge_to_relation(self, source: str, target: str) -> Relation:
        """Convert a graph edge to a Relation object (caller must hold lock)."""
        edge_data = self.graph[source][target]
        return Relation(
            source=source,
            target=target,
            relation_type=edge_data.get("relation_type", "related_to"),
            weight=edge_data.get("weight", 1.0),
            metadata=edge_data.get("metadata", {}),
        )


class KnowledgeGraphBuilder:
    """Helper class for building knowledge graphs from unstructured text.

    This builder uses simple rule-based pattern matching to extract entities
    and relations from Chinese text. It is intended as a lightweight
    alternative to full NLP pipelines and works best with sentences that
    follow common relational patterns.
    """

    # Mapping from textual pattern to relation type
    _PATTERNS: list[tuple[re.Pattern[str], str]] = []

    @classmethod
    def _compile_patterns(cls) -> None:
        """Lazily compile the regex patterns on first use."""
        if cls._PATTERNS:
            return
        raw_patterns = [
            (r"(\S+?)是(\S+?)[。,，！!？?；;]?", "is_a"),
            (r"(\S+?)属于(\S+?)[。,，！!？?；;]?", "belongs_to"),
            (r"(\S+?)包含(\S+?)[。,，！!？?；;]?", "contains"),
            (r"(\S+?)位于(\S+?)[。,，！!？?；;]?", "located_in"),
            (r"(\S+?)有(\S+?)[。,，！!？?；;]?", "has"),
            (r"(\S+?)是一种(\S+?)[。,，！!？?；;]?", "is_a"),
            (r"(\S+?)是(\S+?)的一种[。,，！!？?；;]?", "is_a"),
            (r"(\S+?)是(\S+?)的一部分[。,，！!？?；;]?", "part_of"),
            (r"(\S+?)依赖于(\S+?)[。,，！!？?；;]?", "depends_on"),
            (r"(\S+?)影响(\S+?)[。,，！!？?；;]?", "influences"),
            (r"(\S+?)创建于(\S+?)[。,，！!？?；;]?", "created_in"),
            (r"(\S+?)工作在(\S+?)[。,，！!？?；;]?", "works_in"),
            (r"(\S+?)学习(\S+?)[。,，！!？?；;]?", "studies"),
            (r"(\S+?)喜欢(\S+?)[。,，！!？?；;]?", "likes"),
            (r"(\S+?)生产(\S+?)[。,，！!？?；;]?", "produces"),
            (r"(\S+?)使用(\S+?)[。,，！!？?；;]?", "uses"),
        ]
        for pattern_str, rel_type in raw_patterns:
            cls._PATTERNS.append((re.compile(pattern_str), rel_type))

    @classmethod
    def extract_entities_and_relations(
        cls, text: str
    ) -> tuple[list[Entity], list[Relation]]:
        """Extract entities and relations from text using rule-based patterns.

        The method scans each sentence for known relational patterns
        (e.g., ``"A是B"``, ``"A属于B"``) and creates Entity/Relation objects.

        Args:
            text: Input text (Chinese sentences expected).

        Returns:
            A tuple of ``(entities, relations)`` extracted from the text.
        """
        cls._compile_patterns()

        entities_dict: dict[str, Entity] = {}
        relations: list[Relation] = []

        # Split text into sentences
        sentences = re.split(r"[。！!？?\n]+", text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            for pattern, rel_type in cls._PATTERNS:
                match = pattern.search(sentence)
                if match:
                    source_name = match.group(1).strip()
                    target_name = match.group(2).strip()

                    # Skip trivial or empty matches
                    if not source_name or not target_name:
                        continue
                    if len(source_name) < 1 or len(target_name) < 1:
                        continue

                    # Register entities
                    if source_name not in entities_dict:
                        entities_dict[source_name] = Entity(name=source_name)
                    if target_name not in entities_dict:
                        entities_dict[target_name] = Entity(name=target_name)

                    # Avoid duplicate relations
                    is_duplicate = any(
                        r.source == source_name
                        and r.target == target_name
                        and r.relation_type == rel_type
                        for r in relations
                    )
                    if not is_duplicate:
                        relations.append(
                            Relation(
                                source=source_name,
                                target=target_name,
                                relation_type=rel_type,
                            )
                        )

        return list(entities_dict.values()), relations

    @classmethod
    def build_from_text(
        cls, text: str, kg: KnowledgeGraph | None = None
    ) -> KnowledgeGraph:
        """Extract entities and relations from text and add them to a graph.

        Args:
            text: Input text to process.
            kg: An existing KnowledgeGraph to add to. If None, a new one is created.

        Returns:
            The KnowledgeGraph with the extracted data.
        """
        if kg is None:
            kg = KnowledgeGraph()

        entities, relations = cls.extract_entities_and_relations(text)
        kg.add_entities(entities)
        kg.add_relations(relations)
        return kg


__all__ = [
    "Entity",
    "Relation",
    "GraphSearchResult",
    "KnowledgeGraph",
    "KnowledgeGraphBuilder",
]
