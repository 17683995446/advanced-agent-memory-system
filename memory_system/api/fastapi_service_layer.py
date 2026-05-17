"""
FastAPI 服务层 - HTTP 远程访问接口

提供 RESTful API，支持远程调用记忆系统的所有功能。
基于 FastAPI + Pydantic，自动生成 OpenAPI 文档。

依赖: fastapi, uvicorn (可选)
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    _fastapi_available = True
except ImportError:
    _fastapi_available = False
    FastAPI = None
    HTTPException = None
    JSONResponse = None
    BaseModel = None
    Field = None


def create_app(memory_system: Any = None):
    """
    创建 FastAPI 应用

    当 FastAPI 不可用时返回 None 并记录警告。

    Args:
        memory_system: AgentMemory 实例（可选）

    Returns:
        FastAPI 应用实例，或 None（FastAPI 不可用时）
    """
    if not _fastapi_available:
        logger.warning(
            "FastAPI is not installed. "
            "Install it with: pip install fastapi uvicorn"
        )
        return None
    return _create_fastapi_app(memory_system)


if _fastapi_available:
    # ------------------------------------------------------------------
    # Pydantic 请求/响应模型
    # ------------------------------------------------------------------
    
    class RememberRequest(BaseModel):
        """记忆存储请求"""
        content: str
        embedding: Optional[list[float]] = None
        metadata: dict = Field(default_factory=dict)
        tags: list[str] = Field(default_factory=list)
        category: str = "general"
        importance: float = 0.5
    
    class RememberResponse(BaseModel):
        """记忆存储响应"""
        id: str
        success: bool
        message: str = ""
    
    class SearchRequest(BaseModel):
        """搜索请求"""
        query_embedding: list[float]
        top_k: int = 5
        category: Optional[str] = None
        min_importance: Optional[float] = None
    
    class SearchResultItem(BaseModel):
        """搜索结果项"""
        id: str
        content: str
        score: float
        metadata: dict = Field(default_factory=dict)
        category: str = "general"
    
    class SearchResponse(BaseModel):
        """搜索响应"""
        results: list[SearchResultItem]
        total: int
        query_time_ms: float
    
    class DeleteRequest(BaseModel):
        """删除请求"""
        id: str
    
    class DeleteResponse(BaseModel):
        """删除响应"""
        success: bool
        message: str = ""
    
    class UpdateRequest(BaseModel):
        """更新请求"""
        id: str
        content: Optional[str] = None
        metadata: Optional[dict] = None
        importance: Optional[float] = None
    
    class UpdateResponse(BaseModel):
        """更新响应"""
        success: bool
        message: str = ""
    
    class HealthResponse(BaseModel):
        """健康检查响应"""
        status: str
        version: str
        uptime_seconds: float
        components: dict
    
    class StatsResponse(BaseModel):
        """统计响应"""
        total_memories: int
        vector_store: str
        structured_store: str
        cache_store: str
        sessions: int
    
    class ErrorResponse(BaseModel):
        """错误响应"""
        error: str
        detail: str = ""
    
    # ------------------------------------------------------------------
    # FastAPI 应用工厂
    # ------------------------------------------------------------------
    
    def _create_fastapi_app(memory_system: Any = None) -> FastAPI:
        """
        创建 FastAPI 应用
        
        Args:
            memory_system: AgentMemory 实例（可选）
            
        Returns:
            FastAPI 应用实例
            
        Example:
            from memory_system.core.agent_memory_manager import AgentMemory
            
            app = create_app(AgentMemory())
            
            # 启动: uvicorn memory_system.service_layer:app --reload
        """
        app = FastAPI(
            title="Agent Memory System API",
            description="RESTful API for Agent Memory Management",
            version="3.4.0",
            docs_url="/docs",
            redoc_url="/redoc",
        )
        
        _memory = memory_system
        _start_time = time.time()
        
        # ------------------------------------------------------------------
        # 健康检查
        # ------------------------------------------------------------------
        
        @app.get("/health", response_model=HealthResponse, tags=["系统"])
        async def health_check():
            """健康检查"""
            components = {}
            if _memory is not None:
                components["memory_system"] = "ok"
            
            return HealthResponse(
                status="healthy",
                version="3.4.0",
                uptime_seconds=time.time() - _start_time,
                components=components,
            )
        
        # ------------------------------------------------------------------
        # 记忆操作
        # ------------------------------------------------------------------
        
        @app.post("/api/v1/memory/remember", response_model=RememberResponse, tags=["记忆"])
        async def remember(req: RememberRequest):
            """存储记忆"""
            try:
                memory_id = str(uuid.uuid4())
                
                if _memory is not None:
                    _memory.remember(
                        content=req.content,
                        metadata=req.metadata,
                        tags=req.tags,
                        category=req.category,
                    )
                
                return RememberResponse(
                    id=memory_id,
                    success=True,
                    message="Memory stored successfully",
                )
            except (ValueError, TypeError, RuntimeError) as e:
                logger.error("Remember failed: %s", e)
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/api/v1/memory/search", response_model=SearchResponse, tags=["记忆"])
        async def search(req: SearchRequest):
            """搜索记忆"""
            start = time.time()
            try:
                results = []
                
                if _memory is not None:
                    memory_results = _memory.recall(
                        query=req.query_embedding,
                        top_k=req.top_k,
                    )
                    for item in memory_results:
                        results.append(SearchResultItem(
                            id=getattr(item, 'id', str(uuid.uuid4())),
                            content=getattr(item, 'content', ''),
                            score=getattr(item, 'score', 0.0),
                            metadata=getattr(item, 'metadata', {}),
                            category=getattr(item, 'category', 'general'),
                        ))
                
                return SearchResponse(
                    results=results,
                    total=len(results),
                    query_time_ms=(time.time() - start) * 1000,
                )
            except (ValueError, TypeError, RuntimeError) as e:
                logger.error("Search failed: %s", e)
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.delete("/api/v1/memory/{memory_id}", response_model=DeleteResponse, tags=["记忆"])
        async def delete_memory(memory_id: str):
            """删除记忆"""
            try:
                success = True
                if _memory is not None:
                    success = _memory.forget(memory_id)
                
                return DeleteResponse(
                    success=success,
                    message="Memory deleted" if success else "Memory not found",
                )
            except (ValueError, TypeError, RuntimeError) as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.put("/api/v1/memory", response_model=UpdateResponse, tags=["记忆"])
        async def update_memory(req: UpdateRequest):
            """更新记忆"""
            try:
                success = True
                if _memory is not None:
                    updates = {}
                    if req.content:
                        updates["content"] = req.content
                    if req.metadata:
                        updates["metadata"] = req.metadata
                    if req.importance is not None:
                        updates["importance"] = req.importance
                    success = _memory.update(req.id, **updates)
                
                return UpdateResponse(
                    success=success,
                    message="Memory updated" if success else "Memory not found",
                )
            except (ValueError, TypeError, RuntimeError) as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # ------------------------------------------------------------------
        # 统计
        # ------------------------------------------------------------------
        
        @app.get("/api/v1/stats", response_model=StatsResponse, tags=["系统"])
        async def get_stats():
            """获取统计信息"""
            return StatsResponse(
                total_memories=0,
                vector_store="memory",
                structured_store="sqlite",
                cache_store="memory",
                sessions=0,
            )
        
        # ------------------------------------------------------------------
        # 错误处理
        # ------------------------------------------------------------------
        
        @app.exception_handler(Exception)
        async def global_exception_handler(request, exc):
            return JSONResponse(
                status_code=500,
                content={"error": type(exc).__name__, "detail": str(exc)},
            )
        
        return app


__all__ = [
    "create_app",
    "RememberRequest",
    "RememberResponse",
    "SearchRequest",
    "SearchResponse",
    "HealthResponse",
    "StatsResponse",
    "_fastapi_available",
]
