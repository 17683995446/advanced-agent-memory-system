"""Unit tests for the event bus module."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.infra.blinker_event_bus import (
    EventBus,
    StorageEvent,
    StorageEventType,
    StorageSource,
    get_event_bus,
    reset_event_bus,
    on_memory_add,
    on_memory_update,
    on_memory_delete,
)


class TestStorageEvent:
    """Test StorageEvent dataclass"""
    
    def test_create_event_with_defaults(self):
        """Test creating event with defaults"""
        event = StorageEvent()
        assert event.event_id is not None
        assert event.event_type == StorageEventType.MEMORY_ADD
        assert event.source == StorageSource.LONG_TERM
        assert event.data == {}
    
    def test_create_event_with_data(self):
        """Test creating event with data"""
        event = StorageEvent(
            event_type=StorageEventType.VECTOR_ADD,
            source=StorageSource.VECTOR_STORE,
            data={"content": "test"},
            metadata={"key": "value"},
        )
        assert event.event_type == StorageEventType.VECTOR_ADD
        assert event.source == StorageSource.VECTOR_STORE
        assert event.data == {"content": "test"}
    
    def test_to_dict_and_from_dict(self):
        """Test serialization"""
        event = StorageEvent(
            event_type=StorageEventType.MEMORY_UPDATE,
            source=StorageSource.SHORT_TERM,
            data={"id": "123"},
            correlation_id="corr-123",
        )
        
        data = event.to_dict()
        assert data["event_type"] == "memory_update"
        assert data["source"] == "short_term"
        assert data["correlation_id"] == "corr-123"
        
        restored = StorageEvent.from_dict(data)
        assert restored.event_type == StorageEventType.MEMORY_UPDATE
        assert restored.source == StorageSource.SHORT_TERM
        assert restored.correlation_id == "corr-123"


class TestEventBus:
    """Test EventBus class"""
    
    def setup_method(self):
        """Reset event bus before each test"""
        reset_event_bus()
    
    def test_create_event_bus(self):
        """Test creating event bus"""
        bus = EventBus()
        assert bus is not None
    
    def test_emit_event(self):
        """Test emitting event"""
        bus = EventBus()
        
        event = bus.emit(
            StorageEventType.MEMORY_ADD,
            source=StorageSource.LONG_TERM,
            data={"content": "test"},
        )
        
        assert event.event_id is not None
        assert event.event_type == StorageEventType.MEMORY_ADD
    
    def test_subscribe_with_decorator(self):
        """Test subscribing with decorator"""
        bus = EventBus()
        received = []
        
        @bus.on(StorageEventType.MEMORY_ADD)
        def handler(event):
            received.append(event)
        
        bus.emit(StorageEventType.MEMORY_ADD, data={"test": 1})
        
        assert len(received) == 1
        assert received[0].data == {"test": 1}
    
    def test_subscribe_with_source_filter(self):
        """Test subscribing with source filter"""
        bus = EventBus()
        received = []
        
        @bus.on(StorageEventType.MEMORY_ADD, source_filter=StorageSource.LONG_TERM)
        def handler(event):
            received.append(event)
        
        bus.emit(StorageEventType.MEMORY_ADD, source=StorageSource.LONG_TERM, data={"a": 1})
        bus.emit(StorageEventType.MEMORY_ADD, source=StorageSource.SHORT_TERM, data={"b": 2})
        
        assert len(received) == 1
        assert received[0].data == {"a": 1}
    
    def test_subscribe_programmatically(self):
        """Test programmatic subscription"""
        bus = EventBus()
        received = []
        
        def handler(event):
            received.append(event)
        
        bus.subscribe(StorageEventType.MEMORY_UPDATE, handler)
        
        bus.emit(StorageEventType.MEMORY_UPDATE, data={"test": 1})
        
        assert len(received) == 1
    
    def test_unsubscribe(self):
        """Test unsubscribing"""
        bus = EventBus()
        received = []
        
        def handler(event):
            received.append(event)
        
        bus.subscribe(StorageEventType.MEMORY_DELETE, handler)
        bus.emit(StorageEventType.MEMORY_DELETE, data={"test": 1})
        
        assert len(received) == 1
        
        bus.unsubscribe(StorageEventType.MEMORY_DELETE, handler)
        bus.emit(StorageEventType.MEMORY_DELETE, data={"test": 2})
        
        assert len(received) == 1  # Should still be 1
    
    def test_subscribe_multiple(self):
        """Test subscribing to multiple events"""
        bus = EventBus()
        received = []
        
        @bus.on_multiple([StorageEventType.MEMORY_ADD, StorageEventType.MEMORY_UPDATE])
        def handler(event):
            received.append(event.event_type)
        
        bus.emit(StorageEventType.MEMORY_ADD, data={})
        bus.emit(StorageEventType.MEMORY_UPDATE, data={})
        bus.emit(StorageEventType.MEMORY_DELETE, data={})
        
        assert len(received) == 2
        assert StorageEventType.MEMORY_ADD in received
        assert StorageEventType.MEMORY_UPDATE in received
    
    def test_event_history(self):
        """Test event history"""
        bus = EventBus(history_size=10)
        
        for i in range(5):
            bus.emit(StorageEventType.MEMORY_ADD, data={"index": i})
        
        history = bus.get_history()
        assert len(history) == 5
    
    def test_event_history_with_filter(self):
        """Test event history with filter"""
        bus = EventBus()
        
        bus.emit(StorageEventType.MEMORY_ADD, source=StorageSource.LONG_TERM, data={})
        bus.emit(StorageEventType.MEMORY_ADD, source=StorageSource.SHORT_TERM, data={})
        bus.emit(StorageEventType.MEMORY_UPDATE, source=StorageSource.LONG_TERM, data={})
        
        history = bus.get_history(event_type=StorageEventType.MEMORY_ADD)
        assert len(history) == 2
        
        history = bus.get_history(source=StorageSource.LONG_TERM)
        assert len(history) == 2
    
    def test_clear_history(self):
        """Test clearing history"""
        bus = EventBus()
        
        bus.emit(StorageEventType.MEMORY_ADD, data={})
        assert len(bus.get_history()) == 1
        
        bus.clear_history()
        assert len(bus.get_history()) == 0
    
    def test_history_size_limit(self):
        """Test history size limit"""
        bus = EventBus(history_size=3)
        
        for i in range(5):
            bus.emit(StorageEventType.MEMORY_ADD, data={"index": i})
        
        history = bus.get_history()
        assert len(history) == 3
        # Should have the last 3 events
        assert history[0].data["index"] == 2
    
    def test_get_stats(self):
        """Test getting stats"""
        bus = EventBus()
        
        @bus.on(StorageEventType.MEMORY_ADD)
        def handler(event):
            pass
        
        stats = bus.get_stats()
        
        assert stats["history_size"] == 0
        assert stats["max_history_size"] == 1000
        assert stats["subscriber_count"] == 1
    
    def test_get_subscribers(self):
        """Test getting subscribers"""
        bus = EventBus()
        
        @bus.on(StorageEventType.MEMORY_ADD)
        def handler(event):
            pass
        
        subscribers = bus.get_subscribers(StorageEventType.MEMORY_ADD)
        assert len(subscribers) == 1


class TestGlobalEventBus:
    """Test global event bus functions"""
    
    def setup_method(self):
        """Reset before each test"""
        reset_event_bus()
    
    def test_get_event_bus_singleton(self):
        """Test global event bus singleton"""
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        
        assert bus1 is bus2
    
    def test_reset_event_bus(self):
        """Test resetting global event bus"""
        bus1 = get_event_bus()
        reset_event_bus()
        bus2 = get_event_bus()
        
        assert bus1 is not bus2


class TestConvenienceDecorators:
    """Test convenience decorators"""
    
    def setup_method(self):
        """Reset before each test"""
        reset_event_bus()
    
    def test_on_memory_add(self):
        """Test on_memory_add decorator"""
        received = []
        
        @on_memory_add
        def handler(event):
            received.append(event)
        
        bus = get_event_bus()
        bus.emit(StorageEventType.MEMORY_ADD, data={"test": 1})
        
        assert len(received) == 1
    
    def test_on_memory_update(self):
        """Test on_memory_update decorator"""
        received = []
        
        @on_memory_update
        def handler(event):
            received.append(event)
        
        bus = get_event_bus()
        bus.emit(StorageEventType.MEMORY_UPDATE, data={"test": 1})
        
        assert len(received) == 1
    
    def test_on_memory_delete(self):
        """Test on_memory_delete decorator"""
        received = []
        
        @on_memory_delete
        def handler(event):
            received.append(event)
        
        bus = get_event_bus()
        bus.emit(StorageEventType.MEMORY_DELETE, data={"test": 1})
        
        assert len(received) == 1


class TestEventTypes:
    """Test all event types"""
    
    def test_all_event_types_defined(self):
        """Test all event types are defined"""
        expected_types = [
            "MEMORY_ADD",
            "MEMORY_UPDATE",
            "MEMORY_DELETE",
            "MEMORY_ACCESS",
            "VECTOR_ADD",
            "VECTOR_SEARCH",
            "VECTOR_DELETE",
            "ENTITY_ADD",
            "ENTITY_DELETE",
            "RELATION_ADD",
            "RELATION_DELETE",
            "RECORD_INSERT",
            "RECORD_UPDATE",
            "RECORD_DELETE",
            "CACHE_HIT",
            "CACHE_MISS",
            "SYNC_START",
            "SYNC_COMPLETE",
            "SYNC_ERROR",
        ]
        
        for type_name in expected_types:
            assert hasattr(StorageEventType, type_name)
    
    def test_all_sources_defined(self):
        """Test all sources are defined"""
        expected_sources = [
            "SHORT_TERM",
            "LONG_TERM",
            "VECTOR_STORE",
            "KNOWLEDGE_GRAPH",
            "STRUCTURED_STORE",
            "CACHE",
            "EXTERNAL",
        ]
        
        for source_name in expected_sources:
            assert hasattr(StorageSource, source_name)
