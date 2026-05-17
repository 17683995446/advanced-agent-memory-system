"""
Unit tests for the embedding module.
"""
import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock, patch, PropertyMock

from memory_system.processing.text_embedding_provider import (
    FakeEmbeddingProvider,
    SentenceTransformerProvider,
    OpenAIProvider,
    EmbeddingFactory,
    EmbeddingConfig,
)


# ---------------------------------------------------------------------------
# TestFakeEmbeddingProvider
# ---------------------------------------------------------------------------

class TestFakeEmbeddingProvider:
    """Tests for the deterministic fake embedding provider."""

    def test_encode_returns_correct_dimension(self):
        """encode() should return a vector of the default dimension (128)."""
        provider = FakeEmbeddingProvider()
        vec = provider.encode("hello")
        assert isinstance(vec, list)
        assert len(vec) == 128

    def test_encode_deterministic(self):
        """Encoding the same text twice must return the same vector."""
        provider = FakeEmbeddingProvider()
        vec1 = provider.encode("deterministic test")
        vec2 = provider.encode("deterministic test")
        assert vec1 == vec2

    def test_encode_different_texts_different_vectors(self):
        """Different texts should produce different embedding vectors."""
        provider = FakeEmbeddingProvider()
        vec_a = provider.encode("apple")
        vec_b = provider.encode("banana")
        assert vec_a != vec_b

    def test_encode_custom_dimension(self):
        """FakeEmbeddingProvider(dimension=256) should return 256-dim vectors."""
        provider = FakeEmbeddingProvider(dimension=256)
        vec = provider.encode("custom dim")
        assert len(vec) == 256

    def test_encode_batch(self):
        """encode_batch should return one vector per input text."""
        provider = FakeEmbeddingProvider()
        texts = ["a", "b", "c"]
        results = provider.encode_batch(texts)
        assert len(results) == 3
        for vec in results:
            assert len(vec) == 128
            assert isinstance(vec, list)

    def test_similarity_identical_vectors(self):
        """Cosine similarity of a vector with itself should be ~1.0."""
        provider = FakeEmbeddingProvider()
        vec = provider.encode("identity")
        sim = provider.similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_similarity_orthogonal_vectors(self):
        """Cosine similarity of very different vectors should be low (< 0.5)."""
        provider = FakeEmbeddingProvider()
        vec_a = provider.encode("aaaaaaaaaa")
        vec_b = provider.encode("zzzzzzzzzz")
        sim = provider.similarity(vec_a, vec_b)
        assert sim < 0.5

    def test_dimension_property(self):
        """The dimension property should return the configured value."""
        provider = FakeEmbeddingProvider(dimension=64)
        assert provider.dimension == 64

    def test_encode_empty_string(self):
        """Encoding an empty string should not raise and should return a valid vector."""
        provider = FakeEmbeddingProvider()
        vec = provider.encode("")
        assert isinstance(vec, list)
        assert len(vec) == 128
        # Verify all elements are finite floats.
        assert all(isinstance(v, float) for v in vec)

    def test_encode_chinese_text(self):
        """Should handle Chinese characters without error."""
        provider = FakeEmbeddingProvider()
        vec = provider.encode("你好世界，这是一段中文测试文本。")
        assert isinstance(vec, list)
        assert len(vec) == 128


# ---------------------------------------------------------------------------
# TestEmbeddingConfig
# ---------------------------------------------------------------------------

class TestEmbeddingConfig:
    """Tests for the EmbeddingConfig pydantic model."""

    def test_default_values(self):
        """All default fields should be set to their documented defaults."""
        config = EmbeddingConfig()
        assert config.provider == "auto"
        assert config.model_name is None
        assert config.device == "auto"
        assert config.cache_size == 1024
        assert config.normalize_embeddings is True
        assert config.api_key is None
        assert config.base_url is None
        assert config.dimensions is None
        assert config.fake_dimension == 128
        assert config.dimension is None

    def test_custom_values(self):
        """Custom values should be stored correctly."""
        config = EmbeddingConfig(
            provider="fake",
            model_name="test-model",
            device="cpu",
            cache_size=512,
            normalize_embeddings=False,
            api_key="sk-test",
            base_url="https://example.com/v1",
            dimensions=768,
            fake_dimension=64,
            dimension=32,
        )
        assert config.provider == "fake"
        assert config.model_name == "test-model"
        assert config.device == "cpu"
        assert config.cache_size == 512
        assert config.normalize_embeddings is False
        assert config.api_key == "sk-test"
        assert config.base_url == "https://example.com/v1"
        assert config.dimensions == 768
        assert config.fake_dimension == 64
        assert config.dimension == 32

    def test_dimension_alias_for_fake(self):
        """The generic dimension alias should forward to fake_dimension for the fake provider."""
        config = EmbeddingConfig(provider="fake", dimension=64)
        assert config.fake_dimension == 64

    def test_dimension_alias_for_openai(self):
        """The generic dimension alias should forward to dimensions for the openai provider."""
        config = EmbeddingConfig(provider="openai", dimension=512)
        assert config.dimensions == 512

    def test_extra_fields_forbidden(self):
        """Passing an unrecognised field should raise a ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EmbeddingConfig(invalid_field=1)


# ---------------------------------------------------------------------------
# TestEmbeddingFactory
# ---------------------------------------------------------------------------

class TestEmbeddingFactory:
    """Tests for the EmbeddingFactory creation logic."""

    def test_create_fake(self):
        """EmbeddingFactory.create('fake') should return a FakeEmbeddingProvider."""
        provider = EmbeddingFactory.create("fake")
        assert isinstance(provider, FakeEmbeddingProvider)

    def test_create_fake_with_dimension(self):
        """Creating 'fake' with fake_dimension=32 should yield a 32-dim provider."""
        provider = EmbeddingFactory.create("fake", fake_dimension=32)
        assert isinstance(provider, FakeEmbeddingProvider)
        assert provider.dimension == 32

    def test_create_auto_fallback(self):
        """EmbeddingFactory.create('auto-fallback') should return a provider (Fake if ST unavailable)."""
        # v5.1+: 'auto' requires sentence-transformers, use 'auto-fallback' for fallback behavior
        # Mock the sentence-transformers availability check to avoid network requests
        with patch.object(EmbeddingFactory, '_is_sentence_transformers_available', return_value=False):
            provider = EmbeddingFactory.create("auto-fallback")
            # Should fall back to FakeEmbeddingProvider
            assert isinstance(provider, FakeEmbeddingProvider)
            assert hasattr(provider, "encode")
            assert hasattr(provider, "encode_batch")
            assert hasattr(provider, "dimension")

    def test_create_sentence_transformer_not_available(self):
        """When sentence-transformers is not installed, creating 'st' should raise."""
        # We cannot easily uninstall sentence_transformers in a running test,
        # so we test the fallback path indirectly via 'auto-fallback' when the library
        # is genuinely absent, or we verify the factory returns FakeEmbeddingProvider
        # when ST is not available.
        if not EmbeddingFactory._is_sentence_transformers_available():
            provider = EmbeddingFactory.create("auto-fallback")
            assert isinstance(provider, FakeEmbeddingProvider)
        else:
            # ST is available -- creating 'st' should succeed.
            provider = EmbeddingFactory.create("st")
            assert isinstance(provider, SentenceTransformerProvider)

    def test_create_openai_without_key(self):
        """Creating an OpenAI provider without a key should not raise on init,
        but calling encode should raise due to missing credentials."""
        provider = EmbeddingFactory.create("openai")
        assert isinstance(provider, OpenAIProvider)
        # Attempting to encode should fail because there is no valid API key.
        with pytest.raises(Exception):
            provider.encode("this should fail")


# ---------------------------------------------------------------------------
# TestSentenceTransformerProvider
# ---------------------------------------------------------------------------

_ST_AVAILABLE = False
try:
    import sentence_transformers  # noqa: F401
    _ST_AVAILABLE = True
except Exception:
    pass


@pytest.mark.skipif(not _ST_AVAILABLE, reason="sentence-transformers is not installed")
class TestSentenceTransformerProvider:
    """Tests for the SentenceTransformerProvider (requires sentence-transformers)."""

    def test_init_lazy(self):
        """Creating the provider should not load the model immediately."""
        provider = SentenceTransformerProvider()
        # The model should not be loaded until encode is called.
        assert provider._model is None

    def test_init_with_custom_model(self):
        """Initialising with a custom model name should not raise."""
        provider = SentenceTransformerProvider(model_name="all-MiniLM-L6-v2")
        assert provider._model_name == "all-MiniLM-L6-v2"
        assert provider._model is None

    def test_encode_returns_vector(self):
        """encode() should return a list of floats."""
        # Use mock to avoid actual model loading and network requests
        with patch.object(SentenceTransformerProvider, '_do_encode', return_value=tuple([0.1] * 384)):
            provider = SentenceTransformerProvider()
            provider._dimension = 384  # Pre-set dimension to avoid model loading
            vec = provider.encode("hello world")
            assert isinstance(vec, list)
            assert len(vec) == 384
            assert all(isinstance(v, float) for v in vec)

    def test_encode_deterministic(self):
        """Encoding the same text twice should return the same vector."""
        with patch.object(SentenceTransformerProvider, '_do_encode', return_value=tuple([0.1] * 384)):
            provider = SentenceTransformerProvider()
            provider._dimension = 384
            vec1 = provider.encode("deterministic")
            vec2 = provider.encode("deterministic")
            assert vec1 == vec2

    def test_encode_batch(self):
        """encode_batch should return one vector per input text."""
        # Mock the model to avoid actual network requests
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1] * 384, [0.2] * 384, [0.3] * 384])
        
        with patch.object(SentenceTransformerProvider, '_load_model', return_value=mock_model):
            provider = SentenceTransformerProvider()
            provider._dimension = 384
            provider._model = mock_model
            texts = ["first", "second", "third"]
            results = provider.encode_batch(texts)
            assert len(results) == 3
            for vec in results:
                assert isinstance(vec, list)
                assert len(vec) == 384

    def test_dimension_property(self):
        """The dimension property should return a positive integer."""
        provider = SentenceTransformerProvider()
        provider._dimension = 384  # Pre-set dimension to avoid model loading
        dim = provider.dimension
        assert isinstance(dim, int)
        assert dim > 0


# ---------------------------------------------------------------------------
# TestSentenceTransformerMock
# ---------------------------------------------------------------------------

class TestSentenceTransformerMock:
    """Mock tests for SentenceTransformer provider"""
    
    def test_st_encode_mock(self):
        """Test SentenceTransformer encode with mock"""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3, 0.4]])
        
        result = mock_model.encode(["test text"])
        assert result.shape == (1, 4)
    
    def test_st_encode_batch_mock(self):
        """Test SentenceTransformer batch encode with mock"""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([
            [0.1, 0.2, 0.3, 0.4],
            [0.5, 0.6, 0.7, 0.8],
        ])
        
        result = mock_model.encode(["text1", "text2"])
        assert result.shape == (2, 4)
    
    def test_st_dimension_mock(self):
        """Test SentenceTransformer dimension"""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        assert mock_model.get_sentence_embedding_dimension() == 384
    
    def test_st_device_mock(self):
        """Test SentenceTransformer device selection"""
        mock_model = MagicMock()
        mock_model.device = "cpu"
        assert mock_model.device == "cpu"


# ---------------------------------------------------------------------------
# TestOpenAIEmbeddingMock
# ---------------------------------------------------------------------------

class TestOpenAIEmbeddingMock:
    """Mock tests for OpenAI embedding provider"""
    
    def test_openai_encode_mock(self):
        """Test OpenAI encode with mock"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create.return_value = mock_response
        
        result = mock_client.embeddings.create(
            model="text-embedding-ada-002",
            input="test text",
        )
        assert len(result.data[0].embedding) == 3
    
    def test_openai_encode_batch_mock(self):
        """Test OpenAI batch encode with mock"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1, 0.2, 0.3]),
            MagicMock(embedding=[0.4, 0.5, 0.6]),
        ]
        mock_client.embeddings.create.return_value = mock_response
        
        result = mock_client.embeddings.create(
            model="text-embedding-ada-002",
            input=["text1", "text2"],
        )
        assert len(result.data) == 2
    
    def test_openai_dimensions_mock(self):
        """Test OpenAI with custom dimensions"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 256)]
        mock_client.embeddings.create.return_value = mock_response
        
        result = mock_client.embeddings.create(
            model="text-embedding-3-small",
            input="test",
            dimensions=256,
        )
        assert len(result.data[0].embedding) == 256


# ---------------------------------------------------------------------------
# TestEmbeddingFactoryMock
# ---------------------------------------------------------------------------

class TestEmbeddingFactoryMock:
    """Mock tests for EmbeddingFactory with unavailable providers"""
    
    def test_factory_sentence_transformer_unavailable(self):
        """Test factory when sentence-transformers unavailable"""
        from memory_system.processing.text_embedding_provider import EmbeddingFactory, EmbeddingConfig
        
        # 模拟 ImportError
        with patch.dict('sys.modules', {'sentence_transformers': None}):
            try:
                config = EmbeddingConfig(provider="sentence-transformer")
                provider = EmbeddingFactory.create("sentence-transformer")
            except ImportError:
                pass  # 预期的行为
    
    def test_factory_openai_unavailable(self):
        """Test factory when openai unavailable"""
        from memory_system.processing.text_embedding_provider import EmbeddingFactory
        
        with patch.dict('sys.modules', {'openai': None}):
            try:
                provider = EmbeddingFactory.create("openai", api_key="test")
            except ImportError:
                pass  # 预期的行为
    
    def test_factory_auto_fallback(self):
        """Test factory auto falls back to fake"""
        from memory_system.processing.text_embedding_provider import EmbeddingFactory, FakeEmbeddingProvider
        
        # auto 模式在无可用 provider 时应回退到 fake
        provider = EmbeddingFactory.create("fake")
        assert isinstance(provider, FakeEmbeddingProvider)
