"""Unit tests for the serializer module."""
import pytest
import json
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.processing.memory_data_serializer import MemorySerializer, ExportFormat


class TestMemorySerializer:
    def setup_method(self):
        self.serializer = MemorySerializer()
        self.records = [
            {"id": "1", "content": "Hello world", "embedding": [0.1, 0.2], "metadata": {"key": "val"}},
            {"id": "2", "content": "Python programming", "importance": 0.8},
        ]

    def test_export_json(self):
        data = self.serializer.export(self.records, format=ExportFormat.JSON)
        parsed = json.loads(data)
        assert parsed["version"] == "3.0"
        assert parsed["record_count"] == 2
        assert len(parsed["records"]) == 2

    def test_export_json_compact(self):
        data = self.serializer.export(self.records, format=ExportFormat.JSON, pretty=False)
        parsed = json.loads(data)
        assert parsed["record_count"] == 2

    def test_export_yaml(self):
        data = self.serializer.export(self.records, format=ExportFormat.YAML)
        assert "version: '3.0'" in data
        assert "Hello world" in data

    def test_export_exclude_embeddings(self):
        s = MemorySerializer(include_embeddings=False)
        data = s.export(self.records, format=ExportFormat.JSON)
        parsed = json.loads(data)
        assert "embedding" not in parsed["records"][0]

    def test_export_exclude_metadata(self):
        s = MemorySerializer(include_metadata=False)
        data = s.export(self.records, format=ExportFormat.JSON)
        parsed = json.loads(data)
        assert "metadata" not in parsed["records"][0]

    def test_import_json(self):
        exported = self.serializer.export(self.records, format=ExportFormat.JSON)
        imported = self.serializer.import_data(exported, format=ExportFormat.JSON)
        assert len(imported) == 2
        assert imported[0]["content"] == "Hello world"

    def test_import_yaml(self):
        exported = self.serializer.export(self.records, format=ExportFormat.YAML)
        imported = self.serializer.import_data(exported, format=ExportFormat.YAML)
        assert len(imported) == 2

    def test_import_normalize(self):
        exported = self.serializer.export([{"content": "test"}], format=ExportFormat.JSON)
        imported = self.serializer.import_data(exported, format=ExportFormat.JSON)
        record = imported[0]
        assert "id" in record
        assert record["memory_type"] == "semantic"
        assert record["category"] == "general"

    def test_import_invalid_json(self):
        with pytest.raises(Exception):
            self.serializer.import_data("not json", format=ExportFormat.JSON)

    def test_import_missing_records(self):
        with pytest.raises(ValueError, match="missing 'records'"):
            self.serializer.import_data('{"version": "3.0"}', format=ExportFormat.JSON)

    def test_import_records_not_list(self):
        with pytest.raises(ValueError, match="must be a list"):
            self.serializer.import_data('{"records": "not a list"}', format=ExportFormat.JSON)

    def test_export_to_file(self, tmp_path):
        filepath = str(tmp_path / "test_export.json")
        self.serializer.export_to_file(self.records, filepath)
        with open(filepath) as f:
            data = json.load(f)
        assert data["record_count"] == 2

    def test_import_from_file(self, tmp_path):
        filepath = str(tmp_path / "test_import.json")
        self.serializer.export_to_file(self.records, filepath)
        imported = self.serializer.import_from_file(filepath)
        assert len(imported) == 2

    def test_export_to_file_yaml(self, tmp_path):
        filepath = str(tmp_path / "test_export.yaml")
        self.serializer.export_to_file(self.records, filepath)
        imported = self.serializer.import_from_file(filepath)
        assert len(imported) == 2

    def test_validate_valid(self):
        exported = self.serializer.export(self.records, format=ExportFormat.JSON)
        valid, msg = self.serializer.validate(exported, format=ExportFormat.JSON)
        assert valid is True

    def test_validate_invalid(self):
        valid, msg = self.serializer.validate("bad data", format=ExportFormat.JSON)
        assert valid is False

    def test_roundtrip(self):
        exported = self.serializer.export(self.records, format=ExportFormat.JSON)
        imported = self.serializer.import_data(exported, format=ExportFormat.JSON)
        re_exported = self.serializer.export(imported, format=ExportFormat.JSON)
        # Should be able to re-import
        re_imported = self.serializer.import_data(re_exported, format=ExportFormat.JSON)
        assert len(re_imported) == 2

    def test_chinese_content(self):
        records = [{"content": "这是一个中文测试", "id": "cn1"}]
        exported = self.serializer.export(records, format=ExportFormat.JSON)
        imported = self.serializer.import_data(exported, format=ExportFormat.JSON)
        assert imported[0]["content"] == "这是一个中文测试"

    def test_unsupported_format(self):
        with pytest.raises(ValueError):
            self.serializer.export(self.records, format="xml")


class TestExportFormat:
    def test_values(self):
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.YAML.value == "yaml"
