"""
Agent 长短期记忆系统 v3.0

高度模块化的 Agent 记忆管理框架，基于开源生态构建：
- 短期记忆（工作记忆）：临时上下文缓存，快速访问
- 长期记忆（向量存储）：可插拔后端（ChromaDB / FAISS / Redis / 内存）
- 嵌入模型：sentence-transformers / OpenAI / Fake（可插拔）
- 知识图谱：NetworkX 实体关系图谱
- 结构化存储：SQLite / SQLModel ORM 持久化
- Redis 后端：分布式缓存与向量存储
- 事件总线：Blinker 发布-订阅模式
- 统一存储接口：多后端抽象层
- 异步 API：async/await 支持
- 可观测性：Prometheus 指标 + 健康检查
- 中文分词：jieba 支持

每个模块均可独立使用、独立产品化。
"""

# Core orchestrator
from .core.agent_memory_manager import (
    AgentMemory,
    AgentMemoryConfig,
    MemoryManager,
)

# Short-term memory
from .core.short_term_working_memory import ShortTermMemory, WorkingMemoryBuffer, MemoryItem

# Long-term memory (orchestration layer)
from .core.long_term_persistent_memory import LongTermMemory, LongTermMemoryConfig

# Embedding providers (pluggable)
from .processing.text_embedding_provider import (
    EmbeddingProvider,
    EmbeddingConfig,
    EmbeddingFactory,
    SentenceTransformerProvider,
    OpenAIProvider,
    FakeEmbeddingProvider,
)

# Vector store backends (pluggable)
from .storage.vector_store import (
    VectorStoreBackend,
    VectorStoreFactory,
    MemoryRecord,
    SearchResult,
    MemoryVectorStore,
    ChromaDBBackend,
    FAISSBackend,
)

# Knowledge graph
from .processing.knowledge_graph_engine import (
    KnowledgeGraph,
    KnowledgeGraphBuilder,
    Entity,
    Relation,
    GraphSearchResult,
)

# Structured storage
from .storage.structured_sqlite_store import (
    StructuredStore,
    MemoryTable,
    StructuredRecord,
    QueryResult,
)

# Exceptions
from .exceptions import (
    MemoryError,
    EmbeddingError,
    EmbeddingModelNotFoundError,
    EmbeddingDimensionError,
    VectorStoreError,
    MemoryNotFoundError,
    KnowledgeGraphError,
    EntityNotFoundError,
    StructuredStoreError,
    TableNotFoundError,
    ConfigurationError,
    ConsolidationError,
)

# Tokenizer
from .processing.chinese_english_tokenizer import tokenize, tokenize_for_search

# Async API
from .core.async_memory_api_wrapper import AsyncAgentMemory

# Metrics & Observability
try:
    from .observability.prometheus_metrics_collector import MemoryMetrics, timed, get_metrics, reset_metrics
    _metrics_available = True
except ImportError:
    _metrics_available = False

# Health Check
try:
    from .observability.service_health_checker import (
        HealthStatus,
        HealthCheckResult,
        HealthChecker,
        create_embedding_health_check,
        create_vector_store_health_check,
        create_structured_store_health_check,
        create_knowledge_graph_health_check,
    )
    _health_available = True
except ImportError:
    _health_available = False

# SQLModel ORM Store (v3.0)
try:
    from .storage.sqlmodel_orm_store import (
        ORMStore,
        ORMQuery,
        MemoryRecordORM,
        InteractionORM,
        PreferenceORM,
        FactORM,
        create_orm_store,
        _sqlmodel_available,
    )
    _orm_available = _sqlmodel_available
except ImportError:
    _orm_available = False
    ORMStore = None
    ORMQuery = None
    MemoryRecordORM = None
    InteractionORM = None
    PreferenceORM = None
    FactORM = None
    create_orm_store = None

# Redis Store (v3.0)
try:
    from .storage.redis_distributed_store import (
        RedisVectorStore,
        RedisCache,
        create_redis_store,
        create_redis_cache,
    )
    _redis_available = True
except ImportError:
    _redis_available = False

# Event Bus (v3.0)
try:
    from .infra.blinker_event_bus import (
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
    _event_bus_available = True
except ImportError:
    _event_bus_available = False
    EventBus = None
    StorageEvent = None
    StorageEventType = None
    StorageSource = None
    get_event_bus = None
    reset_event_bus = None
    on_memory_add = None
    on_memory_update = None
    on_memory_delete = None

# Unified Storage (v3.0)
from .storage.unified_storage_backend import (
    UnifiedStorage,
    UnifiedRecord,
    VectorBackendType,
    StructuredBackendType,
    CacheBackendType,
)

# Plugin System (v3.1)
try:
    from .infra.plugin_extension_system import (
        PluginManager,
        PluginInfo,
        MemoryPluginSpec,
        get_plugin_manager,
        reset_plugin_manager,
    )
except ImportError:
    PluginManager = None
    PluginInfo = None
    MemoryPluginSpec = None
    get_plugin_manager = None
    reset_plugin_manager = None

# Importance Scoring (v3.1)
from .core.memory_importance_scorer import (
    ImportanceScorer,
    ImportanceScore,
    ScoringStrategy,
)

# Session Manager (v3.1)
from .core.session_context_manager import (
    SessionManager,
    SessionContext,
)

# Serializer (v3.1)
from .processing.memory_data_serializer import (
    MemorySerializer,
    ExportFormat,
)

# Rate Limiter (v3.2)
from .infra.api_rate_limiter import (
    RateLimiter,
    RateLimitStrategy,
    RateLimitResult,
    TokenBucket,
    SlidingWindowCounter,
    ConcurrencyLimiter,
    MultiRateLimiter,
)

# Memory Deduplication (v3.2)
from .processing.simhash_deduplicator import (
    SimHash,
    MemoryDeduplicator,
    DedupResult,
)

# Memory Compressor (v3.3)
from .processing.memory_content_compressor import (
    MemoryCompressor,
    CompressionStrategy,
    CompressionResult,
    simple_summarizer,
)

# Distributed Lock (v3.3)
from .infra.distributed_lock_manager import (
    FileLock,
    RedisDistributedLock,
    DistributedLockManager,
    LockInfo,
)

# Versioning (v3.4)
from .infra.memory_version_controller import (
    MemoryVersionControl,
    Snapshot,
    SnapshotTrigger,
)

# Service Layer (v3.4)
try:
    from .api.fastapi_service_layer import (
        create_app,
        _fastapi_available,
    )
except ImportError:
    create_app = None
    _fastapi_available = False

# Streaming (v3.5)
from .core.streaming_memory_reader import (
    MemoryStreamer,
    StreamBuffer,
    StreamConfig,
    StreamResult,
)

# Migration (v3.5)
from .infra.schema_migration_manager import (
    MigrationManager,
    Migration,
    MigrationRecord,
)

# Circuit Breaker (v3.6)
from .infra.circuit_breaker_pattern import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitStats,
    CircuitBreakerError,
    CircuitBreaker,
    CircuitBreakerRegistry,
    get_circuit_registry,
    reset_circuit_registry,
)

# Memory Cache (v3.6)
try:
    from .storage.multi_level_memory_cache import (
        CacheLevel,
        EvictionPolicy,
        CacheConfig,
        CacheStats,
        CacheKeyGenerator,
        CacheSerializer,
        MemoryCache,
    )
    _cache_available = True
except ImportError:
    _cache_available = False

# Config Manager (v3.6)
from .infra.dynamic_config_manager import (
    ConfigSource,
    DictConfigSource,
    JsonFileConfigSource,
    YamlFileConfigSource,
    EnvConfigSource,
    ConfigChangeEvent,
    ConfigManager,
    create_config_manager,
)

# Audit Logger (v3.7)
from .observability.operation_audit_logger import (
    AuditLevel,
    OperationType,
    ActorType,
    AuditRecord,
    AuditStats,
    MemoryHandler,
    FileHandler,
    LoggingHandler,
    SyslogHandler,
    AuditLogger,
    get_audit_logger,
    reset_audit_logger,
)

# Telemetry (v3.7)
try:
    from .observability.opentelemetry_tracing import (
        TelemetryConfig,
        SpanKind,
        SpanStatus,
        Span,
        TelemetryManager,
        get_telemetry,
        reset_telemetry,
    )
    _telemetry_available = True
except ImportError:
    TelemetryConfig = None
    SpanKind = None
    SpanStatus = None
    Span = None
    TelemetryManager = None
    get_telemetry = None
    reset_telemetry = None
    _telemetry_available = False

# Middleware (v3.7)
try:
    from .api.fastapi_middleware_stack import (
        AuthType,
        CORSMiddlewareConfig,
        RateLimitMiddlewareConfig,
        AuthMiddlewareConfig,
        LoggingMiddlewareConfig,
        MiddlewareConfig,
        RequestIDMiddleware,
        LoggingMiddleware,
        RateLimitMiddleware,
        AuthMiddleware,
        TimeoutMiddleware,
        build_middleware_stack,
        get_request_id,
        generate_api_key,
        hash_password,
        verify_password,
    )
    _middleware_available = True
except ImportError:
    AuthType = None
    CORSMiddlewareConfig = None
    RateLimitMiddlewareConfig = None
    AuthMiddlewareConfig = None
    LoggingMiddlewareConfig = None
    MiddlewareConfig = None
    RequestIDMiddleware = None
    LoggingMiddleware = None
    RateLimitMiddleware = None
    AuthMiddleware = None
    TimeoutMiddleware = None
    build_middleware_stack = None
    get_request_id = None
    generate_api_key = None
    hash_password = None
    verify_password = None
    _middleware_available = False

# Backup Manager (v3.8)
from .storage.backup_restore_manager import (
    BackupType,
    CompressionType,
    BackupStatus,
    BackupManifest,
    BackupStats,
    RetentionPolicy,
    EncryptionHandler,
    CloudUploader,
    S3Uploader,
    BackupManager,
)

# Monitoring (v3.8)
try:
    from .observability.system_monitoring_alerting import (
        MetricType,
        AlertSeverity,
        AlertOperator,
        NotificationChannel,
        SystemMetrics,
        AlertRule,
        AlertEvent,
        NotificationConfig,
        MetricCollector,
        SystemMetricCollector,
        ProcessMetricCollector,
        NotificationHandler,
        LogNotificationHandler,
        WebhookNotificationHandler,
        AlertEngine,
        MonitoringService,
    )
    _monitoring_available = True
except ImportError:
    MetricType = None
    AlertSeverity = None
    AlertOperator = None
    NotificationChannel = None
    SystemMetrics = None
    AlertRule = None
    AlertEvent = None
    NotificationConfig = None
    MetricCollector = None
    SystemMetricCollector = None
    ProcessMetricCollector = None
    NotificationHandler = None
    LogNotificationHandler = None
    WebhookNotificationHandler = None
    AlertEngine = None
    MonitoringService = None
    _monitoring_available = False

# CLI (v3.8)
try:
    from .api.command_line_interface import (
        CLICommand,
        InitCommand,
        StatusCommand,
        BackupCommand,
        RestoreCommand,
        ConfigCommand,
        ServeCommand,
        MonitorCommand,
        main,
    )
    _cli_available = True
except ImportError:
    CLICommand = None
    InitCommand = None
    StatusCommand = None
    BackupCommand = None
    RestoreCommand = None
    ConfigCommand = None
    ServeCommand = None
    MonitorCommand = None
    main = None
    _cli_available = False

# Hybrid Search Engine (v4.0)
from .core.hybrid_search_engine import (
    SearchHit,
    SearchStrategy,
    VectorSearchStrategy,
    KeywordSearchStrategy,
    KnowledgeGraphSearchStrategy,
    HybridSearchEngine,
)

# Memory Consolidation (v4.0)
from .core.memory_consolidation import (
    MemoryItem as ConsolidationMemoryItem,
    SemanticCluster,
    ConsolidationResult,
    ConsolidationStrategy,
    TemporalConsolidationStrategy,
    ImportanceConsolidationStrategy,
    SemanticConsolidationStrategy,
    MemoryConsolidator,
)

__version__ = "12.0.0"
__all__ = [
    # Core
    "AgentMemory",
    "AgentMemoryConfig",
    "MemoryManager",
    # Short-term
    "ShortTermMemory",
    "WorkingMemoryBuffer",
    "MemoryItem",
    # Long-term
    "LongTermMemory",
    "LongTermMemoryConfig",
    # Embedding
    "EmbeddingProvider",
    "EmbeddingConfig",
    "EmbeddingFactory",
    "SentenceTransformerProvider",
    "OpenAIProvider",
    "FakeEmbeddingProvider",
    # Vector Store
    "VectorStoreBackend",
    "VectorStoreFactory",
    "MemoryRecord",
    "SearchResult",
    "MemoryVectorStore",
    "ChromaDBBackend",
    "FAISSBackend",
    # Knowledge Graph
    "KnowledgeGraph",
    "KnowledgeGraphBuilder",
    "Entity",
    "Relation",
    "GraphSearchResult",
    # Structured Store
    "StructuredStore",
    "MemoryTable",
    "StructuredRecord",
    "QueryResult",
    # Exceptions
    "MemoryError",
    "EmbeddingError",
    "EmbeddingModelNotFoundError",
    "EmbeddingDimensionError",
    "VectorStoreError",
    "MemoryNotFoundError",
    "KnowledgeGraphError",
    "EntityNotFoundError",
    "StructuredStoreError",
    "TableNotFoundError",
    "ConfigurationError",
    "ConsolidationError",
    # Tokenizer
    "tokenize",
    "tokenize_for_search",
    # Async API
    "AsyncAgentMemory",
    # Metrics (optional)
    "MemoryMetrics",
    "timed",
    "get_metrics",
    "reset_metrics",
    # Health Check (optional)
    "HealthStatus",
    "HealthCheckResult",
    "HealthChecker",
    "create_embedding_health_check",
    "create_vector_store_health_check",
    "create_structured_store_health_check",
    "create_knowledge_graph_health_check",
    # SQLModel ORM (v3.0)
    "ORMStore",
    "ORMQuery",
    "MemoryRecordORM",
    "InteractionORM",
    "PreferenceORM",
    "FactORM",
    "create_orm_store",
    # Redis (v3.0)
    "RedisVectorStore",
    "RedisCache",
    "create_redis_store",
    "create_redis_cache",
    # Event Bus (v3.0)
    "EventBus",
    "StorageEvent",
    "StorageEventType",
    "StorageSource",
    "get_event_bus",
    "reset_event_bus",
    "on_memory_add",
    "on_memory_update",
    "on_memory_delete",
    # Unified Storage (v3.0)
    "UnifiedStorage",
    "UnifiedRecord",
    "VectorBackendType",
    "StructuredBackendType",
    "CacheBackendType",
]
