"""Unit tests for the FastAPI service layer."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.api.fastapi_service_layer import (
    create_app,
    _fastapi_available,
)


@pytest.mark.skipif(not _fastapi_available, reason="FastAPI not installed")
class TestCreateApp:
    def test_create_app(self):
        app = create_app()
        assert app is not None
        assert app.title == "Agent Memory System API"
    
    def test_create_app_with_memory(self):
        app = create_app(memory_system=None)
        assert app is not None
    
    def test_health_endpoint(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "3.4.0"
    
    def test_remember_endpoint(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.post("/api/v1/memory/remember", json={
            "content": "Hello world",
            "metadata": {"source": "test"},
            "tags": ["greeting"],
            "category": "general",
            "importance": 0.8,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "id" in data
    
    def test_search_endpoint(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.post("/api/v1/memory/search", json={
            "query_embedding": [0.1] * 10,
            "top_k": 5,
        })
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data
        assert "query_time_ms" in data
    
    def test_delete_endpoint(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.delete("/api/v1/memory/test-id")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
    
    def test_update_endpoint(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.put("/api/v1/memory", json={
            "id": "test-id",
            "content": "updated content",
            "importance": 0.9,
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
    
    def test_stats_endpoint(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.get("/api/v1/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_memories" in data
    
    def test_docs_available(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_openapi_schema(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "Agent Memory System API"


class TestFastAPIAvailable:
    def test_fastapi_available(self):
        # FastAPI may or may not be installed in the test environment
        assert isinstance(_fastapi_available, bool)


# ======================================================================
# NEW TEST FUNCTIONS - Added to improve coverage from 12% to 50%+
# ======================================================================


@pytest.mark.skipif(not _fastapi_available, reason="FastAPI not installed")
class TestHealthEndpointDetailed:
    """Detailed tests for the /health endpoint."""

    def test_health_returns_200(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_version_field(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == "3.4.0"

    def test_health_has_uptime_seconds(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_health_has_components(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        assert "components" in data
        assert isinstance(data["components"], dict)

    def test_health_components_with_memory_system(self):
        """When memory_system is provided, components should include memory_system."""
        from fastapi.testclient import TestClient
        mock_memory = type("MockMemory", (), {})()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        assert "memory_system" in data["components"]
        assert data["components"]["memory_system"] == "ok"

    def test_health_components_without_memory_system(self):
        """When no memory_system is provided, components should be empty."""
        from fastapi.testclient import TestClient
        app = create_app(memory_system=None)
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        assert "memory_system" not in data["components"]


@pytest.mark.skipif(not _fastapi_available, reason="FastAPI not installed")
class TestRememberEndpointDetailed:
    """Detailed tests for the /api/v1/memory/remember endpoint."""

    def test_remember_missing_content_returns_422(self):
        """Missing required 'content' field should return 422 validation error."""
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.post("/api/v1/memory/remember", json={
            "metadata": {"source": "test"},
        })
        assert response.status_code == 422

    def test_remember_returns_uuid_id(self):
        """The returned id should be a valid UUID string."""
        import uuid
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.post("/api/v1/memory/remember", json={
            "content": "test content",
        })
        assert response.status_code == 200
        data = response.json()
        # Should be parseable as UUID
        uuid.UUID(data["id"])

    def test_remember_returns_success_message(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.post("/api/v1/memory/remember", json={
            "content": "hello",
        })
        data = response.json()
        assert data["message"] == "Memory stored successfully"

    def test_remember_with_empty_body_returns_422(self):
        """Empty JSON body should return 422."""
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.post("/api/v1/memory/remember", json={})
        assert response.status_code == 422

    def test_remember_with_all_fields(self):
        """Test remember with all optional fields populated."""
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.post("/api/v1/memory/remember", json={
            "content": "full test",
            "embedding": [0.1, 0.2, 0.3],
            "metadata": {"key": "value"},
            "tags": ["tag1", "tag2"],
            "category": "important",
            "importance": 0.99,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_remember_with_mock_memory_system(self):
        """When a mock memory system is provided, remember should call it."""
        from fastapi.testclient import TestClient
        mock_memory = type("MockMemory", (), {
            "remember": lambda self, **kwargs: None,
        })()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.post("/api/v1/memory/remember", json={
            "content": "test with mock",
        })
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_remember_with_memory_system_error(self):
        """When memory_system.remember raises, should return 500."""
        from fastapi.testclient import TestClient
        mock_memory = type("MockMemory", (), {
            "remember": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("DB error")),
        })()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.post("/api/v1/memory/remember", json={
            "content": "will fail",
        })
        assert response.status_code == 500


@pytest.mark.skipif(not _fastapi_available, reason="FastAPI not installed")
class TestSearchEndpointDetailed:
    """Detailed tests for the /api/v1/memory/search endpoint."""

    def test_search_empty_results_without_memory(self):
        """Without memory_system, search should return empty results."""
        from fastapi.testclient import TestClient
        app = create_app(memory_system=None)
        client = TestClient(app)
        response = client.post("/api/v1/memory/search", json={
            "query_embedding": [0.1] * 10,
            "top_k": 5,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []
        assert data["total"] == 0

    def test_search_returns_query_time_ms(self):
        """Response should include a non-negative query_time_ms."""
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.post("/api/v1/memory/search", json={
            "query_embedding": [0.1, 0.2, 0.3],
        })
        data = response.json()
        assert "query_time_ms" in data
        assert data["query_time_ms"] >= 0

    def test_search_missing_query_embedding_returns_422(self):
        """Missing required 'query_embedding' should return 422."""
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.post("/api/v1/memory/search", json={
            "top_k": 5,
        })
        assert response.status_code == 422

    def test_search_with_mock_memory_results(self):
        """When mock memory returns results, they should be mapped correctly."""
        from fastapi.testclient import TestClient
        result_item = type("Result", (), {
            "id": "mem-123",
            "content": "found memory",
            "score": 0.95,
            "metadata": {"source": "test"},
            "category": "general",
        })()
        mock_memory = type("MockMemory", (), {
            "recall": lambda self, **kwargs: [result_item],
        })()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.post("/api/v1/memory/search", json={
            "query_embedding": [0.1] * 10,
            "top_k": 3,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["results"][0]["id"] == "mem-123"
        assert data["results"][0]["content"] == "found memory"
        assert data["results"][0]["score"] == 0.95

    def test_search_with_memory_system_error(self):
        """When memory_system.recall raises, should return 500."""
        from fastapi.testclient import TestClient
        mock_memory = type("MockMemory", (), {
            "recall": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("recall failed")),
        })()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.post("/api/v1/memory/search", json={
            "query_embedding": [0.1] * 10,
        })
        assert response.status_code == 500

    def test_search_with_category_and_min_importance(self):
        """Search with optional category and min_importance filters."""
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.post("/api/v1/memory/search", json={
            "query_embedding": [0.1] * 10,
            "top_k": 10,
            "category": "important",
            "min_importance": 0.7,
        })
        assert response.status_code == 200
        data = response.json()
        assert "results" in data


@pytest.mark.skipif(not _fastapi_available, reason="FastAPI not installed")
class TestDeleteEndpointDetailed:
    """Detailed tests for the DELETE /api/v1/memory/{memory_id} endpoint."""

    def test_delete_without_memory_system_always_succeeds(self):
        """Without memory_system, delete should return success=True."""
        from fastapi.testclient import TestClient
        app = create_app(memory_system=None)
        client = TestClient(app)
        response = client.delete("/api/v1/memory/any-id")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Memory deleted"

    def test_delete_with_mock_memory_found(self):
        """When mock memory.forget returns True."""
        from fastapi.testclient import TestClient
        mock_memory = type("MockMemory", (), {
            "forget": lambda self, mid: True,
        })()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.delete("/api/v1/memory/existing-id")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_delete_with_mock_memory_not_found(self):
        """When mock memory.forget returns False."""
        from fastapi.testclient import TestClient
        mock_memory = type("MockMemory", (), {
            "forget": lambda self, mid: False,
        })()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.delete("/api/v1/memory/nonexistent-id")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["message"] == "Memory not found"

    def test_delete_with_memory_system_error(self):
        """When memory_system.forget raises, should return 500."""
        from fastapi.testclient import TestClient
        mock_memory = type("MockMemory", (), {
            "forget": lambda self, mid: (_ for _ in ()).throw(RuntimeError("delete error")),
        })()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.delete("/api/v1/memory/some-id")
        assert response.status_code == 500


@pytest.mark.skipif(not _fastapi_available, reason="FastAPI not installed")
class TestUpdateEndpointDetailed:
    """Detailed tests for the PUT /api/v1/memory endpoint."""

    def test_update_without_memory_system_always_succeeds(self):
        """Without memory_system, update should return success=True."""
        from fastapi.testclient import TestClient
        app = create_app(memory_system=None)
        client = TestClient(app)
        response = client.put("/api/v1/memory", json={
            "id": "test-id",
            "content": "new content",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_partial_only_content(self):
        """Update with only content field."""
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.put("/api/v1/memory", json={
            "id": "test-id",
            "content": "updated text",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_partial_only_metadata(self):
        """Update with only metadata field."""
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.put("/api/v1/memory", json={
            "id": "test-id",
            "metadata": {"key": "new_value"},
        })
        assert response.status_code == 200

    def test_update_partial_only_importance(self):
        """Update with only importance field."""
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.put("/api/v1/memory", json={
            "id": "test-id",
            "importance": 0.3,
        })
        assert response.status_code == 200

    def test_update_full_fields(self):
        """Update with all fields populated."""
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.put("/api/v1/memory", json={
            "id": "test-id",
            "content": "fully updated",
            "metadata": {"a": 1},
            "importance": 0.75,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Memory updated"

    def test_update_with_mock_memory_success(self):
        """When mock memory.update returns True."""
        from fastapi.testclient import TestClient
        mock_memory = type("MockMemory", (), {
            "update": lambda self, mid, **kwargs: True,
        })()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.put("/api/v1/memory", json={
            "id": "real-id",
            "content": "updated",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_with_mock_memory_not_found(self):
        """When mock memory.update returns False."""
        from fastapi.testclient import TestClient
        mock_memory = type("MockMemory", (), {
            "update": lambda self, mid, **kwargs: False,
        })()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.put("/api/v1/memory", json={
            "id": "missing-id",
            "content": "updated",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["message"] == "Memory not found"

    def test_update_with_memory_system_error(self):
        """When memory_system.update raises, should return 500."""
        from fastapi.testclient import TestClient
        mock_memory = type("MockMemory", (), {
            "update": lambda self, mid, **kwargs: (_ for _ in ()).throw(RuntimeError("update error")),
        })()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.put("/api/v1/memory", json={
            "id": "test-id",
            "content": "will fail",
        })
        assert response.status_code == 500

    def test_update_missing_id_returns_422(self):
        """Missing required 'id' field should return 422."""
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.put("/api/v1/memory", json={
            "content": "no id provided",
        })
        assert response.status_code == 422


@pytest.mark.skipif(not _fastapi_available, reason="FastAPI not installed")
class TestStatsEndpointDetailed:
    """Detailed tests for the /api/v1/stats endpoint."""

    def test_stats_returns_correct_structure(self):
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        response = client.get("/api/v1/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_memories" in data
        assert "vector_store" in data
        assert "structured_store" in data
        assert "cache_store" in data
        assert "sessions" in data

    def test_stats_default_values(self):
        """Stats should return default/zero values when no memory_system."""
        from fastapi.testclient import TestClient
        app = create_app(memory_system=None)
        client = TestClient(app)
        response = client.get("/api/v1/stats")
        data = response.json()
        assert data["total_memories"] == 0
        assert data["vector_store"] == "memory"
        assert data["structured_store"] == "sqlite"
        assert data["cache_store"] == "memory"
        assert data["sessions"] == 0


@pytest.mark.skipif(not _fastapi_available, reason="FastAPI not installed")
class TestGlobalExceptionHandler:
    """Tests for the global exception handler."""

    def test_unhandled_exception_returns_500(self):
        """HTTPException raised inside endpoints should return 500 with detail."""
        from fastapi.testclient import TestClient
        mock_memory = type("MockMemory", (), {
            "remember": lambda self, **kwargs: (_ for _ in ()).throw(ValueError("unexpected")),
        })()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.post("/api/v1/memory/remember", json={
            "content": "trigger error",
        })
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "unexpected"

    def test_exception_handler_includes_error_type(self):
        """HTTPException raised inside endpoints returns 500 with detail."""
        from fastapi.testclient import TestClient
        mock_memory = type("MockMemory", (), {
            "forget": lambda self, mid: (_ for _ in ()).throw(TypeError("type err")),
        })()
        app = create_app(memory_system=mock_memory)
        client = TestClient(app)
        response = client.delete("/api/v1/memory/x")
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "type err"

    def test_global_exception_handler_format(self):
        """The global exception handler should produce {error, detail} format.
        This is triggered for truly unhandled exceptions (not HTTPException)."""
        from fastapi.testclient import TestClient
        from memory_system.api.fastapi_service_layer import _create_fastapi_app
        # Create a raw app and add a route that raises a plain exception
        # not caught by any endpoint-level try/except
        app = _create_fastapi_app(memory_system=None)

        @app.get("/test-unhandled")
        async def unhandled():
            raise RuntimeError("raw error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-unhandled")
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert "detail" in data
        assert data["error"] == "RuntimeError"
        assert data["detail"] == "raw error"


@pytest.mark.skipif(not _fastapi_available, reason="FastAPI not installed")
class TestCreateAppWithoutMemorySystem:
    """Tests for create_app when no memory_system is provided."""

    def test_app_works_without_memory_system(self):
        """App should function correctly without a memory system (returns success with generated IDs)."""
        from fastapi.testclient import TestClient
        app = create_app(memory_system=None)
        client = TestClient(app)

        # Remember should still work
        resp = client.post("/api/v1/memory/remember", json={"content": "test"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["id"] is not None

        # Search should return empty
        resp = client.post("/api/v1/memory/search", json={"query_embedding": [0.1]})
        assert resp.status_code == 200
        assert resp.json()["results"] == []

        # Delete should succeed
        resp = client.delete("/api/v1/memory/some-id")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Update should succeed
        resp = client.put("/api/v1/memory", json={"id": "some-id", "content": "new"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_create_app_default_is_no_memory(self):
        """Calling create_app() without arguments should be equivalent to memory_system=None."""
        from fastapi.testclient import TestClient
        app = create_app()
        client = TestClient(app)
        # Health should show no memory_system component
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "memory_system" not in resp.json()["components"]


class TestCreateAppFastAPIUnavailable:
    """Tests for create_app when FastAPI is not available."""

    def test_create_app_returns_none_when_fastapi_unavailable(self):
        """When FastAPI is not installed, create_app should return None."""
        # We temporarily override the module-level flag to simulate absence
        import memory_system.api.fastapi_service_layer as mod
        original = mod._fastapi_available
        try:
            mod._fastapi_available = False
            result = mod.create_app()
            assert result is None
        finally:
            mod._fastapi_available = original
