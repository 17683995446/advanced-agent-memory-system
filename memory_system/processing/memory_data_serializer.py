"""
序列化器 - 记忆数据的导入导出

支持 JSON/YAML 格式的序列化和反序列化，
用于数据迁移、备份和跨系统交换。

依赖: PyYAML (可选)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import yaml
    _yaml_available = True
except ImportError:
    _yaml_available = False
    yaml = None


class ExportFormat(Enum):
    """导出格式"""
    JSON = "json"
    YAML = "yaml"


class MemorySerializer:
    """
    记忆序列化器
    
    支持将记忆数据导出为 JSON/YAML 格式，以及从这些格式导入。
    
    Example:
        serializer = MemorySerializer()
        
        # 导出
        data = [
            {"id": "1", "content": "Hello", "embedding": [0.1, 0.2]},
            {"id": "2", "content": "World", "embedding": [0.3, 0.4]},
        ]
        
        json_bytes = serializer.export(data, format=ExportFormat.JSON)
        yaml_str = serializer.export(data, format=ExportFormat.YAML)
        
        # 导入
        records = serializer.import_data(json_bytes, format=ExportFormat.JSON)
    """
    
    def __init__(self, include_embeddings: bool = True, include_metadata: bool = True):
        """
        Args:
            include_embeddings: 导出时是否包含向量
            include_metadata: 导出时是否包含元数据
        """
        self._include_embeddings = include_embeddings
        self._include_metadata = include_metadata
    
    def export(
        self,
        records: list[dict],
        format: ExportFormat = ExportFormat.JSON,
        pretty: bool = True,
    ) -> str:
        """
        导出记忆数据
        
        Args:
            records: 记录列表
            format: 导出格式
            pretty: 是否美化输出
            
        Returns:
            序列化后的字符串
        """
        # 准备导出数据
        export_data = {
            "version": "3.0",
            "exported_at": time.time(),
            "record_count": len(records),
            "records": self._prepare_records(records),
        }
        
        if format == ExportFormat.JSON:
            indent = 2 if pretty else None
            return json.dumps(export_data, indent=indent, ensure_ascii=False, default=str)
        
        elif format == ExportFormat.YAML:
            if not _yaml_available:
                raise ImportError("PyYAML is required for YAML export. Install with: pip install pyyaml")
            return yaml.dump(export_data, allow_unicode=True, default_flow_style=False)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def export_to_file(
        self,
        records: list[dict],
        filepath: str,
        format: Optional[ExportFormat] = None,
    ) -> None:
        """
        导出记忆数据到文件
        
        Args:
            records: 记录列表
            filepath: 文件路径
            format: 导出格式（自动从扩展名推断）
        """
        if format is None:
            if filepath.endswith(".yaml") or filepath.endswith(".yml"):
                format = ExportFormat.YAML
            else:
                format = ExportFormat.JSON
        
        data = self.export(records, format=format)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(data)
        
        logger.info("Exported %d records to %s", len(records), filepath)
    
    def import_data(
        self,
        data: str,
        format: ExportFormat = ExportFormat.JSON,
    ) -> list[dict]:
        """
        导入记忆数据
        
        Args:
            data: 序列化数据字符串
            format: 数据格式
            
        Returns:
            记录列表
        """
        if format == ExportFormat.JSON:
            parsed = json.loads(data)
        elif format == ExportFormat.YAML:
            if not _yaml_available:
                raise ImportError("PyYAML is required for YAML import")
            parsed = yaml.safe_load(data)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # 验证格式
        if not isinstance(parsed, dict) or "records" not in parsed:
            raise ValueError("Invalid import data: missing 'records' field")
        
        records = parsed["records"]
        if not isinstance(records, list):
            raise ValueError("Invalid import data: 'records' must be a list")
        
        # 规范化记录
        normalized = []
        for record in records:
            normalized.append(self._normalize_record(record))
        
        logger.info("Imported %d records (version=%s)", len(normalized), parsed.get("version", "unknown"))
        return normalized
    
    def import_from_file(self, filepath: str) -> list[dict]:
        """
        从文件导入记忆数据
        
        Args:
            filepath: 文件路径
            
        Returns:
            记录列表
        """
        if filepath.endswith(".yaml") or filepath.endswith(".yml"):
            format = ExportFormat.YAML
        else:
            format = ExportFormat.JSON
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = f.read()
        
        return self.import_data(data, format=format)
    
    def _prepare_records(self, records: list[dict]) -> list[dict]:
        """准备导出记录"""
        prepared = []
        for record in records:
            r = dict(record)
            
            # 移除不需要的字段
            if not self._include_embeddings and "embedding" in r:
                r.pop("embedding", None)
            if not self._include_metadata and "metadata" in r:
                r.pop("metadata", None)
            
            prepared.append(r)
        
        return prepared
    
    def _normalize_record(self, record: dict) -> dict:
        """规范化导入的记录"""
        normalized = {
            "id": record.get("id", str(uuid.uuid4())),
            "content": record.get("content", ""),
            "memory_type": record.get("memory_type", "semantic"),
            "category": record.get("category", "general"),
            "importance": record.get("importance", 0.5),
            "tags": record.get("tags", []),
            "metadata": record.get("metadata", {}),
            "timestamp": record.get("timestamp", time.time()),
            "access_count": record.get("access_count", 0),
        }
        
        # 可选字段
        if "embedding" in record:
            normalized["embedding"] = record["embedding"]
        
        return normalized
    
    def validate(self, data: str, format: ExportFormat = ExportFormat.JSON) -> tuple[bool, str]:
        """
        验证导入数据格式
        
        Returns:
            (是否有效, 错误信息)
        """
        try:
            records = self.import_data(data, format=format)
            return True, f"Valid: {len(records)} records"
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            return False, str(e)


__all__ = [
    "MemorySerializer",
    "ExportFormat",
]
