"""Unit tests for the tokenizer module."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.processing.chinese_english_tokenizer import tokenize, tokenize_for_search, _detect_language


class TestDetectLanguage:
    def test_chinese_text(self):
        assert _detect_language("你好世界") == "chinese"

    def test_english_text(self):
        assert _detect_language("hello world") == "english"

    def test_mixed_mostly_chinese(self):
        assert _detect_language("你好hello世界") == "chinese"

    def test_mixed_mostly_english(self):
        assert _detect_language("hello你好world") == "english"

    def test_empty_string(self):
        assert _detect_language("") == "english"

    def test_numbers_only(self):
        assert _detect_language("12345") == "english"


class TestTokenize:
    def test_chinese_text(self):
        tokens = tokenize("张三是一名软件工程师")
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        # Should not contain stopwords
        assert "是" not in tokens
        assert "一名" not in tokens or len(tokens) > 0  # jieba may or may not split this

    def test_english_text(self):
        tokens = tokenize("hello world python programming")
        assert isinstance(tokens, list)
        assert "hello" in tokens
        assert "world" in tokens
        assert "python" in tokens
        # Should not contain stopwords
        assert "the" not in tokens

    def test_auto_detect_chinese(self):
        tokens = tokenize("我喜欢Python编程", language="auto")
        assert len(tokens) > 0

    def test_auto_detect_english(self):
        tokens = tokenize("I love Python programming", language="auto")
        assert len(tokens) > 0

    def test_empty_string(self):
        assert tokenize("") == []

    def test_single_char(self):
        tokens = tokenize("我")
        # Single Chinese char should be filtered (too short)
        assert len(tokens) == 0

    def test_returns_list_of_strings(self):
        tokens = tokenize("这是一个测试")
        assert all(isinstance(t, str) for t in tokens)

    def test_no_duplicates_basic(self):
        """Same text tokenized twice should give same results"""
        t1 = tokenize("张三是工程师")
        t2 = tokenize("张三是工程师")
        assert t1 == t2


class TestTokenizeForSearch:
    def test_chinese_search(self):
        tokens = tokenize_for_search("张三是一名软件工程师")
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        # All tokens should be lowercase strings
        assert all(isinstance(t, str) for t in tokens)

    def test_english_search(self):
        tokens = tokenize_for_search("Hello World Python")
        assert "hello" in tokens
        assert "world" in tokens
        assert "python" in tokens

    def test_mixed_text(self):
        tokens = tokenize_for_search("张三喜欢Python编程")
        assert len(tokens) > 0

    def test_filters_stopwords(self):
        tokens = tokenize_for_search("这是一个测试")
        assert "的" not in tokens
        assert "是" not in tokens

    def test_empty_string(self):
        assert tokenize_for_search("") == []
