"""
混合搜索引擎模块 (Hybrid Search Engine)

Agent Memory System v4.0 的核心搜索组件，将多种搜索策略（向量相似度、
关键词匹配、知识图谱遍历）融合为统一的智能搜索体验。

本模块的设计原则：
- 站在巨人的肩膀上：复用已有的 vector_similarity_store、knowledge_graph_engine
  和 chinese_english_tokenizer 模块，不重复造轮子。
- 高度模块化：每种搜索策略都是可插拔的组件，通过统一的 SearchStrategy
  抽象接口接入。
- 生产就绪：完整的错误处理、日志记录、类型标注和文档字符串。

融合方法：
- RRF (Reciprocal Rank Fusion): 倒数排名融合，对每个策略的排名取倒数后求和。
- weighted: 加权融合，按策略权重对原始分数加权求和。
- max: 取各策略中的最高分数。

依赖说明：
- 仅使用 Python 标准库（difflib, math, collections, heapq, logging, abc, typing）
  以及项目内已有的 memory_system 模块。
- 不引入任何额外外部依赖。

典型用法::

    from memory_system.core.hybrid_search_engine import (
        HybridSearchEngine, VectorSearchStrategy, KeywordSearchStrategy,
        KnowledgeGraphSearchStrategy,
    )

    engine = HybridSearchEngine()
    engine.add_strategy(VectorSearchStrategy(vector_store, embedding_provider), weight=1.0)
    engine.add_strategy(KeywordSearchStrategy(memory_records), weight=0.8)
    engine.add_strategy(KnowledgeGraphSearchStrategy(knowledge_graph), weight=0.6)

    results = engine.search("如何优化系统性能", top_k=10)
"""

from __future__ import annotations

import heapq
import logging
import math
import re
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Any, NamedTuple, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "SearchHit",
    "SearchStrategy",
    "VectorSearchStrategy",
    "KeywordSearchStrategy",
    "KnowledgeGraphSearchStrategy",
    "HybridSearchEngine",
]


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

class SearchHit(NamedTuple):
    """单条搜索结果。

    Attributes:
        id: 记录的唯一标识符。
        content: 记录的文本内容。
        score: 相关性得分（越高越相关）。
        source: 结果来源策略标识，如 ``"vector"``、``"keyword"``、``"graph"``。
        metadata: 附带的元数据字典。
    """

    id: str
    content: str
    score: float
    source: str
    metadata: dict


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------

class SearchStrategy(ABC):
    """搜索策略抽象基类。

    所有具体的搜索策略都必须继承此类并实现 :meth:`search` 方法。
    策略之间通过统一的 ``SearchHit`` 返回格式进行解耦，使得
    :class:`HybridSearchEngine` 可以透明地组合任意数量的策略。
    """

    @property
    def name(self) -> str:
        """策略名称，用于日志和结果标记。默认取类名。"""
        return self.__class__.__name__

    @abstractmethod
    def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:
        """执行搜索并返回结果列表。

        Args:
            query: 用户查询字符串。
            top_k: 最大返回结果数量。
            **kwargs: 策略特定的额外参数。

        Returns:
            按 score 降序排列的 :class:`SearchHit` 列表。
        """
        ...


# ---------------------------------------------------------------------------
# 向量相似度搜索策略
# ---------------------------------------------------------------------------

class VectorSearchStrategy(SearchStrategy):
    """基于向量相似度的搜索策略。

    复用已有的 :class:`~memory_system.storage.vector_store.VectorStoreBackend`
    进行 embedding 检索。需要外部提供向量存储后端和 embedding 提供者。

    Args:
        vector_store: 向量存储后端实例，需实现 ``search`` 方法。
        embedding_provider: Embedding 提供者，需为可调用对象，
            接收文本字符串并返回 ``list[float]`` 向量。
    """

    def __init__(
        self,
        vector_store: Any,
        embedding_provider: Any,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider
        logger.info("VectorSearchStrategy 已初始化")

    @property
    def name(self) -> str:
        return "vector"

    def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:
        """通过向量相似度搜索记忆记录。

        Args:
            query: 查询文本。
            top_k: 最大返回数量。
            **kwargs: 可选参数：
                - ``filter`` (dict): 向量存储过滤条件。

        Returns:
            按相似度降序排列的搜索结果列表。
        """
        try:
            query_embedding = self._embedding_provider(query)
            filter_cond = kwargs.get("filter")
            raw_results = self._vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filter=filter_cond,
            )
            hits: list[SearchHit] = []
            for result in raw_results:
                record = result.record
                hits.append(
                    SearchHit(
                        id=record.id,
                        content=record.content,
                        score=float(result.score),
                        source=self.name,
                        metadata={
                            "memory_type": record.memory_type,
                            "category": record.category,
                            "importance": record.importance,
                            "tags": record.tags,
                            **record.metadata,
                        },
                    )
                )
            logger.debug(
                "向量搜索完成，查询='%s'，返回 %d 条结果", query, len(hits)
            )
            return hits
        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("向量搜索失败: %s", e, exc_info=True)
            return []


# ---------------------------------------------------------------------------
# 关键词搜索策略（BM25-like + 模糊匹配）
# ---------------------------------------------------------------------------

class KeywordSearchStrategy(SearchStrategy):
    """基于关键词的全文搜索策略。

    使用 Python 标准库实现：
    - **倒排索引**：基于 ``collections.defaultdict`` 构建。
    - **TF-IDF 评分**：使用 ``math.log`` 计算 IDF，实现 BM25-like 评分。
    - **模糊匹配**：使用 ``difflib.SequenceMatcher`` 进行模糊字符串匹配。

    支持中英文混合文本，内部使用项目已有的
    :func:`~memory_system.processing.chinese_english_tokenizer.tokenize_for_search`
    进行分词；若该模块不可用，则回退到内置的简易分词器。

    Args:
        memory_records: 初始记忆记录列表。每条记录可以是包含
            ``id``、``content`` 字段的字典，也可以是具有同名属性的
            Pydantic 模型实例。传入 ``None`` 表示空索引。
        k1: BM25 的词频饱和参数，默认 1.5。
        b: BM25 的文档长度归一化参数，默认 0.75。
    """

    # BM25 超参数默认值
    _DEFAULT_K1: float = 1.5
    _DEFAULT_B: float = 0.75

    def __init__(
        self,
        memory_records: Optional[list[Any]] = None,
        k1: float = _DEFAULT_K1,
        b: float = _DEFAULT_B,
    ) -> None:
        self._k1 = k1
        self._b = b
        # 倒排索引: token -> {doc_id: [token_positions]}
        self._inverted_index: dict[str, dict[str, list[int]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # 文档存储: doc_id -> {"content": str, "tokens": list[str]}
        self._documents: dict[str, dict[str, Any]] = {}
        # 文档频率: token -> 出现在多少个文档中
        self._doc_freq: Counter[str] = Counter()
        # 文档总数
        self._total_docs: int = 0
        # 平均文档长度（token 数）
        self._avg_doc_len: float = 0.0

        # 尝试导入项目分词器
        self._tokenizer = self._load_tokenizer()

        if memory_records:
            self.build_index(memory_records)
        logger.info(
            "KeywordSearchStrategy 已初始化，文档数=%d，k1=%.2f，b=%.2f",
            self._total_docs,
            self._k1,
            self._b,
        )

    @property
    def name(self) -> str:
        return "keyword"

    # ------------------------------------------------------------------
    # 分词器加载
    # ------------------------------------------------------------------

    @staticmethod
    def _load_tokenizer() -> Any:
        """尝试加载项目内置的中英文分词器，失败则返回 None。"""
        try:
            from memory_system.processing.chinese_english_tokenizer import (
                tokenize_for_search,
            )
            return tokenize_for_search
        except ImportError:
            logger.debug("chinese_english_tokenizer 不可用，使用内置简易分词器")
            return None

    def _tokenize(self, text: str) -> list[str]:
        """对文本进行分词。

        优先使用项目内置分词器，回退到基于正则的简易分词器。

        Args:
            text: 待分词文本。

        Returns:
            分词结果列表。
        """
        if self._tokenizer is not None:
            try:
                return self._tokenizer(text)
            except (ValueError, TypeError, RuntimeError):
                pass
        # 内置回退分词器：英文按单词，中文按双字窗口
        tokens: list[str] = []
        # 英文单词
        tokens.extend(re.findall(r"[a-zA-Z0-9]+", text.lower()))
        # 中文双字窗口
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        for i in range(len(chinese_chars) - 1):
            tokens.append(chinese_chars[i] + chinese_chars[i + 1])
        if len(chinese_chars) == 1:
            tokens.append(chinese_chars[0])
        return tokens

    # ------------------------------------------------------------------
    # 索引构建
    # ------------------------------------------------------------------

    def build_index(self, memory_records: list[Any]) -> None:
        """从记忆记录列表构建倒排索引。

        Args:
            memory_records: 记录列表。每条记录需具有 ``id`` 和 ``content``
                属性或键。
        """
        for record in memory_records:
            doc_id = getattr(record, "id", None) or record.get("id", "")
            content = getattr(record, "content", None) or record.get("content", "")
            if not doc_id or not content:
                continue
            self.add_document(doc_id, content)
        self._recompute_stats()
        logger.info("倒排索引构建完成，共 %d 篇文档", self._total_docs)

    def add_document(self, doc_id: str, content: str) -> None:
        """添加单篇文档到索引。

        Args:
            doc_id: 文档唯一标识。
            content: 文档文本内容。
        """
        tokens = self._tokenize(content)
        self._documents[doc_id] = {"content": content, "tokens": tokens}

        # 更新倒排索引
        seen_tokens: set[str] = set()
        for pos, token in enumerate(tokens):
            self._inverted_index[token][doc_id].append(pos)
            if token not in seen_tokens:
                self._doc_freq[token] += 1
                seen_tokens.add(token)

        self._total_docs = len(self._documents)
        self._recompute_stats()

    def remove_document(self, doc_id: str) -> bool:
        """从索引中移除文档。

        Args:
            doc_id: 待移除的文档标识。

        Returns:
            成功移除返回 ``True``，文档不存在返回 ``False``。
        """
        if doc_id not in self._documents:
            return False
        tokens = self._documents[doc_id]["tokens"]
        token_set = set(tokens)
        for token in token_set:
            if token in self._inverted_index and doc_id in self._inverted_index[token]:
                del self._inverted_index[token][doc_id]
                if not self._inverted_index[token]:
                    del self._inverted_index[token]
                self._doc_freq[token] -= 1
                if self._doc_freq[token] <= 0:
                    del self._doc_freq[token]
        del self._documents[doc_id]
        self._total_docs = len(self._documents)
        self._recompute_stats()
        return True

    def _recompute_stats(self) -> None:
        """重新计算平均文档长度等统计信息。"""
        if self._total_docs == 0:
            self._avg_doc_len = 0.0
        else:
            total_len = sum(len(doc["tokens"]) for doc in self._documents.values())
            self._avg_doc_len = total_len / self._total_docs

    # ------------------------------------------------------------------
    # BM25 评分
    # ------------------------------------------------------------------

    def _bm25_score(self, token: str, doc_id: str) -> float:
        """计算单个 token 对特定文档的 BM25 得分。

        BM25 公式::

            score = IDF * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avgdl))

        其中：
        - IDF = log((N - df + 0.5) / (df + 0.5) + 1)
        - tf = token 在文档中的出现次数
        - dl = 文档长度（token 数）
        - avgdl = 平均文档长度

        Args:
            token: 查询词。
            doc_id: 文档标识。

        Returns:
            BM25 得分。
        """
        if doc_id not in self._documents:
            return 0.0
        if token not in self._inverted_index or doc_id not in self._inverted_index[token]:
            return 0.0

        # 词频
        tf = len(self._inverted_index[token][doc_id])
        # 文档频率
        df = self._doc_freq.get(token, 0)
        # 文档长度
        dl = len(self._documents[doc_id]["tokens"])
        avgdl = self._avg_doc_len if self._avg_doc_len > 0 else 1.0
        N = self._total_docs

        # IDF 计算，使用 Robertson-Sparck Jones 公式的平滑版本
        idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

        # BM25 TF 分量
        numerator = tf * (self._k1 + 1.0)
        denominator = tf + self._k1 * (1.0 - self._b + self._b * dl / avgdl)

        return idf * numerator / denominator

    # ------------------------------------------------------------------
    # 模糊匹配
    # ------------------------------------------------------------------

    def _fuzzy_match_score(self, query: str, content: str) -> float:
        """使用 SequenceMatcher 计算查询与文档内容的模糊相似度。

        Args:
            query: 原始查询字符串。
            content: 文档内容。

        Returns:
            模糊匹配得分，范围 [0.0, 1.0]。
        """
        if not query or not content:
            return 0.0
        # 对于长文档，取前 500 字符进行匹配以提升性能
        snippet = content[:500] if len(content) > 500 else content
        return SequenceMatcher(None, query.lower(), snippet.lower()).ratio()

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:
        """执行关键词搜索。

        搜索流程：
        1. 对查询进行分词。
        2. 对每个查询词计算 BM25 得分并累加。
        3. 对 BM25 得分最高的候选文档进行模糊匹配加分。
        4. 按综合得分降序返回 top_k 结果。

        Args:
            query: 查询文本。
            top_k: 最大返回数量。
            **kwargs: 可选参数：
                - ``fuzzy_weight`` (float): 模糊匹配权重，默认 0.3。
                - ``min_score`` (float): 最低得分阈值，默认 0.0。

        Returns:
            按综合得分降序排列的搜索结果列表。
        """
        if self._total_docs == 0:
            logger.debug("关键词搜索跳过：索引为空")
            return []

        fuzzy_weight = kwargs.get("fuzzy_weight", 0.3)
        min_score = kwargs.get("min_score", 0.0)

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # 第一阶段：BM25 评分
        doc_scores: dict[str, float] = defaultdict(float)
        for token in query_tokens:
            if token not in self._inverted_index:
                continue
            for doc_id in self._inverted_index[token]:
                doc_scores[doc_id] += self._bm25_score(token, doc_id)

        if not doc_scores:
            logger.debug("关键词搜索无 BM25 命中，查询='%s'", query)
            return []

        # 第二阶段：对 top 候选进行模糊匹配加分
        # 先取 BM25 得分最高的候选（最多 top_k * 3 个，避免过多模糊计算）
        bm25_candidates = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        fuzzy_limit = min(top_k * 3, len(bm25_candidates))

        hits: list[SearchHit] = []
        for doc_id, bm25_score in bm25_candidates[:fuzzy_limit]:
            content = self._documents[doc_id]["content"]
            fuzzy_score = self._fuzzy_match_score(query, content)
            # 综合得分 = BM25 + fuzzy_weight * fuzzy_score
            # fuzzy_score 范围 [0,1]，BM25 通常范围较大，这里对 BM25 做归一化
            max_bm25 = bm25_candidates[0][1] if bm25_candidates else 1.0
            normalized_bm25 = bm25_score / max_bm25 if max_bm25 > 0 else 0.0
            combined_score = normalized_bm25 + fuzzy_weight * fuzzy_score

            if combined_score >= min_score:
                hits.append(
                    SearchHit(
                        id=doc_id,
                        content=content,
                        score=round(combined_score, 6),
                        source=self.name,
                        metadata={"bm25_score": round(bm25_score, 6),
                                  "fuzzy_score": round(fuzzy_score, 6)},
                    )
                )

        hits.sort(key=lambda h: h.score, reverse=True)
        results = hits[:top_k]
        logger.debug(
            "关键词搜索完成，查询='%s'，返回 %d 条结果", query, len(results)
        )
        return results


# ---------------------------------------------------------------------------
# 知识图谱搜索策略
# ---------------------------------------------------------------------------

class KnowledgeGraphSearchStrategy(SearchStrategy):
    """基于知识图谱的实体/关系搜索策略。

    复用已有的 :class:`~memory_system.processing.knowledge_graph_engine.KnowledgeGraph`
    进行实体搜索和关系遍历。搜索流程：

    1. 在知识图谱中进行实体模糊搜索。
    2. 对命中的实体，获取其邻居实体和关联关系。
    3. 将实体描述和关系信息组合为搜索结果。

    Args:
        knowledge_graph: 知识图谱实例，需实现 ``search_entities`` 和
            ``get_neighbors`` 方法。
        max_depth: 邻居遍历深度，默认 1。
    """

    def __init__(self, knowledge_graph: Any, max_depth: int = 1) -> None:
        self._kg = knowledge_graph
        self._max_depth = max_depth
        logger.info("KnowledgeGraphSearchStrategy 已初始化，遍历深度=%d", max_depth)

    @property
    def name(self) -> str:
        return "graph"

    def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:
        """在知识图谱中搜索与查询相关的实体和关系。

        Args:
            query: 查询文本。
            top_k: 最大返回数量。
            **kwargs: 可选参数：
                - ``max_depth`` (int): 覆盖实例级别的邻居遍历深度。
                - ``include_relations`` (bool): 是否在结果中包含关系信息，默认 True。

        Returns:
            按相关性得分降序排列的搜索结果列表。
        """
        try:
            max_depth = kwargs.get("max_depth", self._max_depth)
            include_relations = kwargs.get("include_relations", True)

            # 在知识图谱中搜索实体
            entity_results = self._kg.search_entities(query, top_k=top_k)

            if not entity_results:
                logger.debug("知识图谱搜索无命中，查询='%s'", query)
                return []

            hits: list[SearchHit] = []
            for entity, score in entity_results:
                # 构建内容描述
                content_parts = [f"[{entity.entity_type}] {entity.name}"]
                if entity.description:
                    content_parts.append(entity.description)

                metadata: dict[str, Any] = {
                    "entity_type": entity.entity_type,
                    "entity_name": entity.name,
                    "entity_properties": entity.properties,
                }

                # 获取关联关系
                if include_relations:
                    try:
                        relations = self._kg.get_relations(entity.name, direction="both")
                        if relations:
                            rel_descriptions = []
                            for rel in relations:
                                rel_descriptions.append(
                                    f"{rel.source} --[{rel.relation_type}]--> {rel.target}"
                                )
                            content_parts.append("关系: " + "; ".join(rel_descriptions))
                            metadata["relations"] = [
                                {
                                    "source": r.source,
                                    "target": r.target,
                                    "type": r.relation_type,
                                    "weight": r.weight,
                                }
                                for r in relations
                            ]
                    except (AttributeError, KeyError, ValueError) as exc:
                        logger.warning("获取实体关系失败: %s", exc)

                # 获取邻居实体信息
                try:
                    neighbors = self._kg.get_neighbors(entity.name, max_depth=max_depth)
                    if neighbors:
                        neighbor_names = [n.name for n in neighbors[:5]]
                        content_parts.append("相关: " + ", ".join(neighbor_names))
                        metadata["neighbors"] = neighbor_names
                except (AttributeError, KeyError, ValueError) as exc:
                    logger.warning("获取邻居实体失败: %s", exc)

                content = " | ".join(content_parts)
                hits.append(
                    SearchHit(
                        id=f"graph:{entity.name}",
                        content=content,
                        score=round(float(score), 6),
                        source=self.name,
                        metadata=metadata,
                    )
                )

            logger.debug(
                "知识图谱搜索完成，查询='%s'，返回 %d 条结果", query, len(hits)
            )
            return hits
        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("知识图谱搜索失败: %s", e, exc_info=True)
            return []


# ---------------------------------------------------------------------------
# 混合搜索引擎
# ---------------------------------------------------------------------------

class HybridSearchEngine:
    """混合搜索引擎，将多种搜索策略融合为统一的搜索接口。

    支持三种结果融合方法：

    - **rrf** (Reciprocal Rank Fusion): 倒数排名融合。
      公式: ``score = sum(1 / (k + rank))``，其中 ``k`` 为平滑常数（默认 60）。
      该方法对分数尺度不敏感，鲁棒性强。
    - **weighted**: 加权融合。按各策略权重对原始分数加权求和后归一化。
    - **max**: 取各策略中同一文档的最高分数。

    Args:
        strategies: 初始搜索策略列表，可为空。
        fusion_method: 融合方法，可选 ``"rrf"``、``"weighted"``、``"max"``，
            默认 ``"rrf"``。
    """

    _SUPPORTED_FUSION_METHODS = {"rrf", "weighted", "max"}

    def __init__(
        self,
        strategies: Optional[list[SearchStrategy]] = None,
        fusion_method: str = "rrf",
    ) -> None:
        if fusion_method not in self._SUPPORTED_FUSION_METHODS:
            raise ValueError(
                f"不支持的融合方法 '{fusion_method}'，"
                f"可选: {sorted(self._SUPPORTED_FUSION_METHODS)}"
            )
        self._fusion_method = fusion_method
        # 策略列表及其权重
        self._strategies: list[tuple[SearchStrategy, float]] = []
        if strategies:
            for strategy in strategies:
                self.add_strategy(strategy)
        logger.info(
            "HybridSearchEngine 已初始化，融合方法='%s'，策略数=%d",
            fusion_method,
            len(self._strategies),
        )

    @property
    def fusion_method(self) -> str:
        """当前使用的融合方法。"""
        return self._fusion_method

    @property
    def strategy_count(self) -> int:
        """已注册的搜索策略数量。"""
        return len(self._strategies)

    def add_strategy(self, strategy: SearchStrategy, weight: float = 1.0) -> None:
        """添加搜索策略。

        Args:
            strategy: 搜索策略实例。
            weight: 策略权重，用于 ``weighted`` 融合方法。
                对 ``rrf`` 和 ``max`` 方法无影响。默认 1.0。

        Raises:
            TypeError: 如果 strategy 不是 :class:`SearchStrategy` 的实例。
            ValueError: 如果 weight 为负数。
        """
        if not isinstance(strategy, SearchStrategy):
            raise TypeError(
                f"strategy 必须是 SearchStrategy 的实例，"
                f" got {type(strategy).__name__}"
            )
        if weight < 0:
            raise ValueError(f"weight 不能为负数，got {weight}")
        self._strategies.append((strategy, weight))
        logger.info(
            "已添加搜索策略 '%s'，权重=%.2f", strategy.name, weight
        )

    def remove_strategy(self, strategy_name: str) -> bool:
        """按名称移除搜索策略。

        Args:
            strategy_name: 策略名称（即 ``strategy.name`` 属性值）。

        Returns:
            成功移除返回 ``True``，未找到返回 ``False``。
        """
        original_len = len(self._strategies)
        self._strategies = [
            (s, w) for s, w in self._strategies if s.name != strategy_name
        ]
        removed = len(self._strategies) < original_len
        if removed:
            logger.info("已移除搜索策略 '%s'", strategy_name)
        return removed

    def search(self, query: str, top_k: int = 10, **kwargs: Any) -> list[SearchHit]:
        """执行混合搜索。

        依次调用所有已注册的搜索策略，然后使用配置的融合方法将结果合并。

        Args:
            query: 查询文本。
            top_k: 最大返回结果数量。
            **kwargs: 传递给各搜索策略的额外参数。

        Returns:
            按融合得分降序排列的搜索结果列表。
        """
        if not self._strategies:
            logger.warning("混合搜索跳过：未注册任何搜索策略")
            return []

        if not query or not query.strip():
            logger.warning("混合搜索跳过：查询为空")
            return []

        # 并行调用所有策略（同步执行，按顺序调用）
        all_result_lists: list[list[SearchHit]] = []
        for strategy, weight in self._strategies:
            try:
                hits = strategy.search(query, top_k=top_k * 2, **kwargs)
                all_result_lists.append(hits)
                logger.debug(
                    "策略 '%s' 返回 %d 条结果", strategy.name, len(hits)
                )
            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(
                    "策略 '%s' 执行失败: %s", strategy.name, e, exc_info=True
                )
                all_result_lists.append([])

        # 检查是否有任何结果
        total_hits = sum(len(r) for r in all_result_lists)
        if total_hits == 0:
            logger.debug("所有策略均无结果，查询='%s'", query)
            return []

        # 融合结果
        if self._fusion_method == "rrf":
            fused = self._reciprocal_rank_fusion(all_result_lists)
        elif self._fusion_method == "weighted":
            weights = [w for _, w in self._strategies]
            fused = self._weighted_fusion(all_result_lists, weights)
        elif self._fusion_method == "max":
            fused = self._max_fusion(all_result_lists)
        else:
            # 不应到达此处，已在 __init__ 中校验
            fused = self._reciprocal_rank_fusion(all_result_lists)

        # 截取 top_k
        results = fused[:top_k]
        logger.info(
            "混合搜索完成，查询='%s'，融合方法='%s'，返回 %d 条结果",
            query,
            self._fusion_method,
            len(results),
        )
        return results

    # ------------------------------------------------------------------
    # 融合方法实现
    # ------------------------------------------------------------------

    @staticmethod
    def _reciprocal_rank_fusion(
        result_lists: list[list[SearchHit]],
        k: int = 60,
    ) -> list[SearchHit]:
        """倒数排名融合 (Reciprocal Rank Fusion)。

        对每个策略中的结果按排名计算得分 ``1 / (k + rank)``，
        然后按文档 ID 聚合得分。同一文档在多个策略中出现时得分累加。

        Args:
            result_lists: 各策略返回的搜索结果列表。
            k: RRF 平滑常数，防止高排名结果主导最终得分。默认 60。

        Returns:
            按 RRF 得分降序排列的去重搜索结果列表。
        """
        # 聚合得分: doc_id -> (total_score, best_hit)
        score_map: dict[str, tuple[float, SearchHit]] = {}

        for results in result_lists:
            for rank, hit in enumerate(results, start=1):
                rrf_score = 1.0 / (k + rank)
                if hit.id in score_map:
                    prev_score, prev_hit = score_map[hit.id]
                    new_score = prev_score + rrf_score
                    # 保留得分最高的来源信息
                    if hit.score > prev_hit.score:
                        merged_meta = {**prev_hit.metadata, **hit.metadata}
                        best_hit = hit._replace(
                            score=round(new_score, 6),
                            source="hybrid",
                            metadata=merged_meta,
                        )
                    else:
                        best_hit = prev_hit._replace(
                            score=round(new_score, 6),
                            source="hybrid",
                        )
                    score_map[hit.id] = (new_score, best_hit)
                else:
                    new_hit = hit._replace(
                        score=round(rrf_score, 6),
                        source="hybrid",
                    )
                    score_map[hit.id] = (rrf_score, new_hit)

        # 按得分降序排列
        fused = [hit for _, (_, hit) in score_map.items()]
        fused.sort(key=lambda h: h.score, reverse=True)
        return fused

    @staticmethod
    def _weighted_fusion(
        result_lists: list[list[SearchHit]],
        weights: list[float],
    ) -> list[SearchHit]:
        """加权融合。

        按各策略权重对原始分数加权求和。分数先在策略内部归一化到 [0, 1]，
        然后按权重累加。

        Args:
            result_lists: 各策略返回的搜索结果列表。
            weights: 各策略对应的权重列表，长度须与 ``result_lists`` 一致。

        Returns:
            按加权得分降序排列的去重搜索结果列表。

        Raises:
            ValueError: 如果 weights 长度与 result_lists 不一致。
        """
        if len(weights) != len(result_lists):
            raise ValueError(
                f"权重数量 ({len(weights)}) 与结果列表数量 "
                f"({len(result_lists)}) 不一致"
            )

        # 聚合得分: doc_id -> (total_score, best_hit)
        score_map: dict[str, tuple[float, SearchHit]] = {}

        for results, weight in zip(result_lists, weights):
            if not results or weight <= 0:
                continue
            # 归一化：将分数映射到 [0, 1]
            max_score = max(h.score for h in results)
            min_score = min(h.score for h in results)
            score_range = max_score - min_score if max_score != min_score else 1.0

            for hit in results:
                normalized = (hit.score - min_score) / score_range
                weighted_score = normalized * weight

                if hit.id in score_map:
                    prev_score, prev_hit = score_map[hit.id]
                    new_score = prev_score + weighted_score
                    if hit.score > prev_hit.score:
                        merged_meta = {**prev_hit.metadata, **hit.metadata}
                        best_hit = hit._replace(
                            score=round(new_score, 6),
                            source="hybrid",
                            metadata=merged_meta,
                        )
                    else:
                        best_hit = prev_hit._replace(
                            score=round(new_score, 6),
                            source="hybrid",
                        )
                    score_map[hit.id] = (new_score, best_hit)
                else:
                    new_hit = hit._replace(
                        score=round(weighted_score, 6),
                        source="hybrid",
                    )
                    score_map[hit.id] = (weighted_score, new_hit)

        fused = [hit for _, (_, hit) in score_map.items()]
        fused.sort(key=lambda h: h.score, reverse=True)
        return fused

    @staticmethod
    def _max_fusion(
        result_lists: list[list[SearchHit]],
    ) -> list[SearchHit]:
        """最大分数融合。

        对同一文档，取所有策略中的最高分数作为最终得分。

        Args:
            result_lists: 各策略返回的搜索结果列表。

        Returns:
            按最高得分降序排列的去重搜索结果列表。
        """
        score_map: dict[str, tuple[float, SearchHit]] = {}

        for results in result_lists:
            for hit in results:
                if hit.id in score_map:
                    prev_score, prev_hit = score_map[hit.id]
                    if hit.score > prev_score:
                        merged_meta = {**prev_hit.metadata, **hit.metadata}
                        best_hit = hit._replace(
                            score=hit.score,
                            source="hybrid",
                            metadata=merged_meta,
                        )
                        score_map[hit.id] = (hit.score, best_hit)
                else:
                    new_hit = hit._replace(source="hybrid")
                    score_map[hit.id] = (hit.score, new_hit)

        fused = [hit for _, (_, hit) in score_map.items()]
        fused.sort(key=lambda h: h.score, reverse=True)
        return fused

    # ------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------

    def get_strategy_names(self) -> list[str]:
        """获取所有已注册策略的名称列表。

        Returns:
            策略名称列表。
        """
        return [s.name for s, _ in self._strategies]

    def set_fusion_method(self, method: str) -> None:
        """动态切换融合方法。

        Args:
            method: 新的融合方法，可选 ``"rrf"``、``"weighted"``、``"max"``。

        Raises:
            ValueError: 如果方法名称不受支持。
        """
        if method not in self._SUPPORTED_FUSION_METHODS:
            raise ValueError(
                f"不支持的融合方法 '{method}'，"
                f"可选: {sorted(self._SUPPORTED_FUSION_METHODS)}"
            )
        old_method = self._fusion_method
        self._fusion_method = method
        logger.info("融合方法已从 '%s' 切换为 '%s'", old_method, method)

    def __repr__(self) -> str:
        strategies_desc = ", ".join(
            f"{s.name}(w={w:.1f})" for s, w in self._strategies
        )
        return (
            f"HybridSearchEngine(fusion='{self._fusion_method}', "
            f"strategies=[{strategies_desc}])"
        )
