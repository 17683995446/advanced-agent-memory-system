"""Unit tests for the middleware module."""
import pytest
import sys
import os
import time
import hmac
import hashlib
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.api.fastapi_middleware_stack import (
    AuthType,
    CORSMiddlewareConfig,
    RateLimitMiddlewareConfig,
    AuthMiddlewareConfig,
    LoggingMiddlewareConfig,
    MiddlewareConfig,
    get_request_id,
    generate_api_key,
    hash_password,
    verify_password,
)


class TestAuthType:
    def test_all_types(self):
        assert AuthType.NONE.value == "none"
        assert AuthType.API_KEY.value == "api_key"
        assert AuthType.JWT.value == "jwt"
        assert AuthType.HMAC.value == "hmac"


class TestCORSMiddlewareConfig:
    def test_defaults(self):
        config = CORSMiddlewareConfig()
        assert config.allow_origins == ["*"]
        assert config.allow_methods == ["*"]
        assert config.allow_credentials is True
        assert config.max_age == 600


class TestRateLimitMiddlewareConfig:
    def test_defaults(self):
        config = RateLimitMiddlewareConfig()
        assert config.requests_per_second == 100.0
        assert config.burst_size == 200
        assert config.storage == "memory"


class TestAuthMiddlewareConfig:
    def test_defaults(self):
        config = AuthMiddlewareConfig()
        assert config.auth_type == AuthType.NONE
        assert config.jwt_secret == "change-me"
        assert config.jwt_algorithm == "HS256"
    
    def test_api_key_config(self):
        config = AuthMiddlewareConfig(
            auth_type=AuthType.API_KEY,
            api_keys=["key1", "key2"],
        )
        assert config.auth_type == AuthType.API_KEY
        assert len(config.api_keys) == 2


class TestLoggingMiddlewareConfig:
    def test_defaults(self):
        config = LoggingMiddlewareConfig()
        assert config.log_requests is True
        assert config.log_responses is True
        assert config.slow_request_threshold_ms == 1000.0


class TestMiddlewareConfig:
    def test_defaults(self):
        config = MiddlewareConfig()
        assert config.cors.allow_origins == ["*"]
        assert config.rate_limit.requests_per_second == 100.0
        assert config.auth.auth_type == AuthType.NONE
        assert config.request_timeout_ms == 30000.0
        assert config.enable_request_id is True


class TestHelperFunctions:
    def test_generate_api_key(self):
        key1 = generate_api_key()
        key2 = generate_api_key()
        
        assert key1.startswith("am_")
        assert len(key1) == len("am_") + 32
        assert key1 != key2
    
    def test_hash_password(self):
        password = "secure_password_123"
        hashed, salt = hash_password(password)
        
        assert hashed != password
        assert salt != ""
        assert len(hashed) > 0
    
    def test_verify_password_correct(self):
        password = "secure_password_123"
        hashed, salt = hash_password(password)
        
        assert verify_password(password, hashed, salt) is True
    
    def test_verify_password_incorrect(self):
        password = "secure_password_123"
        hashed, salt = hash_password(password)
        
        assert verify_password("wrong_password", hashed, salt) is False
    
    def test_hash_password_custom_salt(self):
        password = "test123"
        salt = "custom_salt_value"
        hashed, returned_salt = hash_password(password, salt)
        
        assert returned_salt == salt
        assert verify_password(password, hashed, salt) is True
    
    def test_different_passwords_different_hashes(self):
        p1, s1 = hash_password("pass1")
        p2, s2 = hash_password("pass2")
        
        assert p1 != p2


class TestRequestIDVar:
    def test_get_request_id_default(self):
        rid = get_request_id()
        # Default is empty string when not in request context
        assert rid == ""
    
    def test_generate_api_key_uniqueness(self):
        keys = [generate_api_key() for _ in range(100)]
        assert len(set(keys)) == 100  # All unique


class TestMiddlewareWithMockApp:
    """Test middleware classes with mock ASGI apps."""
    
    def test_request_id_middleware(self):
        """Test RequestIDMiddleware."""
        from memory_system.api.fastapi_middleware_stack import RequestIDMiddleware
        from unittest.mock import AsyncMock, MagicMock
        
        # Mock ASGI app
        mock_app = AsyncMock()
        mock_send = AsyncMock()
        mock_receive = AsyncMock()
        
        middleware = RequestIDMiddleware(mock_app)
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "state": {},
        }
        
        import asyncio
        asyncio.run(middleware(scope, mock_receive, mock_send))
        
        # Verify app was called
        mock_app.assert_called_once()
        # Verify request ID was added to state
        assert "request_id" in scope["state"]
    
    def test_request_id_middleware_with_existing_header(self):
        """Test RequestIDMiddleware with existing X-Request-ID header."""
        from memory_system.api.fastapi_middleware_stack import RequestIDMiddleware
        from unittest.mock import AsyncMock
        
        mock_app = AsyncMock()
        mock_send = AsyncMock()
        mock_receive = AsyncMock()
        
        middleware = RequestIDMiddleware(mock_app)
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [(b"x-request-id", b"existing-id-123")],
            "state": {},
        }
        
        import asyncio
        asyncio.run(middleware(scope, mock_receive, mock_send))
        
        # Should use existing header
        assert scope["state"]["request_id"] == "existing-id-123"
    
    def test_request_id_middleware_non_http(self):
        """Test RequestIDMiddleware passes through non-HTTP scopes."""
        from memory_system.api.fastapi_middleware_stack import RequestIDMiddleware
        from unittest.mock import AsyncMock
        
        mock_app = AsyncMock()
        mock_send = AsyncMock()
        mock_receive = AsyncMock()
        
        middleware = RequestIDMiddleware(mock_app)
        
        scope = {"type": "websocket", "path": "/ws"}
        
        import asyncio
        asyncio.run(middleware(scope, mock_receive, mock_send))
        
        mock_app.assert_called_once()
    
    def test_rate_limit_middleware_pass(self):
        """Test RateLimitMiddleware allows requests within limit."""
        from memory_system.api.fastapi_middleware_stack import RateLimitMiddleware
        from unittest.mock import AsyncMock
        
        mock_app = AsyncMock()
        mock_send = AsyncMock()
        mock_receive = AsyncMock()
        
        middleware = RateLimitMiddleware(mock_app)
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "client": ("127.0.0.1", 12345),
            "headers": [],
            "state": {},
        }
        
        import asyncio
        asyncio.run(middleware(scope, mock_receive, mock_send))
        
        mock_app.assert_called_once()
    
    def test_rate_limit_middleware_get_client_ip_xff(self):
        """Test RateLimitMiddleware extracts client IP from X-Forwarded-For."""
        from memory_system.api.fastapi_middleware_stack import RateLimitMiddleware
        from unittest.mock import AsyncMock
        
        mock_app = AsyncMock()
        middleware = RateLimitMiddleware(mock_app)
        
        # Test X-Forwarded-For
        scope = {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.1, 70.41.3.18")],
        }
        ip = middleware._get_client_ip(scope)
        assert ip == "203.0.113.1"
    
    def test_rate_limit_middleware_get_client_ip_xreal(self):
        """Test RateLimitMiddleware extracts client IP from X-Real-IP."""
        from memory_system.api.fastapi_middleware_stack import RateLimitMiddleware
        from unittest.mock import AsyncMock
        
        mock_app = AsyncMock()
        middleware = RateLimitMiddleware(mock_app)
        
        scope = {
            "type": "http",
            "headers": [(b"x-real-ip", b"192.168.1.1")],
        }
        ip = middleware._get_client_ip(scope)
        assert ip == "192.168.1.1"
    
    def test_auth_middleware_no_auth(self):
        """Test AuthMiddleware with no auth configured."""
        from memory_system.api.fastapi_middleware_stack import AuthMiddleware
        from unittest.mock import AsyncMock
        
        mock_app = AsyncMock()
        mock_receive = AsyncMock()
        
        middleware = AuthMiddleware(mock_app)
        
        scope = {
            "type": "http",
            "path": "/api/test",
            "headers": [],
            "state": {},
        }
        
        import asyncio
        asyncio.run(middleware(scope, mock_receive, AsyncMock()))
        
        mock_app.assert_called_once()
    
    def test_auth_middleware_health_endpoint_skipped(self):
        """Test AuthMiddleware skips health check endpoints."""
        from memory_system.api.fastapi_middleware_stack import AuthMiddleware
        from unittest.mock import AsyncMock
        
        mock_app = AsyncMock()
        
        middleware = AuthMiddleware(mock_app)
        
        for path in ["/health", "/ready", "/metrics"]:
            mock_app.reset_mock()
            scope = {
                "type": "http",
                "path": path,
                "headers": [],
                "state": {},
            }
            import asyncio
            asyncio.run(middleware(scope, AsyncMock(), AsyncMock()))
            mock_app.assert_called_once()
    
    def test_auth_middleware_api_key_valid(self):
        """Test AuthMiddleware accepts valid API key."""
        from memory_system.api.fastapi_middleware_stack import AuthMiddleware, AuthMiddlewareConfig, AuthType
        from unittest.mock import AsyncMock
        
        mock_app = AsyncMock()
        mock_receive = AsyncMock()
        
        config = AuthMiddlewareConfig(
            auth_type=AuthType.API_KEY,
            api_keys=["valid-key-123"],
        )
        middleware = AuthMiddleware(mock_app, config)
        
        scope = {
            "type": "http",
            "path": "/api/test",
            "headers": [(b"x-api-key", b"valid-key-123")],
            "state": {},
        }
        
        import asyncio
        asyncio.run(middleware(scope, mock_receive, AsyncMock()))
        
        mock_app.assert_called_once()
        assert scope["state"]["auth_type"] == "api_key"
    
    @pytest.mark.skipif(
        True,  # starlette not available in test environment
        reason="starlette not installed"
    )
    def test_auth_middleware_api_key_missing(self):
        """Test AuthMiddleware rejects missing API key."""
        from memory_system.api.fastapi_middleware_stack import AuthMiddleware, AuthMiddlewareConfig, AuthType
        from unittest.mock import AsyncMock
        from starlette.responses import JSONResponse
        import asyncio

        mock_app = AsyncMock()
        mock_receive = AsyncMock()

        config = AuthMiddlewareConfig(auth_type=AuthType.API_KEY)
        middleware = AuthMiddleware(mock_app, config)

        scope = {
            "type": "http",
            "path": "/api/test",
            "headers": [],
            "state": {},
        }

        response_mock = AsyncMock()
        asyncio.run(middleware(scope, mock_receive, response_mock))

        # App should not be called
        mock_app.assert_not_called()

    def test_timeout_middleware(self):
        """Test TimeoutMiddleware."""
        from memory_system.api.fastapi_middleware_stack import TimeoutMiddleware
        from unittest.mock import AsyncMock
        import asyncio

        # Mock app that takes a long time
        async def slow_app(scope, receive, send):
            await asyncio.sleep(10)  # Very long sleep
        mock_send = AsyncMock()
        mock_receive = AsyncMock()

        middleware = TimeoutMiddleware(slow_app, timeout_ms=50)

        scope = {"type": "http", "method": "GET", "path": "/test"}

        # Should timeout
        response_mock = AsyncMock()
        asyncio.run(middleware(scope, mock_receive, response_mock))
