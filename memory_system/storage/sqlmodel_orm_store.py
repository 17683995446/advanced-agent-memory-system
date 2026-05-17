"""
SQLModel ORM 存储层 - 类型安全的结构化存储

使用 SQLModel (Pydantic + SQLAlchemy) 提供类型安全的 ORM 操作。
支持自动迁移、JSON 字段、关系查询等高级功能。

依赖: sqlmodel>=0.0.14
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 检查 SQLModel 可用性
# ---------------------------------------------------------------------------

try:
    from sqlmodel import SQLModel, Field, Session, create_engine, select, col
    _sqlmodel_available = True
except ImportError:
    _sqlmodel_available = False
    SQLModel = None
    Field = None
    Session = None
    create_engine = None
    select = None
    col = None


# ---------------------------------------------------------------------------
# 基础模型定义 (仅在 SQLModel 可用时)
# ---------------------------------------------------------------------------

if _sqlmodel_available:
    class MemoryRecordORM(SQLModel, table=True):
        """
        记忆记录 ORM 模型
        
        对应数据库表: memory_records
        """
        __tablename__ = "memory_records"
        
        id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
        content: str = Field(index=True)
        memory_type: str = Field(default="semantic", index=True)
        category: str = Field(default="general", index=True)
        importance: float = Field(default=0.5, ge=0.0, le=1.0)
        tags_json: str = Field(default="[]")  # JSON 序列化的标签列表
        meta_json: str = Field(default="{}")  # JSON 序列化的元数据
        timestamp: float = Field(default_factory=time.time, index=True)
        access_count: int = Field(default=0)
        last_access: float = Field(default_factory=time.time)
        created_at: datetime = Field(default_factory=datetime.utcnow)
        updated_at: datetime = Field(default_factory=datetime.utcnow)
        
        @property
        def tags(self) -> list[str]:
            """获取标签列表"""
            return json.loads(self.tags_json)
        
        @tags.setter
        def tags(self, value: list[str]):
            """设置标签列表"""
            self.tags_json = json.dumps(value)
        
        @property
        def meta(self) -> dict:
            """获取元数据"""
            return json.loads(self.meta_json)
        
        @meta.setter
        def meta(self, value: dict):
            """设置元数据"""
            self.meta_json = json.dumps(value)


    class InteractionORM(SQLModel, table=True):
        """
        交互记录 ORM 模型
        
        存储用户-Agent 交互历史
        """
        __tablename__ = "interactions"
        
        id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
        session_id: str = Field(index=True)
        role: str = Field(index=True)  # "user" or "assistant"
        content: str
        meta_json: str = Field(default="{}")
        timestamp: float = Field(default_factory=time.time, index=True)
        created_at: datetime = Field(default_factory=datetime.utcnow)
        
        @property
        def meta(self) -> dict:
            return json.loads(self.meta_json)
        
        @meta.setter
        def meta(self, value: dict):
            self.meta_json = json.dumps(value)


    class PreferenceORM(SQLModel, table=True):
        """
        用户偏好 ORM 模型
        
        存储用户偏好设置
        """
        __tablename__ = "preferences"
        
        id: Optional[int] = Field(default=None, primary_key=True)
        user_id: str = Field(index=True)
        key: str = Field(index=True)
        value_json: str  # JSON 序列化的值
        category: str = Field(default="general", index=True)
        updated_at: datetime = Field(default_factory=datetime.utcnow)
        
        @property
        def value(self) -> Any:
            return json.loads(self.value_json)
        
        @value.setter
        def value(self, val: Any):
            self.value_json = json.dumps(val)


    class FactORM(SQLModel, table=True):
        """
        事实知识 ORM 模型
        
        存储结构化事实知识
        """
        __tablename__ = "facts"
        
        id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
        subject: str = Field(index=True)
        predicate: str = Field(index=True)
        object: str = Field(index=True)
        confidence: float = Field(default=1.0, ge=0.0, le=1.0)
        source: str = Field(default="unknown", index=True)
        meta_json: str = Field(default="{}")
        created_at: datetime = Field(default_factory=datetime.utcnow)
        updated_at: datetime = Field(default_factory=datetime.utcnow)
        
        @property
        def meta(self) -> dict:
            return json.loads(self.meta_json)
        
        @meta.setter
        def meta(self, value: dict):
            self.meta_json = json.dumps(value)

else:
    # 占位类
    MemoryRecordORM = None
    InteractionORM = None
    PreferenceORM = None
    FactORM = None


# ---------------------------------------------------------------------------
# ORM 存储引擎
# ---------------------------------------------------------------------------

class ORMStore:
    """
    SQLModel ORM 存储引擎
    
    提供类型安全的 CRUD 操作和高级查询功能。
    
    Args:
        db_url: 数据库连接 URL，支持 SQLite 和 PostgreSQL
            - SQLite: "sqlite:///path/to/db.sqlite" 或 "sqlite::memory:"
            - PostgreSQL: "postgresql://user:pass@host/db"
    """
    
    def __init__(self, db_url: str = "sqlite::memory:"):
        if not _sqlmodel_available:
            raise ImportError(
                "sqlmodel is required for ORMStore. "
                "Install it with: pip install sqlmodel"
            )
        
        self._db_url = db_url
        self._engine = create_engine(db_url, echo=False)
        self._session: Optional[Session] = None
        
        # 创建所有表
        SQLModel.metadata.create_all(self._engine)
        logger.info("ORMStore initialized with db_url=%s", db_url)
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        if self._session is None:
            self._session = Session(self._engine)
        return self._session
    
    def close(self):
        """关闭数据库连接"""
        if self._session is not None:
            self._session.close()
            self._session = None
    
    # ------------------------------------------------------------------
    # 通用 CRUD 操作
    # ------------------------------------------------------------------
    
    def add(self, model: SQLModel) -> SQLModel:
        """添加记录"""
        session = self.get_session()
        session.add(model)
        session.commit()
        session.refresh(model)
        return model
    
    def add_batch(self, models: list[SQLModel]) -> list[SQLModel]:
        """批量添加记录"""
        session = self.get_session()
        for model in models:
            session.add(model)
        session.commit()
        for model in models:
            session.refresh(model)
        return models
    
    def get(self, model_class: type[SQLModel], id: Any) -> Optional[SQLModel]:
        """根据 ID 获取记录"""
        session = self.get_session()
        return session.get(model_class, id)
    
    def get_all(self, model_class: type[SQLModel]) -> list[SQLModel]:
        """获取所有记录"""
        session = self.get_session()
        return session.exec(select(model_class)).all()
    
    def update(self, model: SQLModel) -> SQLModel:
        """更新记录"""
        session = self.get_session()
        model.updated_at = datetime.utcnow()
        session.add(model)
        session.commit()
        session.refresh(model)
        return model
    
    def delete(self, model: SQLModel) -> bool:
        """删除记录"""
        session = self.get_session()
        session.delete(model)
        session.commit()
        return True
    
    def delete_by_id(self, model_class: type[SQLModel], id: Any) -> bool:
        """根据 ID 删除记录"""
        session = self.get_session()
        model = session.get(model_class, id)
        if model is None:
            return False
        session.delete(model)
        session.commit()
        return True
    
    def count(self, model_class: type[SQLModel]) -> int:
        """统计记录数量"""
        session = self.get_session()
        return len(session.exec(select(model_class)).all())
    
    # ------------------------------------------------------------------
    # 查询构建器
    # ------------------------------------------------------------------
    
    def query(self, model_class: type[SQLModel]) -> "ORMQuery":
        """创建查询构建器"""
        return ORMQuery(self.get_session(), model_class)


class ORMQuery:
    """ORM 查询构建器"""
    
    def __init__(self, session: Session, model_class: type[SQLModel]):
        self._session = session
        self._model_class = model_class
        self._statement = select(model_class)
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
    
    def where(self, *conditions) -> "ORMQuery":
        """添加 WHERE 条件"""
        self._statement = self._statement.where(*conditions)
        return self
    
    def order_by(self, *columns) -> "ORMQuery":
        """添加排序"""
        self._statement = self._statement.order_by(*columns)
        return self
    
    def limit(self, n: int) -> "ORMQuery":
        """限制结果数量"""
        self._limit = n
        self._statement = self._statement.limit(n)
        return self
    
    def offset(self, n: int) -> "ORMQuery":
        """设置偏移量"""
        self._offset = n
        self._statement = self._statement.offset(n)
        return self
    
    def all(self) -> list[SQLModel]:
        """获取所有结果"""
        return self._session.exec(self._statement).all()
    
    def first(self) -> Optional[SQLModel]:
        """获取第一个结果"""
        return self._session.exec(self._statement).first()
    
    def one(self) -> SQLModel:
        """获取唯一结果（不存在则抛出异常）"""
        return self._session.exec(self._statement).one()
    
    def count(self) -> int:
        """统计结果数量"""
        return len(self.all())


# ---------------------------------------------------------------------------
# 便捷工厂函数
# ---------------------------------------------------------------------------

def create_orm_store(db_path: str = ":memory:") -> ORMStore:
    """创建 ORM 存储实例"""
    if not _sqlmodel_available:
        raise ImportError("sqlmodel is required. Install with: pip install sqlmodel")
    
    if db_path == ":memory:":
        return ORMStore("sqlite:///:memory:")
    else:
        return ORMStore(f"sqlite:///{db_path}")


__all__ = [
    "ORMStore",
    "ORMQuery",
    "MemoryRecordORM",
    "InteractionORM",
    "PreferenceORM",
    "FactORM",
    "create_orm_store",
    "_sqlmodel_available",
]
