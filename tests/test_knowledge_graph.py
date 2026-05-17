"""Unit tests for the knowledge_graph module."""
import pytest
import json
import os
import tempfile
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.processing.knowledge_graph_engine import (
    Entity,
    Relation,
    GraphSearchResult,
    KnowledgeGraph,
    KnowledgeGraphBuilder,
)


# ======================================================================
# TestEntity
# ======================================================================


class TestEntity:
    """Tests for the Entity model."""

    def test_create_with_defaults(self):
        """Entity(name='test') should have default entity_type='concept'."""
        entity = Entity(name="test")
        assert entity.name == "test"
        assert entity.entity_type == "concept"
        assert entity.description == ""
        assert entity.properties == {}

    def test_create_with_properties(self):
        """Entity created with custom properties should store them."""
        entity = Entity(name="test", properties={"age": 30})
        assert entity.properties == {"age": 30}

    def test_equality(self):
        """Two entities with the same name should be considered equal."""
        e1 = Entity(name="alice", entity_type="person")
        e2 = Entity(name="alice", entity_type="person")
        assert e1 == e2


# ======================================================================
# TestRelation
# ======================================================================


class TestRelation:
    """Tests for the Relation model."""

    def test_create(self):
        """Relation should store source, target, and relation_type."""
        rel = Relation(source="A", target="B", relation_type="knows")
        assert rel.source == "A"
        assert rel.target == "B"
        assert rel.relation_type == "knows"

    def test_default_weight(self):
        """Weight should default to 1.0 when not specified."""
        rel = Relation(source="A", target="B", relation_type="knows")
        assert rel.weight == 1.0


# ======================================================================
# TestKnowledgeGraph
# ======================================================================


class TestKnowledgeGraph:
    """Tests for the KnowledgeGraph class."""

    def test_add_entity(self):
        """Adding an entity should increase entity_count to 1."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="test"))
        assert kg.entity_count() == 1

    def test_add_duplicate_entity(self):
        """Adding an entity with the same name should update, not duplicate."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="test", entity_type="person"))
        kg.add_entity(Entity(name="test", entity_type="concept"))
        assert kg.entity_count() == 1
        entity = kg.get_entity("test")
        assert entity.entity_type == "concept"

    def test_remove_entity(self):
        """Adding then removing an entity should leave entity_count at 0."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="test"))
        kg.remove_entity("test")
        assert kg.entity_count() == 0

    def test_add_relation(self):
        """Adding 2 entities and a relation should yield relation_count 1."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="A"))
        kg.add_entity(Entity(name="B"))
        kg.add_relation(Relation(source="A", target="B", relation_type="knows"))
        assert kg.relation_count() == 1

    def test_remove_relation(self):
        """Adding then removing a relation should leave relation_count at 0."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="A"))
        kg.add_entity(Entity(name="B"))
        kg.add_relation(Relation(source="A", target="B", relation_type="knows"))
        kg.remove_relation("A", "B", "knows")
        assert kg.relation_count() == 0

    def test_get_entity(self):
        """get_entity should return the entity that was added."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="alice", entity_type="person", description="A person"))
        entity = kg.get_entity("alice")
        assert entity is not None
        assert entity.name == "alice"
        assert entity.entity_type == "person"
        assert entity.description == "A person"

    def test_get_entity_nonexistent(self):
        """get_entity for a nonexistent name should return None."""
        kg = KnowledgeGraph()
        assert kg.get_entity("nonexistent") is None

    def test_get_relations_outgoing(self):
        """get_relations with direction='outgoing' should return all outgoing edges."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="A"))
        kg.add_entity(Entity(name="B"))
        kg.add_entity(Entity(name="C"))
        kg.add_relation(Relation(source="A", target="B", relation_type="knows"))
        kg.add_relation(Relation(source="A", target="C", relation_type="knows"))
        relations = kg.get_relations("A", direction="outgoing")
        assert len(relations) == 2

    def test_get_relations_incoming(self):
        """get_relations with direction='incoming' should return all incoming edges."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="A"))
        kg.add_entity(Entity(name="B"))
        kg.add_relation(Relation(source="A", target="B", relation_type="knows"))
        relations = kg.get_relations("B", direction="incoming")
        assert len(relations) == 1
        assert relations[0].source == "A"
        assert relations[0].target == "B"

    def test_get_neighbors(self):
        """get_neighbors with max_depth=2 should include entities 2 hops away."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="A"))
        kg.add_entity(Entity(name="B"))
        kg.add_entity(Entity(name="C"))
        kg.add_relation(Relation(source="A", target="B", relation_type="knows"))
        kg.add_relation(Relation(source="B", target="C", relation_type="knows"))
        neighbors = kg.get_neighbors("A", max_depth=2)
        neighbor_names = {e.name for e in neighbors}
        assert "B" in neighbor_names
        assert "C" in neighbor_names

    def test_search_entities_fuzzy(self):
        """Searching for 'Python' should find 'Python编程语言' via fuzzy match."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="Python编程语言", entity_type="language"))
        results = kg.search_entities("Python")
        assert len(results) >= 1
        names = [e.name for e, _ in results]
        assert "Python编程语言" in names

    def test_find_path_exists(self):
        """find_path between connected entities should return the path."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="A"))
        kg.add_entity(Entity(name="B"))
        kg.add_entity(Entity(name="C"))
        kg.add_relation(Relation(source="A", target="B", relation_type="knows"))
        kg.add_relation(Relation(source="B", target="C", relation_type="knows"))
        path = kg.find_path("A", "C")
        assert path == ["A", "B", "C"]

    def test_find_path_not_exists(self):
        """find_path between disconnected entities should return None."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="A"))
        kg.add_entity(Entity(name="B"))
        kg.add_entity(Entity(name="C"))
        kg.add_entity(Entity(name="D"))
        kg.add_relation(Relation(source="A", target="B", relation_type="knows"))
        kg.add_relation(Relation(source="C", target="D", relation_type="knows"))
        path = kg.find_path("A", "D")
        assert path is None

    def test_find_related(self):
        """find_related should return related entities sorted by descending score."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="A"))
        kg.add_entity(Entity(name="B"))
        kg.add_entity(Entity(name="C"))
        kg.add_relation(Relation(source="A", target="B", relation_type="knows"))
        kg.add_relation(Relation(source="A", target="C", relation_type="likes"))
        results = kg.find_related("A")
        assert len(results) >= 1
        # Scores should be sorted in descending order
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_entity_count(self):
        """An empty graph should have entity_count 0."""
        kg = KnowledgeGraph()
        assert kg.entity_count() == 0

    def test_relation_count(self):
        """An empty graph should have relation_count 0."""
        kg = KnowledgeGraph()
        assert kg.relation_count() == 0

    def test_get_entity_types(self):
        """get_entity_types should return a sorted list of unique entity types."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="A", entity_type="person"))
        kg.add_entity(Entity(name="B", entity_type="location"))
        kg.add_entity(Entity(name="C", entity_type="person"))
        types = kg.get_entity_types()
        assert types == ["location", "person"]

    def test_get_relation_types(self):
        """get_relation_types should return a sorted list of unique relation types."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="A"))
        kg.add_entity(Entity(name="B"))
        kg.add_entity(Entity(name="C"))
        kg.add_relation(Relation(source="A", target="B", relation_type="knows"))
        kg.add_relation(Relation(source="A", target="C", relation_type="likes"))
        types = kg.get_relation_types()
        assert types == ["knows", "likes"]

    def test_most_connected(self):
        """most_connected_entities should return entities sorted by connection count."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="A"))
        kg.add_entity(Entity(name="B"))
        kg.add_entity(Entity(name="C"))
        kg.add_entity(Entity(name="D"))
        kg.add_relation(Relation(source="A", target="B", relation_type="knows"))
        kg.add_relation(Relation(source="A", target="C", relation_type="knows"))
        kg.add_relation(Relation(source="A", target="D", relation_type="knows"))
        kg.add_relation(Relation(source="B", target="C", relation_type="likes"))
        result = kg.most_connected_entities(top_k=2)
        assert len(result) == 2
        # A has degree 3, B has degree 2
        assert result[0] == ("A", 3)
        assert result[1] == ("B", 2)

    def test_merge(self):
        """Merging two graphs should combine all entities and relations."""
        kg1 = KnowledgeGraph()
        kg1.add_entity(Entity(name="A"))
        kg1.add_entity(Entity(name="B"))
        kg1.add_relation(Relation(source="A", target="B", relation_type="knows"))

        kg2 = KnowledgeGraph()
        kg2.add_entity(Entity(name="C"))
        kg2.add_entity(Entity(name="D"))
        kg2.add_relation(Relation(source="C", target="D", relation_type="likes"))

        kg1.merge(kg2)
        assert kg1.entity_count() == 4
        assert kg1.relation_count() == 2

    def test_save_and_load_json(self):
        """Saving to JSON and loading into a new graph should preserve data."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="Alice", entity_type="person", description="A person"))
        kg.add_entity(Entity(name="Bob", entity_type="person"))
        kg.add_relation(Relation(source="Alice", target="Bob", relation_type="knows", weight=0.8))

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmp_path = f.name

        try:
            kg.save_to_json(tmp_path)

            kg2 = KnowledgeGraph()
            kg2.load_from_json(tmp_path)

            assert kg2.entity_count() == 2
            assert kg2.relation_count() == 1
            alice = kg2.get_entity("Alice")
            assert alice is not None
            assert alice.entity_type == "person"
            assert alice.description == "A person"
        finally:
            os.unlink(tmp_path)

    def test_export_graphml(self):
        """export_to_graphml should create a .graphml file."""
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="A"))
        kg.add_entity(Entity(name="B"))
        kg.add_relation(Relation(source="A", target="B", relation_type="knows"))

        with tempfile.NamedTemporaryFile(suffix=".graphml", delete=False) as f:
            tmp_path = f.name

        try:
            kg.export_to_graphml(tmp_path)
            assert os.path.exists(tmp_path)
            assert os.path.getsize(tmp_path) > 0
        finally:
            os.unlink(tmp_path)


# ======================================================================
# TestKnowledgeGraphBuilder
# ======================================================================


class TestKnowledgeGraphBuilder:
    """Tests for the KnowledgeGraphBuilder class."""

    def test_extract_from_simple_text(self):
        """'张三是工程师' should extract entity '张三'."""
        entities, relations = KnowledgeGraphBuilder.extract_entities_and_relations(
            "张三是工程师"
        )
        names = [e.name for e in entities]
        assert "张三" in names

    def test_build_from_text(self):
        """build_from_text should create a graph with entities and relations."""
        kg = KnowledgeGraphBuilder.build_from_text("张三是工程师")
        assert kg.entity_count() >= 1
        assert kg.relation_count() >= 1

    def test_build_from_text_multiple_sentences(self):
        """Longer text with multiple sentences should extract more entities."""
        text = "张三是工程师。李四是医生。张三喜欢Python。"
        kg = KnowledgeGraphBuilder.build_from_text(text)
        assert kg.entity_count() >= 3
        assert kg.relation_count() >= 2
