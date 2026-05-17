"""
健康检查模块

提供服务健康状态检测，支持 Kubernetes 探针和负载均衡器健康检查。
"""

import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    name: str
    status: HealthStatus
    response_time_ms: float
    message: str = ""
    details: Dict = field(default_factory=dict)


class HealthChecker:
    """
    健康检查器
    
    支持多种检查类型：
    - 嵌入模型可用性
    - 向量存储连接状态
    - 结构化存储状态
    - 知识图谱状态
    - 自定义检查
    """
    
    def __init__(self, timeout_seconds: float = 5.0):
        """
        Args:
            timeout_seconds: 单个检查的超时时间
        """
        self.timeout_seconds = timeout_seconds
        self._checks: Dict[str, Callable[[], HealthCheckResult]] = {}
        self._last_results: Dict[str, HealthCheckResult] = {}
        logger.info("HealthChecker initialized with timeout=%.1fs", timeout_seconds)
    
    def register_check(self, name: str, check_func: Callable[[], HealthCheckResult]):
        """
        注册健康检查
        
        Args:
            name: 检查名称
            check_func: 检查函数，返回 HealthCheckResult
        """
        self._checks[name] = check_func
        logger.debug("Registered health check: %s", name)
    
    def check(self, name: Optional[str] = None) -> Dict[str, HealthCheckResult]:
        """
        执行健康检查
        
        Args:
            name: 指定检查名称，None 表示检查所有
        
        Returns:
            检查结果字典
        """
        results = {}
        checks_to_run = {name: self._checks[name]} if name else self._checks
        
        for check_name, check_func in checks_to_run.items():
            start = time.time()
            try:
                result = check_func()
                result.response_time_ms = (time.time() - start) * 1000
                results[check_name] = result
                self._last_results[check_name] = result
            except (ValueError, TypeError, RuntimeError, ConnectionError, OSError) as e:
                logger.exception("Health check %s failed", check_name)
                results[check_name] = HealthCheckResult(
                    name=check_name,
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=(time.time() - start) * 1000,
                    message=f"Check failed: {str(e)}"
                )
        
        return results
    
    def is_healthy(self) -> bool:
        """检查整体健康状态"""
        results = self.check()
        return all(
            r.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
            for r in results.values()
        )
    
    def get_overall_status(self) -> HealthStatus:
        """获取整体健康状态"""
        results = self.check()
        statuses = [r.status for r in results.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        return HealthStatus.UNKNOWN
    
    def to_dict(self) -> Dict:
        """转换为字典格式（用于 HTTP API 响应）"""
        results = self.check()
        return {
            "status": self.get_overall_status().value,
            "timestamp": time.time(),
            "checks": {
                name: {
                    "status": r.status.value,
                    "response_time_ms": round(r.response_time_ms, 2),
                    "message": r.message,
                    "details": r.details,
                }
                for name, r in results.items()
            }
        }


def create_embedding_health_check(embedder) -> Callable[[], HealthCheckResult]:
    """创建嵌入模型健康检查"""
    def check() -> HealthCheckResult:
        start = time.time()
        try:
            # 尝试编码一个简单文本
            result = embedder.encode("health check")
            if result and len(result) > 0:
                return HealthCheckResult(
                    name="embedding",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=(time.time() - start) * 1000,
                    message="Embedding model is responsive",
                    details={"dimension": len(result)}
                )
            return HealthCheckResult(
                name="embedding",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start) * 1000,
                message="Embedding returned empty result"
            )
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            return HealthCheckResult(
                name="embedding",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start) * 1000,
                message=f"Embedding check failed: {str(e)}"
            )
    return check


def create_vector_store_health_check(store) -> Callable[[], HealthCheckResult]:
    """创建向量存储健康检查"""
    def check() -> HealthCheckResult:
        start = time.time()
        try:
            count = store.count()
            return HealthCheckResult(
                name="vector_store",
                status=HealthStatus.HEALTHY,
                response_time_ms=(time.time() - start) * 1000,
                message="Vector store is accessible",
                details={"memory_count": count}
            )
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            return HealthCheckResult(
                name="vector_store",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start) * 1000,
                message=f"Vector store check failed: {str(e)}"
            )
    return check


def create_structured_store_health_check(store) -> Callable[[], HealthCheckResult]:
    """创建结构化存储健康检查"""
    def check() -> HealthCheckResult:
        start = time.time()
        try:
            tables = store.list_tables()
            return HealthCheckResult(
                name="structured_store",
                status=HealthStatus.HEALTHY,
                response_time_ms=(time.time() - start) * 1000,
                message="Structured store is accessible",
                details={"table_count": len(tables)}
            )
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            return HealthCheckResult(
                name="structured_store",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start) * 1000,
                message=f"Structured store check failed: {str(e)}"
            )
    return check


def create_knowledge_graph_health_check(kg) -> Callable[[], HealthCheckResult]:
    """创建知识图谱健康检查"""
    def check() -> HealthCheckResult:
        start = time.time()
        try:
            entity_count = kg.entity_count()
            relation_count = kg.relation_count()
            return HealthCheckResult(
                name="knowledge_graph",
                status=HealthStatus.HEALTHY,
                response_time_ms=(time.time() - start) * 1000,
                message="Knowledge graph is accessible",
                details={
                    "entity_count": entity_count,
                    "relation_count": relation_count
                }
            )
        except (ValueError, TypeError, RuntimeError, AttributeError, OSError) as e:
            return HealthCheckResult(
                name="knowledge_graph",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start) * 1000,
                message=f"Knowledge graph check failed: {str(e)}"
            )
    return check


__all__ = [
    "HealthStatus",
    "HealthCheckResult",
    "HealthChecker",
    "create_embedding_health_check",
    "create_vector_store_health_check",
    "create_structured_store_health_check",
    "create_knowledge_graph_health_check",
]
