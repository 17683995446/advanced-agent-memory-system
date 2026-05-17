"""Unit tests for the SQLModel ORM store module."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.storage.sqlmodel_orm_store import (
    ORMStore,
    ORMQuery,
    MemoryRecordORM,
    InteractionORM,
    PreferenceORM,
    FactORM,
    create_orm_store,
)
from sqlmodel import col


class TestMemoryRecordORM:
    """Test MemoryRecordORM model"""
    
    def test_create_with_defaults(self):
        """Test creating record with defaults"""
        record = MemoryRecordORM(content="Test content")
        assert record.content == "Test content"
        assert record.memory_type == "semantic"
        assert record.category == "general"
        assert record.importance == 0.5
    
    def test_tags_property(self):
        """Test tags JSON property"""
        record = MemoryRecordORM(content="Test")
        record.tags = ["tag1", "tag2"]
        assert record.tags == ["tag1", "tag2"]
        assert record.tags_json == '["tag1", "tag2"]'
    
    def test_metadata_property(self):
        """Test metadata JSON property"""
        record = MemoryRecordORM(content="Test")
        record.meta = {"key": "value"}
        assert record.meta == {"key": "value"}


class TestInteractionORM:
    """Test InteractionORM model"""
    
    def test_create_interaction(self):
        """Test creating interaction"""
        interaction = InteractionORM(
            session_id="session1",
            role="user",
            content="Hello"
        )
        assert interaction.session_id == "session1"
        assert interaction.role == "user"
        assert interaction.content == "Hello"


class TestPreferenceORM:
    """Test PreferenceORM model"""
    
    def test_create_preference(self):
        """Test creating preference"""
        pref = PreferenceORM(
            user_id="user1",
            key="theme",
            value_json='"dark"'
        )
        assert pref.user_id == "user1"
        assert pref.key == "theme"
        assert pref.value == "dark"


class TestFactORM:
    """Test FactORM model"""
    
    def test_create_fact(self):
        """Test creating fact"""
        fact = FactORM(
            subject="Python",
            predicate="is_a",
            object="programming_language"
        )
        assert fact.subject == "Python"
        assert fact.predicate == "is_a"
        assert fact.object == "programming_language"
        assert fact.confidence == 1.0


class TestORMStore:
    """Test ORMStore class"""
    
    def test_create_memory_store(self):
        """Test creating in-memory store"""
        store = create_orm_store(":memory:")
        assert store is not None
        store.close()
    
    def test_add_and_get_record(self):
        """Test adding and getting record"""
        store = create_orm_store(":memory:")
        
        record = MemoryRecordORM(content="Test content", category="test")
        added = store.add(record)
        
        assert added.id is not None
        
        retrieved = store.get(MemoryRecordORM, added.id)
        assert retrieved is not None
        assert retrieved.content == "Test content"
        assert retrieved.category == "test"
        
        store.close()
    
    def test_add_batch(self):
        """Test batch add"""
        store = create_orm_store(":memory:")
        
        records = [
            MemoryRecordORM(content=f"Content {i}")
            for i in range(5)
        ]
        added = store.add_batch(records)
        
        assert len(added) == 5
        for r in added:
            assert r.id is not None
        
        store.close()
    
    def test_update_record(self):
        """Test updating record"""
        store = create_orm_store(":memory:")
        
        record = MemoryRecordORM(content="Original")
        added = store.add(record)
        
        added.content = "Updated"
        updated = store.update(added)
        
        assert updated.content == "Updated"
        
        store.close()
    
    def test_delete_record(self):
        """Test deleting record"""
        store = create_orm_store(":memory:")
        
        record = MemoryRecordORM(content="To delete")
        added = store.add(record)
        
        result = store.delete_by_id(MemoryRecordORM, added.id)
        assert result is True
        
        retrieved = store.get(MemoryRecordORM, added.id)
        assert retrieved is None
        
        store.close()
    
    def test_count(self):
        """Test counting records"""
        store = create_orm_store(":memory:")
        
        for i in range(3):
            store.add(MemoryRecordORM(content=f"Content {i}"))
        
        count = store.count(MemoryRecordORM)
        assert count == 3
        
        store.close()
    
    def test_query_builder(self):
        """Test query builder"""
        store = create_orm_store(":memory:")
        
        # Add records with different categories
        store.add(MemoryRecordORM(content="A", category="cat1"))
        store.add(MemoryRecordORM(content="B", category="cat2"))
        store.add(MemoryRecordORM(content="C", category="cat1"))
        
        # Query by category
        from sqlmodel import col
        results = store.query(MemoryRecordORM).where(
            col(MemoryRecordORM.category) == "cat1"
        ).all()
        
        assert len(results) == 2
        
        store.close()
    
    def test_query_limit_offset(self):
        """Test query with limit and offset"""
        store = create_orm_store(":memory:")
        
        for i in range(10):
            store.add(MemoryRecordORM(content=f"Content {i}"))
        
        results = store.query(MemoryRecordORM).limit(5).all()
        assert len(results) == 5
        
        store.close()


class TestORMQuery:
    """Test ORMQuery class"""
    
    def test_query_all(self):
        """Test query all"""
        store = create_orm_store(":memory:")
        
        for i in range(3):
            store.add(MemoryRecordORM(content=f"Content {i}"))
        
        results = store.query(MemoryRecordORM).all()
        assert len(results) == 3
        
        store.close()
    
    def test_query_first(self):
        """Test query first"""
        store = create_orm_store(":memory:")
        
        store.add(MemoryRecordORM(content="First"))
        
        result = store.query(MemoryRecordORM).first()
        assert result is not None
        assert result.content == "First"
        
        store.close()
    
    def test_query_count(self):
        """Test query count"""
        store = create_orm_store(":memory:")
        
        for i in range(5):
            store.add(MemoryRecordORM(content=f"Content {i}"))
        
        count = store.query(MemoryRecordORM).count()
        assert count == 5
        
        store.close()


class TestInteractions:
    """Test interaction operations"""
    
    def test_add_interaction(self):
        """Test adding interaction"""
        store = create_orm_store(":memory:")
        
        interaction = InteractionORM(
            session_id="session1",
            role="user",
            content="Hello"
        )
        added = store.add(interaction)
        
        assert added.id is not None
        
        store.close()
    
    def test_query_by_session(self):
        """Test querying by session"""
        store = create_orm_store(":memory:")
        
        store.add(InteractionORM(session_id="s1", role="user", content="A"))
        store.add(InteractionORM(session_id="s2", role="user", content="B"))
        store.add(InteractionORM(session_id="s1", role="assistant", content="C"))
        
        from sqlmodel import col
        results = store.query(InteractionORM).where(
            col(InteractionORM.session_id) == "s1"
        ).all()
        
        assert len(results) == 2
        
        store.close()


class TestPreferences:
    """Test preference operations"""
    
    def test_upsert_preference(self):
        """Test preference upsert"""
        store = create_orm_store(":memory:")
        
        pref = PreferenceORM(user_id="u1", key="theme", value_json='"dark"')
        store.add(pref)
        
        retrieved = store.query(PreferenceORM).where(
            col(PreferenceORM.user_id) == "u1"
        ).first()
        
        assert retrieved is not None
        assert retrieved.value == "dark"
        
        store.close()


class TestFacts:
    """Test fact operations"""
    
    def test_add_fact(self):
        """Test adding fact"""
        store = create_orm_store(":memory:")
        
        fact = FactORM(
            subject="Python",
            predicate="is_a",
            object="language",
            confidence=0.9
        )
        added = store.add(fact)
        
        assert added.id is not None
        assert added.confidence == 0.9
        
        store.close()
