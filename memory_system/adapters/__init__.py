"""
开源工具集成适配器

提供与主流开源工具的集成接口：
1. ChromaDB - 向量存储（替代内存向量存储）
2. FAISS - 高性能向量检索
3. NetworkX - 知识图谱（替代内存图谱）
4. 兼容 LangChain / LlamaIndex 接口

设计原则：
- 优先使用成熟开源方案
- 保持接口一致性
- 支持无缝切换后端
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class VectorStoreAdapter(ABC):
    """向量存储适配器基类"""

    @abstractmethod
    def add(self, ids: list[str], embeddings: list[list[float]], metadatas: list[dict]) -> None:
        """添加向量"""
        pass

    @abstractmethod
    def search(self, query_embedding: list[float], top_k: int = 10) -> list[dict]:
        """搜索相似向量"""
        pass

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """删除向量"""
        pass


class ChromaDBAdapter(VectorStoreAdapter):
    """
    ChromaDB 向量存储适配器
    
    优点：
    - 开箱即用，零配置
    - 内置 Embedding 支持
    - 与 LangChain/LlamaIndex 一流集成
    - 适合原型开发和中小规模应用
    
    安装：pip install chromadb
    """

    def __init__(
        self,
        collection_name: str = "agent_memory",
        persist_directory: Optional[str] = None,
        embedding_function: Optional[Any] = None,
    ):
        self._collection_name = collection_name
        self._persist_directory = persist_directory
        self._embedding_function = embedding_function
        self._client = None
        self._collection = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """延迟初始化"""
        if self._initialized:
            return

        try:
            import chromadb
            
            if self._persist_directory:
                self._client = chromadb.PersistentClient(path=self._persist_directory)
            else:
                self._client = chromadb.Client()

            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                embedding_function=self._embedding_function,
            )
            self._initialized = True
            logger.info("ChromaDB initialized: collection=%s", self._collection_name)
        except ImportError:
            raise ImportError("ChromaDB not installed. Run: pip install chromadb")

    def add(self, ids: list[str], embeddings: list[list[float]], metadatas: list[dict]) -> None:
        self._ensure_initialized()
        # ChromaDB 需要 documents 参数，我们使用空字符串
        documents = [m.get("content", "") for m in metadatas]
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def search(self, query_embedding: list[float], top_k: int = 10) -> list[dict]:
        self._ensure_initialized()
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )
        
        # 标准化结果格式
        formatted = []
        for i, id_ in enumerate(results["ids"][0]):
            formatted.append({
                "id": id_,
                "score": 1 - results["distances"][0][i] if results.get("distances") else 1.0,
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                "content": results["documents"][0][i] if results.get("documents") else "",
            })
        return formatted

    def delete(self, ids: list[str]) -> None:
        self._ensure_initialized()
        self._collection.delete(ids=ids)

    def count(self) -> int:
        self._ensure_initialized()
        return self._collection.count()


class FAISSAdapter(VectorStoreAdapter):
    """
    FAISS 向量存储适配器
    
    优点：
    - Meta 开发，高性能
    - 支持 GPU 加速
    - 增量索引更新
    - 适合本地部署和大规模数据
    
    安装：pip install faiss-cpu (或 faiss-gpu)
    """

    def __init__(self, dimension: int = 128):
        self._dimension = dimension
        self._index = None
        self._id_map: dict[int, str] = {}  # FAISS index -> memory id
        self._metadata_store: dict[str, dict] = {}  # memory id -> metadata
        self._next_idx = 0

    def _ensure_initialized(self) -> None:
        if self._index is not None:
            return

        try:
            import faiss
            self._index = faiss.IndexFlatIP(self._dimension)  # 内积相似度
            logger.info("FAISS initialized: dimension=%d", self._dimension)
        except ImportError:
            raise ImportError("FAISS not installed. Run: pip install faiss-cpu")

    def add(self, ids: list[str], embeddings: list[list[float]], metadatas: list[dict]) -> None:
        self._ensure_initialized()
        import numpy as np

        vectors = np.array(embeddings, dtype=np.float32)
        
        # 归一化（用于内积相似度）
        faiss = __import__("faiss")
        faiss.normalize_L2(vectors)

        start_idx = self._next_idx
        self._index.add(vectors)

        for i, (id_, meta) in enumerate(zip(ids, metadatas)):
            self._id_map[start_idx + i] = id_
            self._metadata_store[id_] = meta

        self._next_idx += len(ids)

    def search(self, query_embedding: list[float], top_k: int = 10) -> list[dict]:
        self._ensure_initialized()
        import numpy as np

        query = np.array([query_embedding], dtype=np.float32)
        faiss = __import__("faiss")
        faiss.normalize_L2(query)

        scores, indices = self._index.search(query, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS 返回 -1 表示不足 top_k
                continue
            memory_id = self._id_map.get(idx)
            if memory_id:
                results.append({
                    "id": memory_id,
                    "score": float(score),
                    "metadata": self._metadata_store.get(memory_id, {}),
                })
        return results

    def delete(self, ids: list[str]) -> None:
        # FAISS 不支持直接删除，需要重建索引
        # 这里简化处理：从元数据存储中移除
        for id_ in ids:
            self._metadata_store.pop(id_, None)
        logger.warning("FAISS delete requires index rebuild for full effect")


class KnowledgeGraphAdapter(ABC):
    """知识图谱适配器基类"""

    @abstractmethod
    def add_entity(self, name: str, entity_type: str, properties: dict = None) -> None:
        pass

    @abstractmethod
    def add_relation(self, source: str, target: str, relation_type: str) -> None:
        pass

    @abstractmethod
    def find_path(self, source: str, target: str) -> Optional[list[str]]:
        pass


class NetworkXAdapter(KnowledgeGraphAdapter):
    """
    NetworkX 知识图谱适配器
    
    优点：
    - 纯 Python，无外部依赖
    - 丰富的图算法
    - 适合中小规模知识图谱
    - 支持多种图类型
    
    安装：pip install networkx
    """

    def __init__(self):
        self._graph = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        try:
            import networkx as nx
            self._graph = nx.MultiDiGraph()  # 支持多重有向图
            self._initialized = True
            logger.info("NetworkX graph initialized")
        except ImportError:
            raise ImportError("NetworkX not installed. Run: pip install networkx")

    def add_entity(self, name: str, entity_type: str, properties: dict = None) -> None:
        self._ensure_initialized()
        self._graph.add_node(name, entity_type=entity_type, **(properties or {}))

    def add_relation(self, source: str, target: str, relation_type: str) -> None:
        self._ensure_initialized()
        self._graph.add_edge(source, target, relation_type=relation_type)

    def find_path(self, source: str, target: str) -> Optional[list[str]]:
        self._ensure_initialized()
        try:
            import networkx as nx
            path = nx.shortest_path(self._graph, source, target)
            return list(path)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_neighbors(self, node: str) -> list[str]:
        self._ensure_initialized()
        return list(self._graph.neighbors(node))

    def get_entity_types(self) -> dict[str, int]:
        """获取各类型实体数量"""
        self._ensure_initialized()
        from collections import Counter
        types = Counter(
            data.get("entity_type", "unknown")
            for _, data in self._graph.nodes(data=True)
        )
        return dict(types)

    def get_relation_types(self) -> dict[str, int]:
        """获取各类型关系数量"""
        self._ensure_initialized()
        from collections import Counter
        types = Counter(
            data.get("relation_type", "unknown")
            for _, _, data in self._graph.edges(data=True)
        )
        return dict(types)


class LangChainCompatible:
    """
    LangChain 兼容接口
    
    提供与 LangChain Memory 接口兼容的适配器。
    使 Agent Memory System 可直接用于 LangChain Agent。
    """

    def __init__(self, memory_system: Any):
        self._memory = memory_system

    def load_memory_variables(self, inputs: dict) -> dict:
        """LangChain Memory 接口：加载记忆变量"""
        query = inputs.get("input", "")
        results = self._memory.recall(query, top_k=5)
        
        context = "\n".join(
            r.get("content", str(r)) for r in results
        )
        return {"memory_context": context}

    def save_context(self, inputs: dict, outputs: dict) -> None:
        """LangChain Memory 接口：保存上下文"""
        user_input = inputs.get("input", "")
        ai_output = outputs.get("output", "")

        if user_input:
            self._memory.remember(user_input, category="conversation")
        if ai_output:
            self._memory.remember(ai_output, category="response")

    def clear(self) -> None:
        """LangChain Memory 接口：清空记忆"""
        # 保留实现给具体类
        pass


__all__ = [
    "VectorStoreAdapter",
    "ChromaDBAdapter",
    "FAISSAdapter",
    "KnowledgeGraphAdapter",
    "NetworkXAdapter",
    "LangChainCompatible",
]