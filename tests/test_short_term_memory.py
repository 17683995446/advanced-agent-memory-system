"""Unit tests for the short_term_memory module."""
import pytest
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.core.short_term_working_memory import (
    ShortTermMemory,
    WorkingMemoryBuffer,
    MemoryItem,
)


# ===========================================================================
# TestMemoryItem
# ===========================================================================

class TestMemoryItem:

    def test_creation(self):
        """A MemoryItem can be created with content and default values."""
        item = MemoryItem(content="test content")
        assert item.content == "test content"
        assert item.memory_type == "general"
        assert item.importance == 0.5
        assert item.access_count == 0
        assert item.metadata == {}

    def test_priority_score(self):
        """priority_score should return a float between 0 and 1."""
        item = MemoryItem(content="score check", importance=0.8)
        score = item.priority_score
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_touch_increments_access_count(self):
        """Calling touch() should increment access_count by 1."""
        item = MemoryItem(content="touch me")
        assert item.access_count == 0

        item.touch()
        assert item.access_count == 1

        item.touch()
        assert item.access_count == 2

    def test_default_timestamp(self):
        """The default timestamp should be close to the current time."""
        before = time.time()
        item = MemoryItem(content="timestamp check")
        after = time.time()

        assert before <= item.timestamp <= after


# ===========================================================================
# TestWorkingMemoryBuffer
# ===========================================================================

class TestWorkingMemoryBuffer:

    def test_add_and_get(self):
        """Add an item and retrieve it by key."""
        buf = WorkingMemoryBuffer()
        buf.add("key1", "hello world")

        item = buf.get("key1")
        assert item is not None
        assert item.content == "hello world"

    def test_capacity_limit(self):
        """Adding more items than capacity should auto-evict the lowest priority."""
        buf = WorkingMemoryBuffer(capacity=3)
        buf.add("a", "first", importance=0.9)
        buf.add("b", "second", importance=0.5)
        buf.add("c", "third", importance=0.3)
        # Buffer is now at capacity (3). Adding a 4th should trigger eviction.
        buf.add("d", "fourth", importance=0.7)

        # The buffer should still have exactly `capacity` items.
        assert len(buf) == 3
        # "c" had the lowest importance (0.3) and should have been evicted.
        assert "c" not in buf

    def test_set_focus(self):
        """set_focus should make the given key the current focus."""
        buf = WorkingMemoryBuffer()
        buf.add("a", "alpha")
        buf.add("b", "beta")

        result = buf.set_focus("b")
        assert result is True
        assert buf.get_focus() == "b"

    def test_pop_focus(self):
        """pop_focus should remove the current focus and return the next one."""
        buf = WorkingMemoryBuffer()
        buf.add("a", "alpha")
        buf.add("b", "beta")
        buf.add("c", "gamma")

        # Focus stack after adds: [c, b, a] (newest first)
        assert buf.get_focus() == "c"

        # Pop "c" -> focus should move to "b"
        new_focus = buf.pop_focus()
        assert new_focus == "b"

        # Pop "b" -> focus should move to "a"
        new_focus = buf.pop_focus()
        assert new_focus == "a"

    def test_remove(self):
        """Removing an item should make it no longer accessible."""
        buf = WorkingMemoryBuffer()
        buf.add("key1", "will be removed")
        assert "key1" in buf

        result = buf.remove("key1")
        assert result is True
        assert "key1" not in buf
        assert buf.get("key1") is None

    def test_clear(self):
        """clear should empty the entire buffer."""
        buf = WorkingMemoryBuffer()
        buf.add("a", "alpha")
        buf.add("b", "beta")
        assert len(buf) == 2

        buf.clear()
        assert len(buf) == 0
        assert buf.get("a") is None

    def test_get_all_sorted_by_priority(self):
        """get_all should return items sorted by descending priority."""
        buf = WorkingMemoryBuffer()
        buf.add("low", "low priority", importance=0.1)
        buf.add("high", "high priority", importance=0.9)
        buf.add("mid", "mid priority", importance=0.5)

        items = buf.get_all()
        scores = [item.priority_score for _, item in items]
        # Each score should be >= the next (descending order).
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_get_context_string(self):
        """get_context_string should return a non-empty formatted string."""
        buf = WorkingMemoryBuffer()
        buf.add("task", "finish the report", importance=0.8)
        buf.add("note", "meeting at 3pm", importance=0.4)

        ctx = buf.get_context_string()
        assert isinstance(ctx, str)
        assert len(ctx) > 0
        assert "task" in ctx
        assert "note" in ctx

    def test_eviction_removes_lowest_priority(self):
        """When capacity is exceeded, the lowest-priority item is evicted."""
        buf = WorkingMemoryBuffer(capacity=2)
        buf.add("high", "very important", importance=1.0)
        buf.add("low", "not important", importance=0.1)
        # Buffer is full. Adding another should evict "low".
        buf.add("mid", "somewhat important", importance=0.5)

        assert len(buf) == 2
        assert "high" in buf
        assert "mid" in buf
        assert "low" not in buf

    def test_contains(self):
        """The 'in' operator should work for checking key existence."""
        buf = WorkingMemoryBuffer()
        buf.add("exists", "I am here")

        assert "exists" in buf
        assert "missing" not in buf


# ===========================================================================
# TestShortTermMemory
# ===========================================================================

class TestShortTermMemory:

    def test_add_to_working_memory(self):
        """Adding to working memory should make the item retrievable."""
        stm = ShortTermMemory()
        result = stm.add_to_working_memory("task1", "write tests")
        assert result is True

        item = stm.get_from_working_memory("task1")
        assert item is not None
        assert item.content == "write tests"

    def test_add_interaction(self):
        """Adding an interaction should appear in recent history."""
        stm = ShortTermMemory()
        stm.add_interaction("user", "Hello, how are you?")

        history = stm.get_recent_history()
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello, how are you?"

    def test_get_recent_history_limited(self):
        """get_recent_history(n) should return at most n entries."""
        stm = ShortTermMemory()
        for i in range(5):
            stm.add_interaction("user", f"message {i}")

        history = stm.get_recent_history(3)
        assert len(history) == 3
        # Should be the last 3 messages.
        assert history[0]["content"] == "message 2"
        assert history[1]["content"] == "message 3"
        assert history[2]["content"] == "message 4"

    def test_get_conversation_context(self):
        """get_conversation_context should return a formatted conversation string."""
        stm = ShortTermMemory()
        stm.add_interaction("user", "What is the weather?")
        stm.add_interaction("assistant", "It is sunny today.")

        ctx = stm.get_conversation_context()
        assert isinstance(ctx, str)
        assert "user: What is the weather?" in ctx
        assert "assistant: It is sunny today." in ctx

    def test_set_get_session_context(self):
        """Session context values should survive set/get round-trips."""
        stm = ShortTermMemory()
        stm.set_session_context("user_name", "Alice")
        stm.set_session_context("theme", "dark")

        assert stm.get_session_context("user_name") == "Alice"
        assert stm.get_session_context("theme") == "dark"
        assert stm.get_session_context("nonexistent") is None

    def test_clear_session(self):
        """clear_session should empty working memory, history, and session context."""
        stm = ShortTermMemory()
        stm.add_to_working_memory("k1", "data")
        stm.add_interaction("user", "hello")
        stm.set_session_context("key", "value")

        stm.clear_session()

        assert stm.get_from_working_memory("k1") is None
        assert stm.get_recent_history() == []
        assert stm.get_session_context("key") is None

    def test_get_full_context(self):
        """get_full_context should return a dict with all context information."""
        stm = ShortTermMemory()
        stm.add_to_working_memory("task", "do something", importance=0.7)
        stm.add_interaction("user", "hi")
        stm.set_session_context("mode", "debug")

        ctx = stm.get_full_context()
        assert isinstance(ctx, dict)
        assert "working_memory" in ctx
        assert "recent_history" in ctx
        assert "session_context" in ctx
        assert "current_focus" in ctx
        assert ctx["session_context"]["mode"] == "debug"
        assert len(ctx["recent_history"]) == 1

    def test_working_memory_default_capacity(self):
        """The default working memory capacity should be 7."""
        stm = ShortTermMemory()
        assert stm.working_memory.capacity == 7
