"""
记忆推理引擎

基于记忆知识进行逻辑推导和推理：
1. 规则推理 - 基于IF-THEN规则推导
2. 关联推理 - 基于知识图谱关系推导
3. 归纳推理 - 从具体案例归纳一般规律
4. 演绎推理 - 从一般规律推导具体结论
5. 类比推理 - 基于相似性进行类比

支持推理链追踪、置信度计算、反事实推理。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class InferenceType(Enum):
    """推理类型枚举"""
    RULE_BASED = "rule_based"          # 规则推理
    ASSOCIATIVE = "associative"        # 关联推理
    INDUCTIVE = "inductive"            # 归纳推理
    DEDUCTIVE = "deductive"            # 演绎推理
    ANALOGICAL = "analogical"          # 类比推理


@dataclass
class InferenceRule:
    """推理规则"""
    rule_id: str
    name: str
    premises: list[str]                # 前提条件（关键词列表）
    conclusion: str                    # 结论模板
    confidence: float = 1.0            # 规则置信度
    inference_type: InferenceType = InferenceType.RULE_BASED


@dataclass
class InferenceStep:
    """推理步骤"""
    step_number: int
    inference_type: InferenceType
    premises: list[str]                # 使用的记忆/事实
    conclusion: str                    # 推导结论
    confidence: float                  # 步骤置信度
    rule_used: Optional[str] = None    # 使用的规则ID


@dataclass
class InferenceResult:
    """推理结果"""
    query: str                         # 原始查询
    conclusion: Optional[str]          # 最终结论
    confidence: float                  # 总体置信度
    steps: list[InferenceStep]         # 推理链
    supporting_memories: list[str]     # 支持记忆ID列表
    inference_types_used: list[InferenceType]  # 使用的推理类型
    duration_ms: float                 # 推理耗时


@dataclass
class InferenceConfig:
    """推理引擎配置"""
    min_confidence_threshold: float = 0.6   # 最小置信度阈值
    max_inference_steps: int = 5            # 最大推理步数
    enable_rule_reasoning: bool = True      # 启用规则推理
    enable_associative_reasoning: bool = True  # 启用关联推理
    enable_analogical_reasoning: bool = True   # 启用类比推理


class MemoryInferenceEngine:
    """
    记忆推理引擎

    基于存储的记忆进行智能推理：
    1. 规则推理 - 匹配IF-THEN规则
    2. 关联推理 - 利用知识图谱关系
    3. 类比推理 - 基于相似案例推理
    4. 推理链追踪 - 记录完整推导过程
    5. 置信度传播 - 计算结论可信度

    Example:
        engine = MemoryInferenceEngine(config=InferenceConfig())
        result = engine.infer("为什么天空是蓝色的？", memory_system)
        # result.conclusion = "因为瑞利散射..."
        # result.steps = [推理步骤1, 推理步骤2, ...]
    """

    def __init__(self, config: Optional[InferenceConfig] = None):
        self.config = config or InferenceConfig()
        self._rules: list[InferenceRule] = []
        self._inference_history: list[InferenceResult] = []
        self._build_default_rules()

    def _build_default_rules(self) -> None:
        """构建默认推理规则"""
        default_rules = [
            InferenceRule(
                rule_id="r1",
                name="因果关系",
                premises=["原因", "导致"],
                conclusion="{cause} 导致 {effect}",
                confidence=0.9,
                inference_type=InferenceType.RULE_BASED,
            ),
            InferenceRule(
                rule_id="r2",
                name="属性继承",
                premises=["是", "的一种"],
                conclusion="{instance} 继承 {category} 的属性",
                confidence=0.85,
                inference_type=InferenceType.DEDUCTIVE,
            ),
            InferenceRule(
                rule_id="r3",
                name="条件推理",
                premises=["如果", "那么"],
                conclusion="当 {condition} 时，{result}",
                confidence=0.8,
                inference_type=InferenceType.RULE_BASED,
            ),
            InferenceRule(
                rule_id="r4",
                name="功能推理",
                premises=["用于", "可以"],
                conclusion="{tool} 可用于 {purpose}",
                confidence=0.85,
                inference_type=InferenceType.ASSOCIATIVE,
            ),
        ]
        self._rules.extend(default_rules)

    def add_rule(self, rule: InferenceRule) -> None:
        """添加自定义推理规则"""
        self._rules.append(rule)
        logger.debug("Added inference rule: %s", rule.name)

    def infer(
        self,
        query: str,
        memory_system: Any,
        context: Optional[dict[str, Any]] = None,
    ) -> InferenceResult:
        """
        执行推理

        Args:
            query: 查询问题
            memory_system: 记忆系统实例（用于检索相关记忆）
            context: 额外上下文

        Returns:
            InferenceResult 推理结果
        """
        import time
        start_time = time.time()

        steps: list[InferenceStep] = []
        supporting_memories: list[str] = []
        types_used: set[InferenceType] = set()
        current_confidence = 1.0

        # 步骤1: 检索相关记忆
        relevant_memories = self._retrieve_relevant_memories(query, memory_system)
        if not relevant_memories:
            return InferenceResult(
                query=query,
                conclusion=None,
                confidence=0.0,
                steps=[],
                supporting_memories=[],
                inference_types_used=[],
                duration_ms=(time.time() - start_time) * 1000,
            )

        supporting_memories = [m.get("id", "") for m in relevant_memories]

        # 步骤2: 尝试规则推理
        if self.config.enable_rule_reasoning:
            rule_result = self._apply_rule_reasoning(query, relevant_memories)
            if rule_result:
                step = InferenceStep(
                    step_number=len(steps) + 1,
                    inference_type=InferenceType.RULE_BASED,
                    premises=[m.get("content", "") for m in relevant_memories[:3]],
                    conclusion=rule_result["conclusion"],
                    confidence=rule_result["confidence"],
                    rule_used=rule_result.get("rule_id"),
                )
                steps.append(step)
                current_confidence *= rule_result["confidence"]
                types_used.add(InferenceType.RULE_BASED)

        # 步骤3: 尝试关联推理
        if self.config.enable_associative_reasoning and current_confidence >= self.config.min_confidence_threshold:
            assoc_result = self._apply_associative_reasoning(query, relevant_memories, memory_system)
            if assoc_result:
                step = InferenceStep(
                    step_number=len(steps) + 1,
                    inference_type=InferenceType.ASSOCIATIVE,
                    premises=assoc_result.get("premises", []),
                    conclusion=assoc_result["conclusion"],
                    confidence=assoc_result["confidence"],
                )
                steps.append(step)
                current_confidence *= assoc_result["confidence"]
                types_used.add(InferenceType.ASSOCIATIVE)

        # 步骤4: 尝试类比推理
        if self.config.enable_analogical_reasoning and current_confidence >= self.config.min_confidence_threshold:
            analog_result = self._apply_analogical_reasoning(query, relevant_memories)
            if analog_result:
                step = InferenceStep(
                    step_number=len(steps) + 1,
                    inference_type=InferenceType.ANALOGICAL,
                    premises=analog_result.get("premises", []),
                    conclusion=analog_result["conclusion"],
                    confidence=analog_result["confidence"],
                )
                steps.append(step)
                current_confidence *= analog_result["confidence"]
                types_used.add(InferenceType.ANALOGICAL)

        # 构建最终结论
        final_conclusion = None
        if steps:
            final_conclusion = steps[-1].conclusion

        result = InferenceResult(
            query=query,
            conclusion=final_conclusion,
            confidence=current_confidence,
            steps=steps,
            supporting_memories=supporting_memories,
            inference_types_used=list(types_used),
            duration_ms=(time.time() - start_time) * 1000,
        )

        self._inference_history.append(result)
        logger.info("Inference complete: query='%s...', steps=%d, confidence=%.2f",
                   query[:30], len(steps), current_confidence)

        return result

    def _retrieve_relevant_memories(self, query: str, memory_system: Any) -> list[dict]:
        """检索相关记忆"""
        try:
            # 使用记忆系统的recall功能
            if hasattr(memory_system, "recall"):
                results = memory_system.recall(query, top_k=10)
                # 标准化结果格式
                normalized = []
                for r in results:
                    if isinstance(r, dict):
                        normalized.append(r)
                    else:
                        normalized.append({"content": str(r), "id": str(id(r))})
                return normalized
        except Exception as e:
            logger.warning("Failed to retrieve memories: %s", e)
        return []

    def _apply_rule_reasoning(
        self,
        query: str,
        memories: list[dict],
    ) -> Optional[dict]:
        """应用规则推理"""
        query_lower = query.lower()
        memory_texts = [m.get("content", "").lower() for m in memories]

        for rule in self._rules:
            # 检查前提是否匹配
            all_premises_match = True
            matched_premises = []

            for premise in rule.premises:
                premise_found = False
                # 检查查询或记忆中是否包含前提
                if premise.lower() in query_lower:
                    premise_found = True
                    matched_premises.append(f"query:{premise}")
                else:
                    for i, mem_text in enumerate(memory_texts):
                        if premise.lower() in mem_text:
                            premise_found = True
                            matched_premises.append(f"memory{i}:{premise}")
                            break

                if not premise_found:
                    all_premises_match = False
                    break

            if all_premises_match:
                # 生成结论
                conclusion = self._generate_conclusion(rule.conclusion, query, memories)
                return {
                    "conclusion": conclusion,
                    "confidence": rule.confidence,
                    "rule_id": rule.rule_id,
                    "premises": matched_premises,
                }

        return None

    def _generate_conclusion(
        self,
        template: str,
        query: str,
        memories: list[dict],
    ) -> str:
        """根据模板生成结论"""
        # 简单模板替换
        conclusion = template

        # 尝试提取查询中的关键信息
        # 例如：从"为什么天空是蓝色的"提取"天空"和"蓝色"
        cause_match = re.search(r"为什么(.+?)是(.+?)[？?]", query)
        if cause_match:
            conclusion = conclusion.replace("{cause}", cause_match.group(1))
            conclusion = conclusion.replace("{effect}", cause_match.group(2))

        # 尝试从记忆中提取信息
        if memories:
            first_mem = memories[0].get("content", "")
            conclusion = conclusion.replace("{instance}", first_mem[:50])

        # 清理未替换的模板变量
        conclusion = re.sub(r"\{[^}]+\}", "某事物", conclusion)

        return conclusion

    def _apply_associative_reasoning(
        self,
        query: str,
        memories: list[dict],
        memory_system: Any,
    ) -> Optional[dict]:
        """应用关联推理（基于知识图谱）"""
        # 检查是否有知识图谱
        if not hasattr(memory_system, "knowledge_graph") or memory_system.knowledge_graph is None:
            return None

        try:
            # 从记忆中提取实体
            entities = self._extract_entities_from_memories(memories)
            if not entities:
                return None

            # 查找实体间的关系路径
            paths = []
            for i, e1 in enumerate(entities[:3]):
                for e2 in entities[i+1:4]:
                    if hasattr(memory_system.knowledge_graph, "find_path"):
                        path = memory_system.knowledge_graph.find_path(e1, e2)
                        if path:
                            paths.append((e1, e2, path))

            if paths:
                # 使用最短路径生成结论
                shortest = min(paths, key=lambda x: len(x[2]))
                e1, e2, path = shortest
                conclusion = f"{e1} 与 {e2} 通过 {' -> '.join(path)} 相关联"
                return {
                    "conclusion": conclusion,
                    "confidence": 0.75,
                    "premises": [f"实体:{e1}", f"实体:{e2}"],
                }
        except Exception as e:
            logger.debug("Associative reasoning failed: %s", e)

        return None

    def _extract_entities_from_memories(self, memories: list[dict]) -> list[str]:
        """从记忆中提取实体"""
        entities = []
        for mem in memories:
            content = mem.get("content", "")
            # 简单实体提取：大写单词或引号中的内容
            # 中文：提取名词（简化处理，提取2-4字词组）
            import re
            # 英文实体
            english_entities = re.findall(r"\b[A-Z][a-zA-Z]*\b", content)
            entities.extend(english_entities)

            # 中文实体（简单提取）
            chinese_entities = re.findall(r"[\u4e00-\u9fa5]{2,4}", content)
            entities.extend(chinese_entities[:3])  # 限制数量

        return list(set(entities))[:10]  # 去重并限制

    def _apply_analogical_reasoning(
        self,
        query: str,
        memories: list[dict],
    ) -> Optional[dict]:
        """应用类比推理"""
        if len(memories) < 2:
            return None

        # 查找相似案例
        query_keywords = set(self._extract_keywords(query))

        best_match = None
        best_score = 0.0

        for mem in memories:
            mem_text = mem.get("content", "")
            mem_keywords = set(self._extract_keywords(mem_text))

            # 计算相似度
            if query_keywords and mem_keywords:
                intersection = len(query_keywords & mem_keywords)
                union = len(query_keywords | mem_keywords)
                similarity = intersection / union if union > 0 else 0

                if similarity > best_score and similarity > 0.3:  # 相似度阈值
                    best_score = similarity
                    best_match = mem

        if best_match:
            conclusion = f"基于类似案例 '{best_match.get('content', '')[:50]}...'，可以推断"
            return {
                "conclusion": conclusion,
                "confidence": best_score * 0.9,  # 类比推理置信度略低
                "premises": [best_match.get("content", "")],
            }

        return None

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词"""
        import re
        # 简单关键词提取
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        # 过滤停用词
        stopwords = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her", "was", "one", "our", "out", "day", "get", "has", "him", "his", "how", "its", "may", "new", "now", "old", "see", "two", "who", "boy", "did", "she", "use", "her", "way", "many", "oil", "sit", "set", "run", "eat", "far", "sea", "eye", "ago", "off", "too", "any", "say", "man", "try", "ask", "end", "why", "let", "put", "say", "she", "try", "way", "own", "say", "too", "old", "tell", "very", "when", "much", "would", "there", "their", "what", "said", "each", "which", "will", "about", "could", "other", "after", "first", "never", "these", "think", "where", "being", "every", "great", "might", "shall", "still", "those", "while", "this", "that", "with", "have", "from", "they", "been", "were", "said", "time", "than", "them", "into", "just", "like", "over", "also", "back", "only", "know", "take", "year", "good", "some", "come", "make", "well", "work", "life", "even", "more", "want", "here", "look", "down", "most", "long", "last", "find", "give", "does", "made", "part", "such", "keep", "call", "came", "need", "feel", "seem", "turn", "hand", "high", "sure", "upon", "head", "help", "home", "side", "move", "both", "five", "once", "same", "must", "name", "left", "each", "done", "open", "case", "show", "live", "play", "went", "told", "seen", "hear", "talk", "soon", "read", "stop", "face", "fact", "land", "line", "kind", "next", "word", "came", "went", "told", "seen", "hear", "talk", "soon", "read", "stop", "face", "fact", "land", "line", "kind", "next", "word"}
        return [w for w in words if w not in stopwords]

    def explain_inference(self, result: InferenceResult) -> str:
        """生成推理过程的自然语言解释"""
        lines = [f"推理查询: {result.query}", ""]

        if not result.steps:
            lines.append("无法找到支持该结论的相关记忆或规则。")
            return "\n".join(lines)

        lines.append(f"推理过程（共{len(result.steps)}步，总体置信度: {result.confidence:.2f}）：")
        lines.append("")

        for step in result.steps:
            lines.append(f"步骤 {step.step_number}: {step.inference_type.value}")
            lines.append(f"  前提: {'; '.join(step.premises[:2])}...")
            lines.append(f"  结论: {step.conclusion}")
            lines.append(f"  置信度: {step.confidence:.2f}")
            if step.rule_used:
                lines.append(f"  使用规则: {step.rule_used}")
            lines.append("")

        lines.append(f"最终结论: {result.conclusion}")
        lines.append(f"支持记忆: {len(result.supporting_memories)} 条")

        return "\n".join(lines)

    def get_statistics(self) -> dict[str, Any]:
        """获取推理引擎统计信息"""
        if not self._inference_history:
            return {
                "total_inferences": 0,
                "avg_confidence": 0.0,
                "avg_steps": 0.0,
                "avg_duration_ms": 0.0,
            }

        total = len(self._inference_history)
        return {
            "total_inferences": total,
            "avg_confidence": sum(r.confidence for r in self._inference_history) / total,
            "avg_steps": sum(len(r.steps) for r in self._inference_history) / total,
            "avg_duration_ms": sum(r.duration_ms for r in self._inference_history) / total,
            "rules_count": len(self._rules),
            "inference_types_used": list(set(
                it for r in self._inference_history for it in r.inference_types_used
            )),
        }


__all__ = [
    "MemoryInferenceEngine",
    "InferenceConfig",
    "InferenceResult",
    "InferenceStep",
    "InferenceRule",
    "InferenceType",
]