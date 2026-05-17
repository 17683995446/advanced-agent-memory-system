"""
命令行工具模块 - Agent Memory System CLI

基于 argparse 实现完整的命令行接口：
- init: 初始化配置和数据目录
- backup: 创建备份
- restore: 恢复备份
- status: 查看系统状态
- config: 配置管理
- serve: 启动服务
- monitor: 监控命令
- interactive: 交互式模式

依赖: Python 标准库
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("memory_system.cli")


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------

class CLICommand:
    """CLI 命令基类"""
    
    name: str = ""
    description: str = ""
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """添加命令参数"""
        pass
    
    def execute(self, args: argparse.Namespace) -> int:
        """执行命令，返回退出码"""
        raise NotImplementedError


class InitCommand(CLICommand):
    """初始化命令"""
    
    name = "init"
    description = "Initialize memory system configuration and data directories"
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--data-dir",
            default="./data",
            help="Data directory path (default: ./data)",
        )
        parser.add_argument(
            "--config-file",
            default="./memory_config.yaml",
            help="Configuration file path (default: ./memory_config.yaml)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing configuration",
        )
    
    def execute(self, args: argparse.Namespace) -> int:
        data_dir = Path(args.data_dir)
        config_file = Path(args.config_file)
        
        # Create data directories
        dirs = [
            data_dir / "memories",
            data_dir / "backups",
            data_dir / "logs",
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {d}")
        
        # Create default config
        if config_file.exists() and not args.force:
            print(f"Configuration file already exists: {config_file}")
            print("Use --force to overwrite")
            return 1
        
        default_config = """# Agent Memory System Configuration

# Short-term memory settings
short_term:
  working_memory_capacity: 10
  default_ttl: 3600

# Long-term memory settings
long_term:
  embedding:
    provider: fake  # fake, sentence-transformers, openai
    fake_dimension: 384
  vector_store:
    backend: memory  # memory, chromadb, faiss, redis

# Structured storage
structured_store:
  db_path: ./data/memories.db

# Knowledge graph
knowledge_graph:
  auto_build: true
  max_entities: 10000

# Backup settings
backup:
  enabled: true
  directory: ./data/backups
  retention_days: 30

# Monitoring
monitoring:
  enabled: true
  interval_sec: 60
  alert_rules:
    - name: high_memory
      metric: memory_percent
      operator: ">"
      threshold: 80
      severity: warning
"""
        
        config_file.write_text(default_config)
        print(f"Created configuration file: {config_file}")
        
        print("\nInitialization complete!")
        print(f"Data directory: {data_dir.absolute()}")
        print(f"Config file: {config_file.absolute()}")
        return 0


class StatusCommand(CLICommand):
    """状态命令"""
    
    name = "status"
    description = "Show system status and statistics"
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format",
        )
        parser.add_argument(
            "--config",
            default="./memory_config.yaml",
            help="Configuration file path",
        )
    
    def execute(self, args: argparse.Namespace) -> int:
        try:
            from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig
            from memory_system.infra.dynamic_config_manager import create_config_manager
            
            # Load config
            config_path = Path(args.config)
            if config_path.exists():
                config_manager = create_config_manager(config_path=config_path)
                config = AgentMemoryConfig.model_validate(config_manager.as_dict())
            else:
                config = AgentMemoryConfig()
            
            # Create memory instance
            memory = AgentMemory(config=config)
            
            # Get stats
            stats = memory.get_stats()
            
            if args.format == "json":
                print(json.dumps(stats, indent=2, default=str))
            else:
                print("=" * 50)
                print("Agent Memory System Status")
                print("=" * 50)
                
                print("\n[Session]")
                session = stats.get("session", {})
                print(f"  Interaction count: {session.get('interaction_count', 0)}")
                
                print("\n[Working Memory]")
                working = stats.get("working_memory", {})
                print(f"  Current size: {working.get('current_size', 0)}")
                print(f"  Max capacity: {working.get('max_capacity', 0)}")
                
                print("\n[Knowledge Graph]")
                kg = stats.get("knowledge_graph", {})
                print(f"  Entity count: {kg.get('entity_count', 0)}")
                print(f"  Relation count: {kg.get('relation_count', 0)}")
                
                print("\n[Long-term Memory]")
                lt = stats.get("long_term", {})
                print(f"  Memory count: {lt.get('memory_count', 0)}")
                
                print("\n" + "=" * 50)
            
            memory.close()
            return 0
            
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            logger.error("Failed to get status: %s", e)
            return 1


class BackupCommand(CLICommand):
    """备份命令"""
    
    name = "backup"
    description = "Create a backup of memory data"
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--type",
            choices=["full", "incremental"],
            default="full",
            help="Backup type",
        )
        parser.add_argument(
            "--output",
            default="./data/backups",
            help="Backup output directory",
        )
        parser.add_argument(
            "--compress",
            choices=["gz", "bz2", "xz", "none"],
            default="gz",
            help="Compression type",
        )
        parser.add_argument(
            "--encrypt",
            action="store_true",
            help="Encrypt backup",
        )
        parser.add_argument(
            "--password",
            help="Encryption password",
        )
    
    def execute(self, args: argparse.Namespace) -> int:
        try:
            from memory_system.storage.backup_restore_manager import (
                BackupManager,
                BackupType,
                CompressionType,
            )
            
            # Determine compression
            compression_map = {
                "gz": CompressionType.GZIP,
                "bz2": CompressionType.BZIP2,
                "xz": CompressionType.XZ,
                "none": CompressionType.NONE,
            }
            compression = compression_map.get(args.compress, CompressionType.GZIP)
            
            # Determine backup type
            backup_type = BackupType.FULL if args.type == "full" else BackupType.INCREMENTAL
            
            # Create backup manager
            password = args.password if args.encrypt else None
            manager = BackupManager(
                backup_dir=args.output,
                compression=compression,
                encrypt_password=password,
            )
            
            # Source paths
            source_paths = [
                "./data/memories",
                "./data/knowledge_graph.json",
            ]
            
            print(f"Creating {args.type} backup...")
            manifest = manager.create_backup(
                source_paths=source_paths,
                backup_type=backup_type,
            )
            
            print(f"Backup created successfully!")
            print(f"  Backup ID: {manifest.backup_id}")
            print(f"  Size: {manifest.size_bytes / 1024 / 1024:.2f} MB")
            print(f"  Checksum: {manifest.checksum[:16]}...")
            print(f"  Location: {args.output}")
            
            return 0
            
        except (IOError, OSError, ValueError, RuntimeError) as e:
            logger.error("Backup failed: %s", e)
            return 1


class RestoreCommand(CLICommand):
    """恢复命令"""
    
    name = "restore"
    description = "Restore from a backup"
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "backup_id",
            help="Backup ID to restore",
        )
        parser.add_argument(
            "--backup-dir",
            default="./data/backups",
            help="Backup directory",
        )
        parser.add_argument(
            "--restore-dir",
            default="./data/restored",
            help="Restore target directory",
        )
        parser.add_argument(
            "--password",
            help="Decryption password",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing data",
        )
    
    def execute(self, args: argparse.Namespace) -> int:
        try:
            from memory_system.storage.backup_restore_manager import BackupManager
            
            manager = BackupManager(
                backup_dir=args.backup_dir,
                encrypt_password=args.password,
            )
            
            # Check if restore directory exists
            restore_dir = Path(args.restore_dir)
            if restore_dir.exists() and any(restore_dir.iterdir()) and not args.force:
                print(f"Restore directory not empty: {restore_dir}")
                print("Use --force to overwrite")
                return 1
            
            print(f"Restoring backup {args.backup_id}...")
            success = manager.restore_backup(
                backup_id=args.backup_id,
                restore_dir=args.restore_dir,
            )
            
            if success:
                print(f"Backup restored successfully to: {args.restore_dir}")
                return 0
            else:
                print("Restore failed")
                return 1
                
        except (IOError, OSError, ValueError, RuntimeError) as e:
            logger.error("Restore failed: %s", e)
            return 1


class ConfigCommand(CLICommand):
    """配置命令"""
    
    name = "config"
    description = "Manage configuration"
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        subparsers = parser.add_subparsers(dest="config_action")
        
        # Get
        get_parser = subparsers.add_parser("get", help="Get configuration value")
        get_parser.add_argument("key", help="Configuration key (dot notation)")
        
        # Set
        set_parser = subparsers.add_parser("set", help="Set configuration value")
        set_parser.add_argument("key", help="Configuration key")
        set_parser.add_argument("value", help="Configuration value")
        
        # List
        subparsers.add_parser("list", help="List all configuration")
    
    def execute(self, args: argparse.Namespace) -> int:
        config_file = Path("./memory_config.yaml")
        
        if not config_file.exists():
            print(f"Configuration file not found: {config_file}")
            print("Run 'memory-system init' first")
            return 1
        
        try:
            from memory_system.infra.dynamic_config_manager import create_config_manager
            
            manager = create_config_manager(config_path=config_file)
            
            if args.config_action == "get":
                value = manager.get(args.key)
                print(json.dumps(value, indent=2, default=str))
                
            elif args.config_action == "set":
                # Parse value
                try:
                    parsed_value = json.loads(args.value)
                except json.JSONDecodeError:
                    parsed_value = args.value
                
                manager.set(args.key, parsed_value)
                manager.save_to_file(config_file, format="yaml")
                print(f"Set {args.key} = {parsed_value}")
                
            elif args.config_action == "list":
                config = manager.as_dict()
                print(json.dumps(config, indent=2, default=str))
            
            return 0
            
        except (ValueError, TypeError, OSError, RuntimeError) as e:
            logger.error("Config command failed: %s", e)
            return 1


class ServeCommand(CLICommand):
    """服务命令"""
    
    name = "serve"
    description = "Start the HTTP API server"
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--host",
            default="0.0.0.0",
            help="Host to bind (default: 0.0.0.0)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=8000,
            help="Port to bind (default: 8000)",
        )
        parser.add_argument(
            "--reload",
            action="store_true",
            help="Enable auto-reload (development)",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=1,
            help="Number of worker processes",
        )
        parser.add_argument(
            "--config",
            default="./memory_config.yaml",
            help="Configuration file",
        )
    
    def execute(self, args: argparse.Namespace) -> int:
        try:
            from memory_system.api.fastapi_service_layer import create_app
            
            print(f"Starting server on {args.host}:{args.port}")
            
            import uvicorn
            uvicorn.run(
                "memory_system.service_layer:create_app",
                host=args.host,
                port=args.port,
                reload=args.reload,
                workers=args.workers if not args.reload else 1,
            )
            
            return 0
            
        except ImportError:
            print("FastAPI/uvicorn not installed. Install with: pip install fastapi uvicorn")
            return 1
        except (OSError, RuntimeError, ValueError) as e:
            logger.error("Server failed: %s", e)
            return 1


class MonitorCommand(CLICommand):
    """监控命令"""
    
    name = "monitor"
    description = "System monitoring commands"
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        subparsers = parser.add_subparsers(dest="monitor_action")
        
        # Start
        start_parser = subparsers.add_parser("start", help="Start monitoring")
        start_parser.add_argument(
            "--interval",
            type=int,
            default=30,
            help="Collection interval in seconds",
        )
        
        # Status
        subparsers.add_parser("status", help="Show monitoring status")
        
        # Metrics
        metrics_parser = subparsers.add_parser("metrics", help="Show current metrics")
        metrics_parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format",
        )
    
    def execute(self, args: argparse.Namespace) -> int:
        try:
            from memory_system.observability.system_monitoring_alerting import MonitoringService
            
            if args.monitor_action == "start":
                print(f"Starting monitoring (interval={args.interval}s)...")
                print("Press Ctrl+C to stop")
                
                service = MonitoringService(interval_sec=args.interval)
                service.start()
                
                try:
                    while True:
                        import time
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\nStopping monitoring...")
                    service.stop()
                    
            elif args.monitor_action == "status":
                print("Monitoring status: not implemented")
                
            elif args.monitor_action == "metrics":
                service = MonitoringService()
                metrics = service.get_latest_metrics()
                
                if metrics:
                    if args.format == "json":
                        print(metrics.to_json())
                    else:
                        print(f"CPU: {metrics.cpu_percent:.1f}%")
                        print(f"Memory: {metrics.memory_percent:.1f}% ({metrics.memory_used}MB / {metrics.memory_total}MB)")
                        print(f"Disk: {metrics.disk_percent:.1f}%")
                else:
                    print("No metrics available")
            
            return 0
            
        except ImportError as e:
            print(f"Required dependency not found: {e}")
            return 1
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            logger.error("Monitor command failed: %s", e)
            return 1


# ---------------------------------------------------------------------------
# CLI Main
# ---------------------------------------------------------------------------

def create_parser() -> argparse.ArgumentParser:
    """创建参数解析器"""
    parser = argparse.ArgumentParser(
        prog="memory-system",
        description="Agent Memory System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              %(prog)s init                    # Initialize system
              %(prog)s status                  # Show system status
              %(prog)s backup --type full      # Create full backup
              %(prog)s serve --port 8080       # Start server
              %(prog)s monitor metrics         # Show metrics
        """),
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 3.8.0",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Register commands
    commands: list[CLICommand] = [
        InitCommand(),
        StatusCommand(),
        BackupCommand(),
        RestoreCommand(),
        ConfigCommand(),
        ServeCommand(),
        MonitorCommand(),
    ]
    
    for cmd in commands:
        cmd_parser = subparsers.add_parser(cmd.name, help=cmd.description)
        cmd.add_arguments(cmd_parser)
        cmd_parser.set_defaults(command_instance=cmd)
    
    return parser


def main(args: Optional[list[str]] = None) -> int:
    """CLI 入口点"""
    parser = create_parser()
    parsed_args = parser.parse_args(args)
    
    if parsed_args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if hasattr(parsed_args, "command_instance"):
        return parsed_args.command_instance.execute(parsed_args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "CLICommand",
    "InitCommand",
    "StatusCommand",
    "BackupCommand",
    "RestoreCommand",
    "ConfigCommand",
    "ServeCommand",
    "MonitorCommand",
    "main",
]
