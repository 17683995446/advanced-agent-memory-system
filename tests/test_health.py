"""Unit tests for the health module."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.observability.service_health_checker import (
    HealthStatus,
    HealthCheckResult,
    HealthChecker,
    create_embedding_health_check,
    create_vector_store_health_check,
    create_structured_store_health_check,
    create_knowledge_graph_health_check,
)
from memory_system.processing.text_embedding_provider import FakeEmbeddingProvider
from memory_system.storage.vector_store import MemoryVectorStore, MemoryRecord
from memory_system.storage.structured_sqlite_store import StructuredStore
from memory_system.processing.knowledge_graph_engine import KnowledgeGraph
import time


class TestHealthStatus:
    """Test HealthStatus enum"""
    
    def test_health_status_values(self):
        """Test health status enum values"""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestHealthCheckResult:
    """Test HealthCheckResult dataclass"""
    
    def test_result_creation(self):
        """Test creating health check result"""
        result = HealthCheckResult(
            name="test_check",
            status=HealthStatus.HEALTHY,
            response_time_ms=10.5,
            message="All good",
            details={"count": 100}
        )
        assert result.name == "test_check"
        assert result.status == HealthStatus.HEALTHY
        assert result.response_time_ms == 10.5
        assert result.message == "All good"
        assert result.details == {"count": 100}


class TestHealthChecker:
    """Test HealthChecker class"""
    
    def test_register_check(self):
        """Test registering health check"""
        checker = HealthChecker()
        
        def dummy_check():
            return HealthCheckResult("dummy", HealthStatus.HEALTHY, 0)
        
        checker.register_check("dummy", dummy_check)
        assert "dummy" in checker._checks
    
    def test_check_single(self):
        """Test running single check"""
        checker = HealthChecker()
        
        def dummy_check():
            return HealthCheckResult("dummy", HealthStatus.HEALTHY, 5.0)
        
        checker.register_check("dummy", dummy_check)
        results = checker.check("dummy")
        
        assert "dummy" in results
        assert results["dummy"].status == HealthStatus.HEALTHY
    
    def test_check_all(self):
        """Test running all checks"""
        checker = HealthChecker()
        
        checker.register_check("check1", lambda: HealthCheckResult("c1", HealthStatus.HEALTHY, 1.0))
        checker.register_check("check2", lambda: HealthCheckResult("c2", HealthStatus.HEALTHY, 2.0))
        
        results = checker.check()
        
        assert len(results) == 2
        assert "check1" in results
        assert "check2" in results
    
    def test_is_healthy_all_healthy(self):
        """Test is_healthy when all checks pass"""
        checker = HealthChecker()
        checker.register_check("c1", lambda: HealthCheckResult("c1", HealthStatus.HEALTHY, 1.0))
        
        assert checker.is_healthy() is True
    
    def test_is_healthy_with_unhealthy(self):
        """Test is_healthy when one check fails"""
        checker = HealthChecker()
        checker.register_check("c1", lambda: HealthCheckResult("c1", HealthStatus.HEALTHY, 1.0))
        checker.register_check("c2", lambda: HealthCheckResult("c2", HealthStatus.UNHEALTHY, 1.0))
        
        assert checker.is_healthy() is False
    
    def test_is_healthy_with_degraded(self):
        """Test is_healthy with degraded status"""
        checker = HealthChecker()
        checker.register_check("c1", lambda: HealthCheckResult("c1", HealthStatus.DEGRADED, 1.0))
        
        assert checker.is_healthy() is True  # Degraded is still considered healthy
    
    def test_get_overall_status_healthy(self):
        """Test overall status when healthy"""
        checker = HealthChecker()
        checker.register_check("c1", lambda: HealthCheckResult("c1", HealthStatus.HEALTHY, 1.0))
        
        assert checker.get_overall_status() == HealthStatus.HEALTHY
    
    def test_get_overall_status_unhealthy(self):
        """Test overall status when unhealthy"""
        checker = HealthChecker()
        checker.register_check("c1", lambda: HealthCheckResult("c1", HealthStatus.UNHEALTHY, 1.0))
        
        assert checker.get_overall_status() == HealthStatus.UNHEALTHY
    
    def test_get_overall_status_degraded(self):
        """Test overall status when degraded"""
        checker = HealthChecker()
        checker.register_check("c1", lambda: HealthCheckResult("c1", HealthStatus.DEGRADED, 1.0))
        
        assert checker.get_overall_status() == HealthStatus.DEGRADED
    
    def test_to_dict(self):
        """Test converting to dict"""
        checker = HealthChecker()
        checker.register_check("c1", lambda: HealthCheckResult("c1", HealthStatus.HEALTHY, 5.0, "OK"))
        
        data = checker.to_dict()
        
        assert "status" in data
        assert "timestamp" in data
        assert "checks" in data
        assert "c1" in data["checks"]
    
    def test_check_exception_handling(self):
        """Test that exceptions in checks are handled gracefully"""
        checker = HealthChecker()
        
        def failing_check():
            raise ValueError("Something went wrong")
        
        checker.register_check("failing", failing_check)
        results = checker.check()
        
        assert results["failing"].status == HealthStatus.UNHEALTHY
        assert "Something went wrong" in results["failing"].message


class TestHealthCheckFactories:
    """Test health check factory functions"""
    
    def test_create_embedding_health_check_healthy(self):
        """Test embedding health check with working embedder"""
        embedder = FakeEmbeddingProvider(dimension=64)
        check = create_embedding_health_check(embedder)
        
        result = check()
        
        assert result.status == HealthStatus.HEALTHY
        assert "responsive" in result.message
        assert result.details["dimension"] == 64
    
    def test_create_vector_store_health_check(self):
        """Test vector store health check"""
        store = MemoryVectorStore()
        store.add(MemoryRecord(id="1", content="test", embedding=[0.1]*64, timestamp=time.time()))
        
        check = create_vector_store_health_check(store)
        result = check()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.details["memory_count"] == 1
    
    def test_create_structured_store_health_check(self):
        """Test structured store health check"""
        store = StructuredStore(":memory:")
        store.create_table("test", {"name": "TEXT"})
        
        check = create_structured_store_health_check(store)
        result = check()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.details["table_count"] == 1
    
    def test_create_knowledge_graph_health_check(self):
        """Test knowledge graph health check"""
        from memory_system.processing.knowledge_graph_engine import Entity, Relation
        kg = KnowledgeGraph()
        kg.add_entity(Entity(name="Python", entity_type="language"))
        kg.add_relation(Relation(source="Python", target="programming_language", relation_type="is_a"))
        
        check = create_knowledge_graph_health_check(kg)
        result = check()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.details["entity_count"] == 2
        assert result.details["relation_count"] == 1
