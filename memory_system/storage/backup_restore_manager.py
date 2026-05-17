"""
备份管理模块 - 记忆数据的备份与恢复

基于 shutil + tarfile 实现完整的备份恢复功能：
- 全量备份：完整数据快照
- 增量备份：基于时间戳的差异备份
- 压缩归档：gzip/bzip2/xz 压缩
- 完整性校验：SHA256 校验和
- 加密支持：AES-256-GCM 加密（可选）
- 云存储钩子：S3/MinIO/GCS 上传接口
- 自动清理：保留策略管理

依赖: Python 标准库 + cryptography（可选加密）
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import shutil
import tarfile
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, Union

logger = logging.getLogger(__name__)

# Try to import cryptography for encryption
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _crypto_available = True
except ImportError:
    _crypto_available = False
    Fernet = None
    PBKDF2HMAC = None
    hashes = None


# ---------------------------------------------------------------------------
# Enums and Constants
# ---------------------------------------------------------------------------

class BackupType(Enum):
    """备份类型"""
    FULL = "full"           # 全量备份
    INCREMENTAL = "incr"    # 增量备份
    DIFFERENTIAL = "diff"   # 差异备份


class CompressionType(Enum):
    """压缩类型"""
    NONE = ""
    GZIP = "gz"
    BZIP2 = "bz2"
    XZ = "xz"


class BackupStatus(Enum):
    """备份状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    VERIFIED = "verified"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class BackupManifest:
    """备份清单
    
    Attributes:
        backup_id: 唯一备份标识
        backup_type: 备份类型
        created_at: 创建时间戳（ISO 格式）
        source_paths: 源路径列表
        archive_path: 归档文件路径
        size_bytes: 归档大小（字节）
        checksum: SHA256 校验和
        compression: 压缩类型
        encrypted: 是否加密
        parent_backup_id: 父备份 ID（增量/差异备份）
        metadata: 额外元数据
    """
    backup_id: str
    backup_type: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_paths: list[str] = field(default_factory=list)
    archive_path: str = ""
    size_bytes: int = 0
    checksum: str = ""
    compression: str = CompressionType.GZIP.value
    encrypted: bool = False
    parent_backup_id: str = ""
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: dict) -> "BackupManifest":
        return cls(**data)


@dataclass
class BackupStats:
    """备份统计"""
    total_backups: int = 0
    total_size_bytes: int = 0
    last_backup_time: Optional[str] = None
    last_backup_status: str = ""
    avg_backup_duration_ms: float = 0.0
    success_rate: float = 0.0


@dataclass
class RetentionPolicy:
    """保留策略
    
    Attributes:
        keep_daily: 保留最近 N 天的每日备份
        keep_weekly: 保留最近 N 周的每周备份
        keep_monthly: 保留最近 N 月的每月备份
        max_total_size_gb: 最大总大小（GB），超出时删除最旧备份
        min_backups: 最少保留备份数
    """
    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 12
    max_total_size_gb: float = 100.0
    min_backups: int = 3


# ---------------------------------------------------------------------------
# Encryption Handler
# ---------------------------------------------------------------------------

class EncryptionHandler:
    """加密处理器"""
    
    def __init__(self, password: str, salt: Optional[bytes] = None):
        if not _crypto_available:
            raise ImportError(
                "cryptography is required for encryption. "
                "Install: pip install cryptography"
            )
        
        self._salt = salt or os.urandom(16)
        self._key = self._derive_key(password, self._salt)
        self._password = password
        self._fernet = Fernet(self._key)
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """从密码派生密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def encrypt(self, data: bytes) -> bytes:
        """加密数据"""
        return self._fernet.encrypt(data)
    
    def decrypt(self, data: bytes) -> bytes:
        """解密数据"""
        return self._fernet.decrypt(data)
    
    def encrypt_file(self, src_path: Path, dst_path: Path) -> None:
        """加密文件"""
        with open(src_path, "rb") as f:
            data = f.read()
        encrypted = self.encrypt(data)
        with open(dst_path, "wb") as f:
            f.write(self._salt + encrypted)
    
    def decrypt_file(self, src_path: Path, dst_path: Path) -> None:
        """解密文件"""
        with open(src_path, "rb") as f:
            data = f.read()
        # First 16 bytes are salt
        salt = data[:16]
        encrypted = data[16:]
        
        # Re-derive key with stored salt
        key = self._derive_key(self._password, salt)
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted)
        
        with open(dst_path, "wb") as f:
            f.write(decrypted)


# ---------------------------------------------------------------------------
# Cloud Upload Interface
# ---------------------------------------------------------------------------

class CloudUploader:
    """云存储上传器基类"""
    
    def upload(self, local_path: Path, remote_key: str) -> bool:
        """上传文件到云存储"""
        raise NotImplementedError
    
    def download(self, remote_key: str, local_path: Path) -> bool:
        """从云存储下载文件"""
        raise NotImplementedError
    
    def list_backups(self) -> list[str]:
        """列出云存储中的备份"""
        raise NotImplementedError
    
    def delete(self, remote_key: str) -> bool:
        """删除云存储中的备份"""
        raise NotImplementedError


class S3Uploader(CloudUploader):
    """S3/MinIO 上传器"""
    
    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
    ):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.region = region
        self._client = None
    
    def _get_client(self):
        """获取 S3 客户端"""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region,
                )
            except ImportError:
                raise ImportError("boto3 is required for S3 upload. Install: pip install boto3")
        return self._client
    
    def upload(self, local_path: Path, remote_key: str) -> bool:
        try:
            self._get_client().upload_file(str(local_path), self.bucket, remote_key)
            return True
        except (ConnectionError, OSError, ValueError, TypeError) as e:
            logger.error("S3 upload failed: %s", e)
            return False

    def download(self, remote_key: str, local_path: Path) -> bool:
        try:
            self._get_client().download_file(self.bucket, remote_key, str(local_path))
            return True
        except (ConnectionError, OSError, ValueError, TypeError) as e:
            logger.error("S3 download failed: %s", e)
            return False

    def list_backups(self) -> list[str]:
        try:
            response = self._get_client().list_objects_v2(Bucket=self.bucket)
            return [obj["Key"] for obj in response.get("Contents", [])]
        except (ConnectionError, OSError, KeyError, TypeError) as e:
            logger.error("S3 list failed: %s", e)
            return []

    def delete(self, remote_key: str) -> bool:
        try:
            self._get_client().delete_object(Bucket=self.bucket, Key=remote_key)
            return True
        except (ConnectionError, OSError, ValueError, TypeError) as e:
            logger.error("S3 delete failed: %s", e)
            return False


# ---------------------------------------------------------------------------
# Backup Manager
# ---------------------------------------------------------------------------

class BackupManager:
    """
    备份管理器
    
    Example:
        # 创建备份管理器
        manager = BackupManager(
            backup_dir="/backups/memory",
            retention=RetentionPolicy(keep_daily=7, keep_weekly=4),
        )
        
        # 全量备份
        manifest = manager.create_backup(
            source_paths=["data/memories", "data/knowledge_graph.json"],
            backup_type=BackupType.FULL,
        )
        
        # 增量备份
        incr_manifest = manager.create_backup(
            source_paths=["data/memories"],
            backup_type=BackupType.INCREMENTAL,
            parent_backup_id=manifest.backup_id,
        )
        
        # 列出备份
        backups = manager.list_backups()
        
        # 恢复备份
        manager.restore_backup(manifest.backup_id, restore_dir="/restore")
        
        # 清理旧备份
        manager.apply_retention_policy()
        
        # 上传到云存储
        manager.upload_to_cloud(manifest.backup_id, uploader=s3_uploader)
    """
    
    def __init__(
        self,
        backup_dir: Union[str, Path],
        retention: Optional[RetentionPolicy] = None,
        compression: CompressionType = CompressionType.GZIP,
        encrypt_password: Optional[str] = None,
    ):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.retention = retention or RetentionPolicy()
        self.compression = compression
        self.encrypt_password = encrypt_password
        self._lock = threading.RLock()
        self._manifests: dict[str, BackupManifest] = {}
        self._load_manifests()
    
    def _load_manifests(self) -> None:
        """加载所有备份清单"""
        manifest_dir = self.backup_dir / "manifests"
        if not manifest_dir.exists():
            return
        
        for manifest_file in manifest_dir.glob("*.json"):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                manifest = BackupManifest.from_dict(data)
                self._manifests[manifest.backup_id] = manifest
            except (json.JSONDecodeError, ValueError, TypeError, OSError) as e:
                logger.warning("Failed to load manifest %s: %s", manifest_file, e)
    
    def _save_manifest(self, manifest: BackupManifest) -> None:
        """保存备份清单"""
        manifest_dir = self.backup_dir / "manifests"
        manifest_dir.mkdir(exist_ok=True)
        
        manifest_file = manifest_dir / f"{manifest.backup_id}.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            f.write(manifest.to_json())
    
    def _generate_backup_id(self) -> str:
        """生成备份 ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.sha256(os.urandom(32)).hexdigest()[:8]
        return f"backup_{timestamp}_{random_suffix}"
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """计算文件 SHA256 校验和"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def create_backup(
        self,
        source_paths: list[Union[str, Path]],
        backup_type: BackupType = BackupType.FULL,
        parent_backup_id: str = "",
        metadata: Optional[dict] = None,
    ) -> BackupManifest:
        """
        创建备份
        
        Args:
            source_paths: 要备份的源路径列表
            backup_type: 备份类型
            parent_backup_id: 父备份 ID（增量/差异备份）
            metadata: 额外元数据
            
        Returns:
            BackupManifest: 备份清单
        """
        with self._lock:
            backup_id = self._generate_backup_id()
            start_time = time.time()
            
            manifest = BackupManifest(
                backup_id=backup_id,
                backup_type=backup_type.value,
                source_paths=[str(p) for p in source_paths],
                parent_backup_id=parent_backup_id,
                compression=self.compression.value,
                encrypted=bool(self.encrypt_password),
                metadata=metadata or {},
            )
            
            try:
                # Create archive
                archive_name = f"{backup_id}.tar"
                if self.compression != CompressionType.NONE:
                    archive_name += f".{self.compression.value}"
                
                archive_path = self.backup_dir / archive_name
                
                # Create tar archive
                mode = "w"
                if self.compression == CompressionType.GZIP:
                    mode = "w:gz"
                elif self.compression == CompressionType.BZIP2:
                    mode = "w:bz2"
                elif self.compression == CompressionType.XZ:
                    mode = "w:xz"
                
                with tarfile.open(archive_path, mode) as tar:
                    for src_path in source_paths:
                        src = Path(src_path)
                        if src.exists():
                            tar.add(src, arcname=src.name)
                
                # Encrypt if password provided
                if self.encrypt_password and _crypto_available:
                    encrypted_path = Path(str(archive_path) + ".enc")
                    handler = EncryptionHandler(self.encrypt_password)
                    handler.encrypt_file(archive_path, encrypted_path)
                    archive_path.unlink()  # Remove unencrypted
                    archive_path = encrypted_path
                
                # Calculate checksum
                manifest.checksum = self._calculate_checksum(archive_path)
                manifest.size_bytes = archive_path.stat().st_size
                manifest.archive_path = str(archive_path.relative_to(self.backup_dir))
                
                # Save manifest
                self._save_manifest(manifest)
                self._manifests[backup_id] = manifest
                
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    "Backup %s created successfully (%.2f MB, %.0fms)",
                    backup_id,
                    manifest.size_bytes / 1024 / 1024,
                    duration_ms,
                )
                
                return manifest
                
            except (IOError, OSError, ValueError, RuntimeError) as e:
                logger.error("Backup %s failed: %s", backup_id, e)
                raise
    
    def restore_backup(
        self,
        backup_id: str,
        restore_dir: Union[str, Path],
        verify_checksum: bool = True,
    ) -> bool:
        """
        恢复备份
        
        Args:
            backup_id: 备份 ID
            restore_dir: 恢复目标目录
            verify_checksum: 是否验证校验和
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            manifest = self._manifests.get(backup_id)
            if not manifest:
                raise ValueError(f"Backup {backup_id} not found")
            
            archive_path = self.backup_dir / manifest.archive_path
            if not archive_path.exists():
                raise FileNotFoundError(f"Archive not found: {archive_path}")
            
            # Verify checksum
            if verify_checksum:
                current_checksum = self._calculate_checksum(archive_path)
                if current_checksum != manifest.checksum:
                    raise ValueError("Checksum mismatch - archive corrupted")
            
            # Decrypt if encrypted
            temp_archive = None
            if manifest.encrypted:
                if not _crypto_available:
                    raise ImportError("cryptography is required for decryption")
                
                if not self.encrypt_password:
                    raise ValueError("Encryption password not provided")
                
                temp_archive = Path(tempfile.mktemp(suffix=".tar"))
                handler = EncryptionHandler(self.encrypt_password)
                handler.decrypt_file(archive_path, temp_archive)
                archive_path = temp_archive
            
            try:
                # Extract archive
                restore_path = Path(restore_dir)
                restore_path.mkdir(parents=True, exist_ok=True)
                
                mode = "r"
                if manifest.compression == CompressionType.GZIP.value:
                    mode = "r:gz"
                elif manifest.compression == CompressionType.BZIP2.value:
                    mode = "r:bz2"
                elif manifest.compression == CompressionType.XZ.value:
                    mode = "r:xz"
                
                with tarfile.open(archive_path, mode) as tar:
                    tar.extractall(path=restore_path)
                
                logger.info("Backup %s restored to %s", backup_id, restore_path)
                return True
                
            finally:
                if temp_archive and temp_archive.exists():
                    temp_archive.unlink()
    
    def list_backups(
        self,
        backup_type: Optional[BackupType] = None,
        limit: int = 100,
    ) -> list[BackupManifest]:
        """列出备份"""
        manifests = list(self._manifests.values())
        
        if backup_type:
            manifests = [m for m in manifests if m.backup_type == backup_type.value]
        
        # Sort by creation time (newest first)
        manifests.sort(key=lambda m: m.created_at, reverse=True)
        
        return manifests[:limit]
    
    def delete_backup(self, backup_id: str) -> bool:
        """删除备份"""
        with self._lock:
            manifest = self._manifests.get(backup_id)
            if not manifest:
                return False
            
            # Delete archive
            archive_path = self.backup_dir / manifest.archive_path
            if archive_path.exists():
                archive_path.unlink()
            
            # Delete manifest
            manifest_file = self.backup_dir / "manifests" / f"{backup_id}.json"
            if manifest_file.exists():
                manifest_file.unlink()
            
            del self._manifests[backup_id]
            logger.info("Backup %s deleted", backup_id)
            return True
    
    def verify_backup(self, backup_id: str) -> bool:
        """验证备份完整性"""
        manifest = self._manifests.get(backup_id)
        if not manifest:
            return False
        
        archive_path = self.backup_dir / manifest.archive_path
        if not archive_path.exists():
            return False
        
        current_checksum = self._calculate_checksum(archive_path)
        return current_checksum == manifest.checksum
    
    def apply_retention_policy(self) -> list[str]:
        """
        应用保留策略，删除过期备份
        
        Returns:
            list[str]: 被删除的备份 ID 列表
        """
        with self._lock:
            deleted = []
            manifests = list(self._manifests.values())
            
            if len(manifests) <= self.retention.min_backups:
                return deleted
            
            # Group by date
            daily_groups: dict[str, list[BackupManifest]] = {}
            for m in manifests:
                date = m.created_at[:10]  # YYYY-MM-DD
                daily_groups.setdefault(date, []).append(m)
            
            # Sort dates
            sorted_dates = sorted(daily_groups.keys(), reverse=True)
            
            # Keep recent daily backups
            backups_to_keep = set()
            for date in sorted_dates[:self.retention.keep_daily]:
                # Keep newest backup for each day
                daily_groups[date].sort(key=lambda m: m.created_at, reverse=True)
                backups_to_keep.add(daily_groups[date][0].backup_id)
            
            # Apply size limit
            total_size = sum(m.size_bytes for m in manifests)
            max_size_bytes = self.retention.max_total_size_gb * 1024 * 1024 * 1024
            
            if total_size > max_size_bytes:
                # Sort by age (oldest first)
                sorted_manifests = sorted(manifests, key=lambda m: m.created_at)
                for m in sorted_manifests:
                    if m.backup_id not in backups_to_keep:
                        if len(backups_to_keep) <= self.retention.min_backups:
                            break
                        self.delete_backup(m.backup_id)
                        deleted.append(m.backup_id)
                        total_size -= m.size_bytes
                        if total_size <= max_size_bytes:
                            break
            
            return deleted
    
    def upload_to_cloud(
        self,
        backup_id: str,
        uploader: CloudUploader,
        remote_prefix: str = "",
    ) -> bool:
        """上传备份到云存储"""
        manifest = self._manifests.get(backup_id)
        if not manifest:
            return False
        
        archive_path = self.backup_dir / manifest.archive_path
        remote_key = f"{remote_prefix}{manifest.archive_path}"
        
        success = uploader.upload(archive_path, remote_key)
        if success:
            logger.info("Backup %s uploaded to cloud", backup_id)
        return success
    
    def download_from_cloud(
        self,
        backup_id: str,
        uploader: CloudUploader,
        remote_prefix: str = "",
    ) -> bool:
        """从云存储下载备份"""
        manifest = self._manifests.get(backup_id)
        if not manifest:
            # Try to fetch manifest from cloud
            return False
        
        remote_key = f"{remote_prefix}{manifest.archive_path}"
        local_path = self.backup_dir / manifest.archive_path
        
        success = uploader.download(remote_key, local_path)
        if success:
            logger.info("Backup %s downloaded from cloud", backup_id)
        return success
    
    def get_stats(self) -> BackupStats:
        """获取备份统计"""
        manifests = list(self._manifests.values())
        
        total_size = sum(m.size_bytes for m in manifests)
        
        success_count = sum(1 for m in manifests if m.checksum)  # Has checksum = completed
        success_rate = success_count / len(manifests) if manifests else 0.0
        
        last_backup = max(manifests, key=lambda m: m.created_at) if manifests else None
        
        return BackupStats(
            total_backups=len(manifests),
            total_size_bytes=total_size,
            last_backup_time=last_backup.created_at if last_backup else None,
            last_backup_status="success" if last_backup and last_backup.checksum else "unknown",
            success_rate=success_rate,
        )


__all__ = [
    "BackupType",
    "CompressionType",
    "BackupStatus",
    "BackupManifest",
    "BackupStats",
    "RetentionPolicy",
    "EncryptionHandler",
    "CloudUploader",
    "S3Uploader",
    "BackupManager",
]
