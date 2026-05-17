"""Unit tests for the async_api module."""
import pytest
import pytest_asyncio
import asyncio
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.core.async_memory_api_wrapper import AsyncAgentMemory
from memory_system.core.agent_memory_manager import AgentMemoryConfig
from memory_system.core.long_term_persistent_memory import LongTermMemoryConfig


@pytest.mark.asyncio
class TestAsyncAgentMemory:
    """Test AsyncAgentMemory async operations"""
    
    @pytest_asyncio.fixture
    async def async_memory(self):
        """Fixture to create and cleanup async memory"""
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "dimension": 64},
                vector_store={"backend": "memory"},
            ),
            knowledge_graph={"enabled": False},
            structured_store={"enabled": False},
        )
        memory = AsyncAgentMemory(config, max_workers=2)
        yield memory
        await memory.close()
    
    async def test_async_remember(self, async_memory):
        """Test async remember operation"""
        mid = await async_memory.remember("test content", importance=0.8)
        assert isinstance(mid, str)
        assert len(mid) > 0
    
    async def test_async_recall(self, async_memory):
        """Test async recall operation"""
        await async_memory.remember("Python programming", category="tech", importance=0.9)
        await async_memory.remember("JavaScript coding", category="tech", importance=0.8)
        
        results = await async_memory.recall("Python", top_k=3)
        assert isinstance(results, list)
        assert len(results) > 0
    
    async def test_async_add_to_working_memory(self, async_memory):
        """Test async add to working memory"""
        result = await async_memory.add_to_working_memory("key1", "value1", importance=0.9)
        assert result is True
    
    async def test_async_context_manager(self):
        """Test async context manager"""
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "dimension": 64},
                vector_store={"backend": "memory"},
            ),
            knowledge_graph={"enabled": False},
            structured_store={"enabled": False},
        )
        
        async with AsyncAgentMemory(config, max_workers=2) as memory:
            mid = await memory.remember("test", importance=0.8)
            assert isinstance(mid, str)
    
    async def test_async_get_stats(self, async_memory):
        """Test async get_stats"""
        await async_memory.remember("test", importance=0.8)
        stats = await async_memory.get_stats()
        assert isinstance(stats, dict)
        assert "long_term" in stats
    
    async def test_async_clear_session(self, async_memory):
        """Test async clear session"""
        await async_memory.add_to_working_memory("key", "value")
        await async_memory.remember("test", importance=0.8)
        
        await async_memory.clear_session()
        
        # After clear, working memory should be empty
        # (can't directly verify without exposing internals)
        stats = await async_memory.get_stats()
        assert stats["short_term"]["working_memory_size"] == 0
    
    async def test_concurrent_operations(self, async_memory):
        """Test concurrent async operations"""
        # Run multiple operations concurrently
        tasks = [
            async_memory.remember(f"content {i}", importance=0.8)
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        assert all(isinstance(r, str) for r in results)
