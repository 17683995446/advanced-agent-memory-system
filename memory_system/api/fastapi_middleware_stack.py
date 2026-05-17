"""
中间件模块 - FastAPI 服务中间件

为服务层提供中间件支持：
- CORS 跨域请求处理
- 请求限流（基于内存或 Redis）
- 请求日志和追踪
- 身份验证（API Key / JWT）
- 请求超时控制
- 响应压缩

依赖: Python 标准库 + fastapi (可选)
"""

from __future__ import annotations

import asyncio
import binascii
import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional
from contextvars import ContextVar

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response, JSONResponse
    from starlette.types import ASGIApp
    _starlette_available = True
except ImportError:
    _starlette_available = False
    BaseHTTPMiddleware = object
    Request = Any
    Response = Any
    JSONResponse = None
    ASGIApp = Any

logger = logging.getLogger(__name__)

# Request ID context variable
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class AuthType(Enum):
    """认证类型"""
    NONE = "none"
    API_KEY = "api_key"
    JWT = "jwt"
    HMAC = "hmac"


@dataclass
class CORSMiddlewareConfig:
    """CORS 配置"""
    allow_origins: list[str] = field(default_factory=lambda: ["*"])
    allow_methods: list[str] = field(default_factory=lambda: ["*"])
    allow_headers: list[str] = field(default_factory=lambda: ["*"])
    allow_credentials: bool = True
    max_age: int = 600


@dataclass
class RateLimitMiddlewareConfig:
    """限流中间件配置"""
    requests_per_second: float = 100.0
    burst_size: int = 200
    key_prefix: str = "ratelimit:"
    storage: str = "memory"  # memory or redis
    redis_url: Optional[str] = None


@dataclass
class AuthMiddlewareConfig:
    """认证中间件配置"""
    auth_type: AuthType = AuthType.NONE
    api_keys: list[str] = field(default_factory=list)
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: Optional[str] = None
    hmac_secrets: dict[str, str] = field(default_factory=dict)


@dataclass
class LoggingMiddlewareConfig:
    """日志中间件配置"""
    log_requests: bool = True
    log_responses: bool = True
    log_headers: bool = False
    log_body: bool = False
    slow_request_threshold_ms: float = 1000.0


@dataclass
class MiddlewareConfig:
    """中间件总配置"""
    cors: CORSMiddlewareConfig = field(default_factory=CORSMiddlewareConfig)
    rate_limit: RateLimitMiddlewareConfig = field(default_factory=RateLimitMiddlewareConfig)
    auth: AuthMiddlewareConfig = field(default_factory=AuthMiddlewareConfig)
    logging: LoggingMiddlewareConfig = field(default_factory=LoggingMiddlewareConfig)
    request_timeout_ms: float = 30000.0
    enable_request_id: bool = True


# ---------------------------------------------------------------------------
# Request ID Middleware
# ---------------------------------------------------------------------------

class RequestIDMiddleware:
    """请求 ID 中间件
    
    为每个请求分配唯一 ID，便于追踪和日志关联。
    """
    
    def __init__(self, app: ASGIApp):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request_id = None
        headers = dict(scope.get("headers", []))
        
        # Check for existing X-Request-ID header
        if b"x-request-id" in headers:
            request_id = headers[b"x-request-id"].decode("utf-8")
        else:
            request_id = str(uuid.uuid4())
        
        request_id_var.set(request_id)
        
        # Add to response headers
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append(
                    (b"x-request-id", request_id.encode("utf-8"))
                )
            await send(message)
        
        scope["state"]["request_id"] = request_id
        await self.app(scope, receive, send_wrapper)


# ---------------------------------------------------------------------------
# Logging Middleware
# ---------------------------------------------------------------------------

class LoggingMiddleware:
    """请求日志中间件
    
    记录所有 HTTP 请求和响应的详细信息。
    """
    
    def __init__(self, app: ASGIApp, config: Optional[LoggingMiddlewareConfig] = None):
        self.app = app
        self.config = config or LoggingMiddlewareConfig()
        self._logger = logging.getLogger("middleware.access")
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start_time = time.perf_counter()
        method = scope["method"]
        path = scope["path"]
        client = scope.get("client")
        request_id = scope.get("state", {}).get("request_id", "-")
        
        # Log incoming request
        if self.config.log_requests:
            self._logger.info(
                "→ %s %s [%s] %s",
                method, path, request_id,
                f"from {client[0]}" if client else "",
            )
        
        # Collect request body if needed
        body = b""
        if self.config.log_body or self.config.log_headers:
            body = await self._receive_body(receive)
        
        # Process request
        async def send_wrapper(message):
            nonlocal body
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            if message["type"] == "http.response.start":
                status_code = message["status"]
                
                # Log slow requests
                if duration_ms > self.config.slow_request_threshold_ms:
                    self._logger.warning(
                        "⚠ SLOW %s %s [%s] %dms - %s",
                        method, path, request_id, duration_ms,
                        f"from {client[0]}" if client else "",
                    )
                elif self.config.log_responses:
                    self._logger.info(
                        "← %s %s [%s] %d %dms",
                        method, path, request_id, status_code, duration_ms,
                    )
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)
    
    async def _receive_body(self, receive) -> bytes:
        """接收请求体"""
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body"):
                    break
            elif message["type"] == "http.disconnect":
                break
        return body


# ---------------------------------------------------------------------------
# Rate Limit Middleware
# ---------------------------------------------------------------------------

class RateLimitMiddleware:
    """请求限流中间件
    
    基于令牌桶算法的请求限流。
    """
    
    def __init__(
        self,
        app: ASGIApp,
        config: Optional[RateLimitMiddlewareConfig] = None,
    ):
        self.app = app
        self.config = config or RateLimitMiddlewareConfig()
        self._tokens: dict[str, float] = {}
        self._last_update: dict[str, float] = {}
        self._lock: Optional[asyncio.Lock] = None
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Get client identifier
        client_ip = self._get_client_ip(scope)
        key = f"{self.config.key_prefix}{client_ip}"
        
        # Check rate limit
        allowed, remaining, retry_after = await self._check_rate_limit(key)
        
        if not allowed:
            response = JSONResponse(
                {
                    "error": "Rate limit exceeded",
                    "retry_after": retry_after,
                },
                status_code=429,
            )
            await response(scope, receive, send)
            return
        
        # Add rate limit headers
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-ratelimit-remaining", str(remaining).encode()))
                headers.append((b"x-ratelimit-limit", str(self.config.requests_per_second).encode()))
                if retry_after:
                    headers.append((b"retry-after", str(int(retry_after)).encode()))
                message["headers"] = headers
            await send(message)
        
        await self.app(scope, receive, send_wrapper)
    
    def _get_client_ip(self, scope) -> str:
        """获取客户端 IP"""
        headers = dict(scope.get("headers", []))
        
        # Check X-Forwarded-For first
        if b"x-forwarded-for" in headers:
            return headers[b"x-forwarded-for"].decode().split(",")[0].strip()
        
        if b"x-real-ip" in headers:
            return headers[b"x-real-ip"].decode()
        
        client = scope.get("client")
        return client[0] if client else "unknown"
    
    async def _check_rate_limit(self, key: str) -> tuple[bool, int, Optional[float]]:
        """检查限流"""
        now = time.time()
        current_time = now
        
        # Token bucket algorithm
        rate = self.config.requests_per_second
        capacity = self.config.burst_size
        
        last = self._last_update.get(key, current_time)
        tokens = self._tokens.get(key, float(capacity))
        
        # Add tokens based on elapsed time
        elapsed = current_time - last
        tokens = min(capacity, tokens + elapsed * rate)
        
        if tokens >= 1.0:
            tokens -= 1.0
            self._tokens[key] = tokens
            self._last_update[key] = current_time
            remaining = int(tokens)
            return True, remaining, None
        else:
            retry_after = (1.0 - tokens) / rate
            return False, 0, retry_after


# ---------------------------------------------------------------------------
# Auth Middleware
# ---------------------------------------------------------------------------

class AuthMiddleware:
    """身份验证中间件
    
    支持 API Key、JWT 和 HMAC 认证。
    """
    
    def __init__(
        self,
        app: ASGIApp,
        config: Optional[AuthMiddlewareConfig] = None,
    ):
        self.app = app
        self.config = config or AuthMiddlewareConfig()
        self._logger = logging.getLogger("middleware.auth")
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Skip auth for health check
        if scope["path"] in ("/health", "/ready", "/metrics"):
            await self.app(scope, receive, send)
            return
        
        auth_result = await self._authenticate(scope, receive)
        
        if not auth_result["valid"]:
            response = JSONResponse(
                {"error": "Unauthorized", "message": auth_result["message"]},
                status_code=401,
            )
            await response(scope, receive, send)
            return
        
        # Add user info to scope
        scope["state"]["user"] = auth_result.get("user")
        scope["state"]["auth_type"] = self.config.auth_type.value
        
        await self.app(scope, receive, send)
    
    async def _authenticate(self, scope, receive) -> dict:
        """执行认证"""
        headers = dict(scope.get("headers", []))
        
        if self.config.auth_type == AuthType.NONE:
            return {"valid": True, "user": None}
        
        if self.config.auth_type == AuthType.API_KEY:
            api_key = headers.get(b"x-api-key", b"").decode()
            if not api_key:
                return {"valid": False, "message": "Missing API key"}
            if api_key in self.config.api_keys:
                return {"valid": True, "user": {"api_key": api_key[:8] + "..."}}
            return {"valid": False, "message": "Invalid API key"}
        
        if self.config.auth_type == AuthType.JWT:
            auth_header = headers.get(b"authorization", b"").decode()
            if not auth_header.startswith("Bearer "):
                return {"valid": False, "message": "Missing Bearer token"}
            
            token = auth_header[7:]
            try:
                user = self._decode_jwt(token)
                return {"valid": True, "user": user}
            except (ValueError, TypeError, binascii.Error) as e:
                return {"valid": False, "message": f"Invalid token: {e}"}
        
        if self.config.auth_type == AuthType.HMAC:
            signature = headers.get(b"x-signature", b"").decode()
            body = await self._receive_body(receive)
            scope["_body"] = body  # Store for later use
            
            for key, secret in self.config.hmac_secrets.items():
                expected = hmac.new(
                    secret.encode(),
                    body,
                    hashlib.sha256,
                ).hexdigest()
                if hmac.compare_digest(signature, expected):
                    return {"valid": True, "user": {"key": key}}
            
            return {"valid": False, "message": "Invalid HMAC signature"}
        
        return {"valid": False, "message": "Unknown auth type"}
    
    def _decode_jwt(self, token: str) -> dict:
        """解码 JWT"""
        import base64
        import json
        
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        
        # Decode payload
        payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        data = json.loads(decoded)
        
        # Verify
        if self.config.jwt_issuer and data.get("iss") != self.config.jwt_issuer:
            raise ValueError("Invalid issuer")
        
        if data.get("exp", float("inf")) < time.time():
            raise ValueError("Token expired")
        
        return data
    
    async def _receive_body(self, receive) -> bytes:
        """接收请求体"""
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body"):
                    break
            elif message["type"] == "http.disconnect":
                break
        return body


# ---------------------------------------------------------------------------
# Timeout Middleware
# ---------------------------------------------------------------------------

class TimeoutMiddleware:
    """请求超时中间件"""
    
    def __init__(self, app: ASGIApp, timeout_ms: float = 30000.0):
        self.app = app
        self.timeout = timeout_ms / 1000.0
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        try:
            await asyncio.wait_for(
                self.app(scope, receive, send),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            if JSONResponse is not None:
                response = JSONResponse(
                    {"error": "Request timeout"},
                    status_code=504,
                )
                await response(scope, receive, send)
            else:
                # Fallback: send raw JSON response when starlette is unavailable
                body = json.dumps({"error": "Request timeout"}).encode()
                await send({
                    "type": "http.response.start",
                    "status": 504,
                    "headers": [[b"content-type", b"application/json"]],
                })
                await send({
                    "type": "http.response.body",
                    "body": body,
                })


# ---------------------------------------------------------------------------
# Middleware Stack Builder
# ---------------------------------------------------------------------------

def build_middleware_stack(
    app: ASGIApp,
    config: Optional[MiddlewareConfig] = None,
) -> ASGIApp:
    """
    构建中间件栈
    
    按照推荐的顺序应用中间件：
    1. Request ID
    2. Timeout
    3. Logging
    4. Rate Limit
    5. Auth
    6. CORS
    """
    config = config or MiddlewareConfig()
    
    # Apply in reverse order (outermost first)
    if config.cors.allow_origins != ["*"]:
        from starlette.middleware.cors import CORSMiddleware
        app = CORSMiddleware(
            app,
            allow_origins=config.cors.allow_origins,
            allow_methods=config.cors.allow_methods,
            allow_headers=config.cors.allow_headers,
            allow_credentials=config.cors.allow_credentials,
            max_age=config.cors.max_age,
        )
    
    app = AuthMiddleware(app, config.auth)
    app = RateLimitMiddleware(app, config.rate_limit)
    app = LoggingMiddleware(app, config.logging)
    app = TimeoutMiddleware(app, config.request_timeout_ms)
    app = RequestIDMiddleware(app)
    
    return app


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def get_request_id() -> str:
    """获取当前请求 ID"""
    return request_id_var.get()


def generate_api_key() -> str:
    """生成 API Key"""
    return f"am_{uuid.uuid4().hex}"


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """密码哈希"""
    import hashlib
    import base64
    
    if salt is None:
        salt_bytes = uuid.uuid4().bytes
        salt = base64.b64encode(salt_bytes).decode()
    
    hash_obj = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        100000,
    )
    return base64.b64encode(hash_obj).decode(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """验证密码"""
    expected, _ = hash_password(password, salt)
    return hmac.compare_digest(hashed, expected)


__all__ = [
    "AuthType",
    "CORSMiddlewareConfig",
    "RateLimitMiddlewareConfig",
    "AuthMiddlewareConfig",
    "LoggingMiddlewareConfig",
    "MiddlewareConfig",
    "RequestIDMiddleware",
    "LoggingMiddleware",
    "RateLimitMiddleware",
    "AuthMiddleware",
    "TimeoutMiddleware",
    "build_middleware_stack",
    "get_request_id",
    "generate_api_key",
    "hash_password",
    "verify_password",
]
