"""
记忆重要性衰减引擎 v1.0

创新点：
- 动态衰减：记忆的 effective_importance 随时间自动降低
- 多因子衰减：时间衰减 + 访问频率加成 + 语义关联加成
- 可插拔衰减曲线：指数衰减、线性衰减、阶梯衰减
- 定期刷新：后台线程定期更新所有记忆的有效重要性
- 容量感知：当记忆数接近上限时加速衰减低价值记忆

与现有系统的区别：
- ImportanceScorer 是"按需计算"的评分器，不修改原始数据
- MemoryDecayEngine 是"主动更新"的衰减器，定期刷新 effective_importance
- 两者互补：DecayEngine 维护动态重要性，Scorer 提供即时评分
"""

from __future__ import annotations

import math
import time
import threading
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class DecayCurve(Enum):
    """衰减曲线类型。"""
    EXPONENTIAL = "exponential"    # 指数衰减: 2^(-age/half_life)
    LINEAR = "linear"              # 线性衰减: max(0, 1 - age/max_age)
    STEP = "step"                  # 阶梯衰减: 按固定时间间隔降低
    LOGARITHMIC = "logarithmic"    # 对数衰减: 1 / (1 + ln(1 + age/scale))


@dataclass
class DecayConfig:
    """衰减引擎配置。

    Attributes:
        enabled: 是否启用衰减引擎
        curve: 衰减曲线类型
        half_life: 指数衰减半衰期（秒），默认7天
        max_age: 线性衰减最大年龄（秒），默认30天
        step_interval: 阶梯衰减间隔（秒），默认1天
        step_decay: 阶梯衰减每步降低量，默认0.1
        log_scale: 对数衰减时间尺度（秒），默认1天
        access_boost: 每次访问恢复的重要性，默认0.05
        access_decay_cap: 访问加成上限，默认0.3
        min_importance: 最低有效重要性，默认0.01
        refresh_interval: 刷新间隔（秒），默认300秒（5分钟）
        importance_threshold: 低于此值的记忆标记为可驱逐，默认0.05
        capacity_limit: 触发加速衰减的记忆数上限，0表示无限制
        on_decay_callback: 衰减回调函数 (memory_id, old_importance, new_importance)
    """
    enabled: bool = True
    curve: DecayCurve = DecayCurve.EXPONENTIAL
    half_life: float = 604800.0        # 7天
    max_age: float = 2592000.0         # 30天
    step_interval: float = 86400.0     # 1天
    step_decay: float = 0.1
    log_scale: float = 86400.0         # 1天
    access_boost: float = 0.05
    access_decay_cap: float = 0.3
    min_importance: float = 0.01
    refresh_interval: float = 300.0    # 5分钟
    importance_threshold: float = 0.05
    capacity_limit: int = 0
    on_decay_callback: Optional[Callable] = None


@dataclass
class MemoryDecayState:
    """单条记忆的衰减状态。"""
    memory_id: str
    base_importance: float              # 原始重要性（用户设定的）
    effective_importance: float         # 当前有效重要性（衰减后的）
    last_access_time: float             # 最后访问时间
    access_count_since_decay: int = 0   # 自上次衰减以来的访问次数
    created_at: float = field(default_factory=time.time)
    last_decay_time: float = field(default_factory=time.time)


class MemoryDecayEngine:
    """记忆重要性衰减引擎。

    定期计算每条记忆的有效重要性（effective_importance），
    结合时间衰减和访问频率加成，实现动态重要性管理。

    Usage::

        engine = MemoryDecayEngine(config)
        engine.register("mem_1", base_importance=0.8)
        engine.record_access("mem_1")

        # 获取当前有效重要性
        effective = engine.get_effective_importance("mem_1")

        # 获取可驱逐的记忆列表
        evictable = engine.get_evictable_memories()

        # 启动后台刷新
        engine.start()
    """

    def __init__(self, config: Optional[DecayConfig] = None) -> None:
        self._config = config or DecayConfig()
        self._states: dict[str, MemoryDecayState] = {}
        self._lock = threading.RLock()
        self._refresh_thread: Optional[threading.Thread] = None
        self._running = False
        self._total_decays = 0
        self._total_access_boosts = 0

    # ==================== 注册与查询 ====================

    def register(
        self,
        memory_id: str,
        base_importance: float = 0.5,
        created_at: Optional[float] = None,
    ) -> None:
        """注册一条记忆到衰减引擎。

        Args:
            memory_id: 记忆ID
            base_importance: 基础重要性 [0.0, 1.0]
            created_at: 创建时间（Unix时间戳）
        """
        if not self._config.enabled:
            return
        with self._lock:
            self._states[memory_id] = MemoryDecayState(
                memory_id=memory_id,
                base_importance=base_importance,
                effective_importance=base_importance,
                last_access_time=time.time(),
                created_at=created_at or time.time(),
                last_decay_time=time.time(),
            )

    def unregister(self, memory_id: str) -> None:
        """取消注册一条记忆。"""
        with self._lock:
            self._states.pop(memory_id, None)

    def record_access(self, memory_id: str) -> None:
        """记录一次访问，提升记忆的有效重要性。

        Args:
            memory_id: 记忆ID
        """
        if not self._config.enabled:
            return
        with self._lock:
            state = self._states.get(memory_id)
            if state is not None:
                state.last_access_time = time.time()
                state.access_count_since_decay += 1
                self._total_access_boosts += 1

    def get_effective_importance(self, memory_id: str) -> float:
        """获取记忆的当前有效重要性。

        Args:
            memory_id: 记忆ID

        Returns:
            有效重要性 [0.0, 1.0]，未注册时返回 0.0
        """
        with self._lock:
            state = self._states.get(memory_id)
            if state is None:
                return 0.0
            return self._compute_effective(state)

    def get_evictable_memories(self, limit: int = 10) -> list[tuple[str, float]]:
        """获取可驱逐的记忆列表（按有效重要性升序）。

        Args:
            limit: 最大返回数量

        Returns:
            [(memory_id, effective_importance), ...] 列表
        """
        if not self._config.enabled:
            return []
        with self._lock:
            self._refresh_all_states()
            candidates = [
                (mid, state.effective_importance)
                for mid, state in self._states.items()
                if state.effective_importance <= self._config.importance_threshold
            ]
            candidates.sort(key=lambda x: x[1])
            return candidates[:limit]

    def get_all_effective_importances(self) -> dict[str, float]:
        """获取所有记忆的有效重要性。

        Returns:
            {memory_id: effective_importance, ...}
        """
        with self._lock:
            self._refresh_all_states()
            return {
                mid: state.effective_importance
                for mid, state in self._states.items()
            }

    def get_stats(self) -> dict:
        """获取衰减引擎统计信息。

        Returns:
            统计信息字典
        """
        with self._lock:
            states = list(self._states.values())
            if not states:
                return {
                    "registered_count": 0,
                    "avg_effective": 0.0,
                    "min_effective": 0.0,
                    "max_effective": 0.0,
                    "evictable_count": 0,
                    "total_decays": self._total_decays,
                    "total_access_boosts": self._total_access_boosts,
                }

            effective_values = [s.effective_importance for s in states]
            evictable = sum(
                1 for v in effective_values
                if v <= self._config.importance_threshold
            )

            return {
                "registered_count": len(states),
                "avg_effective": sum(effective_values) / len(effective_values),
                "min_effective": min(effective_values),
                "max_effective": max(effective_values),
                "evictable_count": evictable,
                "total_decays": self._total_decays,
                "total_access_boosts": self._total_access_boosts,
            }

    # ==================== 衰减计算 ====================

    def _compute_effective(self, state: MemoryDecayState) -> float:
        """计算单条记忆的有效重要性。

        公式: effective = base * time_decay + access_boost

        其中:
        - time_decay: 根据配置的衰减曲线计算
        - access_boost: 基于自上次衰减以来的访问次数，有上限
        """
        config = self._config
        now = time.time()
        age = now - state.created_at

        # 1. 时间衰减因子
        time_decay = self._compute_time_decay(age)

        # 2. 访问加成
        access_boost = min(
            state.access_count_since_decay * config.access_boost,
            config.access_decay_cap,
        )

        # 3. 容量压力加速衰减
        capacity_factor = 1.0
        if config.capacity_limit > 0 and len(self._states) > config.capacity_limit:
            overflow_ratio = len(self._states) / config.capacity_limit
            capacity_factor = 1.0 / math.sqrt(overflow_ratio)

        # 4. 计算有效重要性
        effective = state.base_importance * time_decay * capacity_factor + access_boost
        effective = max(config.min_importance, min(1.0, effective))

        return effective

    def _compute_time_decay(self, age: float) -> float:
        """根据配置的衰减曲线计算时间衰减因子。"""
        config = self._config
        curve = config.curve

        if curve == DecayCurve.EXPONENTIAL:
            if age <= 0:
                return 1.0
            return math.pow(2, -age / config.half_life)

        elif curve == DecayCurve.LINEAR:
            if age <= 0:
                return 1.0
            return max(0.0, 1.0 - age / config.max_age)

        elif curve == DecayCurve.STEP:
            if age <= 0:
                return 1.0
            steps = int(age / config.step_interval)
            return max(0.0, 1.0 - steps * config.step_decay)

        elif curve == DecayCurve.LOGARITHMIC:
            if age <= 0:
                return 1.0
            return 1.0 / (1.0 + math.log(1.0 + age / config.log_scale))

        return 1.0

    # ==================== 后台刷新 ====================

    def _refresh_all_states(self) -> None:
        """刷新所有记忆的有效重要性。"""
        now = time.time()
        for state in self._states.values():
            old_effective = state.effective_importance
            new_effective = self._compute_effective(state)
            state.effective_importance = new_effective
            state.last_decay_time = now
            state.access_count_since_decay = 0  # 重置访问计数

            if abs(old_effective - new_effective) > 0.001:
                self._total_decays += 1
                if self._config.on_decay_callback:
                    try:
                        self._config.on_decay_callback(
                            state.memory_id, old_effective, new_effective
                        )
                    except Exception:
                        logger.debug(
                            "Decay callback failed for %s",
                            state.memory_id,
                            exc_info=True,
                        )

    def _refresh_loop(self) -> None:
        """后台刷新循环。"""
        while self._running:
            try:
                time.sleep(self._config.refresh_interval)
                if not self._running:
                    break
                with self._lock:
                    self._refresh_all_states()
            except Exception:
                logger.debug("Decay engine refresh error", exc_info=True)

    def start(self) -> None:
        """启动后台衰减刷新线程。"""
        if not self._config.enabled:
            return
        with self._lock:
            if self._running:
                return
            self._running = True
            self._refresh_thread = threading.Thread(
                target=self._refresh_loop,
                daemon=True,
                name="memory-decay-engine",
            )
            self._refresh_thread.start()
            logger.info("MemoryDecayEngine started (interval=%.0fs)", self._config.refresh_interval)

    def stop(self) -> None:
        """停止后台衰减刷新线程。"""
        with self._lock:
            self._running = False
        if self._refresh_thread is not None:
            self._refresh_thread.join(timeout=10)
            self._refresh_thread = None
            logger.info("MemoryDecayEngine stopped")

    def refresh_once(self) -> dict:
        """手动触发一次刷新（用于测试或按需更新）。

        Returns:
            刷新后的统计信息
        """
        with self._lock:
            self._refresh_all_states()
        return self.get_stats()

    @property
    def is_running(self) -> bool:
        """是否正在运行。"""
        return self._running

    @property
    def registered_count(self) -> int:
        """已注册的记忆数量。"""
        return len(self._states)
