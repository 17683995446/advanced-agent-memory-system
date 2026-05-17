"""
Embedding module for the Agent Memory System.

Provides a modular, extensible embedding interface with multiple provider
implementations (sentence-transformers, OpenAI, and a deterministic fake
provider for testing).  An `EmbeddingFactory` makes it easy to instantiate
the right backend at runtime.

Typical usage::

    from agent_memory_system.memory_system.embedding import EmbeddingFactory

    provider = EmbeddingFactory.create("auto")
    vector = provider.encode("Hello world")
    score = provider.similarity(vector, provider.encode("Hi there"))
"""

from __future__ import annotations

import hashlib
import math
import threading
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Configuration models
# ---------------------------------------------------------------------------

class EmbeddingConfig(BaseModel):
    """Central configuration for embedding providers.

    Attributes:
        provider: Provider identifier -- ``"auto"``, ``"auto-fallback"``,
            ``"sentence-transformer"``, ``"st"``, ``"openai"``, or ``"fake"``.
        model_name: Model name / identifier.  Meaning depends on the provider.
        device: Compute device -- ``"cpu"``, ``"cuda"``, or ``"auto"``.
        cache_size: Maximum number of entries in the per-provider LRU cache.
        normalize_embeddings: Whether to L2-normalise vectors before returning.
        api_key: OpenAI API key (only used by :class:`OpenAIProvider`).
        base_url: Optional custom base URL for the OpenAI-compatible API.
        dimensions: Explicit embedding dimension (only used by
            :class:`OpenAIProvider` when the model supports it).
        fake_dimension: Dimensionality for :class:`FakeEmbeddingProvider`.
        dimension: Universal dimension alias -- forwarded to ``fake_dimension``
            (for FakeEmbeddingProvider) or ``dimensions`` (for OpenAI).
        cache_dir: Directory to cache downloaded models (SentenceTransformer).
    """

    model_config = {"extra": "forbid"}

    provider: str = Field(default="auto", description="Embedding provider name.")
    model_name: Optional[str] = Field(default=None, description="Model identifier.")
    device: str = Field(default="auto", description="Compute device (cpu/cuda/auto).")
    cache_size: int = Field(default=1024, ge=0, description="LRU cache size.")
    normalize_embeddings: bool = Field(
        default=True, description="L2-normalise output vectors."
    )
    api_key: Optional[str] = Field(default=None, description="OpenAI API key.")
    base_url: Optional[str] = Field(
        default=None, description="Custom OpenAI-compatible base URL."
    )
    dimensions: Optional[int] = Field(
        default=None, description="Explicit embedding dimension (OpenAI)."
    )
    fake_dimension: int = Field(
        default=128, ge=1, description="Dimension for FakeEmbeddingProvider."
    )
    dimension: Optional[int] = Field(
        default=None, description="Universal dimension alias."
    )
    cache_dir: Optional[str] = Field(
        default=None, description="Directory to cache downloaded models."
    )

    @model_validator(mode="after")
    def _resolve_dimension_alias(self) -> "EmbeddingConfig":
        """Forward the generic ``dimension`` to the provider-specific field."""
        if self.dimension is not None:
            if self.provider in ("fake",) and self.fake_dimension == 128:
                self.fake_dimension = self.dimension
            if self.provider in ("openai",) and self.dimensions is None:
                self.dimensions = self.dimension
        return self


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class EmbeddingProvider(ABC):
    """Abstract interface for all embedding backends.

    Every concrete provider must implement :meth:`encode`,
    :meth:`encode_batch`, and the :attr:`dimension` property.
    """

    def __call__(self, text: str) -> list[float]:
        """Allow provider to be called as a function: provider(text)."""
        return self.encode(text)

    @abstractmethod
    def encode(self, text: str) -> list[float]:
        """Encode a single piece of text into a dense vector.

        Args:
            text: The input text.

        Returns:
            A list of floats representing the embedding.
        """

    @abstractmethod
    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode multiple texts into dense vectors.

        Args:
            texts: A list of input strings.

        Returns:
            A list of embedding vectors (one per input text).
        """

    @staticmethod
    def similarity(vec1: list[float], vec2: list[float]) -> float:
        """Compute cosine similarity between two vectors (numpy-accelerated).

        Args:
            vec1: First embedding vector.
            vec2: Second embedding vector.

        Returns:
            Cosine similarity in the range ``[-1, 1]``.
        """
        v1 = np.asarray(vec1, dtype=np.float64)
        v2 = np.asarray(vec2, dtype=np.float64)
        dot = np.dot(v1, v2)
        norm = np.linalg.norm(v1) * np.linalg.norm(v2)
        if norm == 0.0:
            return 0.0
        return float(dot / norm)

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of the embedding vectors."""


# ---------------------------------------------------------------------------
# Sentence-Transformer provider
# ---------------------------------------------------------------------------

class SentenceTransformerProvider(EmbeddingProvider):
    """Embedding provider backed by the *sentence-transformers* library.

    Features:
    * Lazy model loading -- the transformer is only loaded on first use.
    * Thread-safe via an internal lock.
    * LRU cache (default 1 024 entries) to avoid redundant computation.
    * Configurable device, model, and normalisation.
    * Configurable cache directory for downloaded models.

    Args:
        model_name: HuggingFace model identifier
            (default ``"all-MiniLM-L6-v2"``).
        device: ``"cpu"``, ``"cuda"``, or ``"auto"``.
        normalize_embeddings: L2-normalise vectors before returning.
        cache_size: Maximum cached entries.
        cache_dir: Directory to cache downloaded models.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "auto",
        normalize_embeddings: bool = True,
        cache_size: int = 1024,
        cache_dir: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._normalize = normalize_embeddings
        self._cache_size = cache_size
        self._cache_dir = cache_dir
        self._model: Any | None = None
        self._lock = threading.Lock()
        self._dimension: int | None = None

        # Build a bounded LRU cache that delegates to the underlying _do_encode.
        self._encode_impl = lru_cache(maxsize=cache_size)(self._do_encode)

    # -- internal helpers ---------------------------------------------------

    def _load_model(self) -> Any:
        """Lazily load the sentence-transformers model (thread-safe)."""
        if self._model is not None:
            return self._model
        with self._lock:
            # Double-checked locking pattern.
            if self._model is not None:
                return self._model
            from sentence_transformers import SentenceTransformer  # noqa: WPS433

            device = self._device
            if device == "auto":
                try:
                    import torch  # noqa: WPS433

                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except (ImportError, RuntimeError, OSError):
                    device = "cpu"
            # Build kwargs for SentenceTransformer
            st_kwargs: dict[str, Any] = {"device": device}
            if self._cache_dir is not None:
                st_kwargs["cache_folder"] = self._cache_dir
            self._model = SentenceTransformer(self._model_name, **st_kwargs)
            self._dimension = self._model.get_sentence_embedding_dimension()
            return self._model

    def _do_encode(self, text: str) -> tuple[float, ...]:
        """Actual encoding logic (called through the LRU cache)."""
        model = self._load_model()
        embedding = model.encode(
            text,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
        )
        return tuple(float(v) for v in embedding)

    # -- public API ---------------------------------------------------------

    def encode(self, text: str) -> list[float]:
        """Encode a single text to a vector.

        Args:
            text: Input text.

        Returns:
            Embedding as a list of floats.
        """
        return list(self._encode_impl(text))

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch of texts.

        Args:
            texts: List of input strings.

        Returns:
            List of embedding vectors.
        """
        model = self._load_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
            batch_size=min(64, len(texts)),
        )
        return [list(float(v) for v in row) for row in embeddings]

    @property
    def dimension(self) -> int:
        """Embedding vector dimension."""
        if self._dimension is None:
            self._load_model()
        assert self._dimension is not None  # noqa: S101
        return self._dimension


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class OpenAIProvider(EmbeddingProvider):
    """Embedding provider that calls the OpenAI embeddings API.

    The ``openai`` package is imported inside methods so that projects
    that do not use this provider are not forced to install it.

    Args:
        api_key: OpenAI API key (or set ``OPENAI_API_KEY`` env var).
        model: Model identifier (default ``"text-embedding-3-small"``).
        base_url: Optional custom API base URL.
        dimensions: Explicit dimension (only for models that support it,
            e.g. ``text-embedding-3-*``).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
        dimensions: Optional[int] = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._dimensions = dimensions
        self._dimension: int | None = None

    def _get_client(self) -> Any:
        """Return an OpenAI client instance (imported lazily)."""
        import openai  # noqa: WPS433

        kwargs: dict[str, Any] = {}
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        if self._base_url is not None:
            kwargs["base_url"] = self._base_url
        return openai.OpenAI(**kwargs)

    def _request_kwargs(self) -> dict[str, Any]:
        """Build keyword arguments for the API call."""
        kwargs: dict[str, Any] = {"model": self._model}
        if self._dimensions is not None:
            kwargs["dimensions"] = self._dimensions
        return kwargs

    def encode(self, text: str) -> list[float]:
        """Encode a single text using the OpenAI embeddings API.

        Args:
            text: Input text.

        Returns:
            Embedding as a list of floats.
        """
        client = self._get_client()
        response = client.embeddings.create(input=[text], **self._request_kwargs())
        data = response.data[0]
        embedding = data.embedding
        if self._dimension is None:
            self._dimension = len(embedding)
        return embedding

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode multiple texts in a single API call.

        Args:
            texts: List of input strings.

        Returns:
            List of embedding vectors.
        """
        client = self._get_client()
        response = client.embeddings.create(input=texts, **self._request_kwargs())
        # Sort by index to guarantee ordering matches the input.
        sorted_data = sorted(response.data, key=lambda d: d.index)
        embeddings = [item.embedding for item in sorted_data]
        if self._dimension is None and embeddings:
            self._dimension = len(embeddings[0])
        return embeddings

    @property
    def dimension(self) -> int:
        """Embedding vector dimension.

        If the dimension has not yet been observed (no encode call has been
        made), a default is returned based on the model name.
        """
        if self._dimension is not None:
            return self._dimension
        # Reasonable defaults for known OpenAI models.
        known_dims: dict[str, int] = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return known_dims.get(self._model, self._dimensions or 1536)


# ---------------------------------------------------------------------------
# Fake (deterministic) embedding provider
# ---------------------------------------------------------------------------

class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic, hash-based embedding provider for testing and demos.

    No GPU or model download is required.  Vectors are derived from an
    MD5 hash of the input text and mapped to the range ``[-1, 1]`` using
    a reproducible algorithm.

    Args:
        dimension: Dimensionality of the fake embeddings (default 128).
        seed: Optional integer seed for additional reproducibility.
    """

    def __init__(self, dimension: int = 128, seed: int | None = None) -> None:
        self._dimension = dimension
        self._seed = seed

    def _text_to_vector(self, text: str) -> list[float]:
        """Convert *text* into a deterministic pseudo-random vector."""
        rng = np.random.RandomState(self._seed)  # type: ignore[call-arg]
        # Produce a deterministic byte sequence from the text.
        raw = hashlib.md5(text.encode("utf-8")).digest()
        # Extend the seed bytes by repeating and hashing as needed.
        while len(raw) < self._dimension * 4:
            raw += hashlib.sha256(raw).digest()
        # Convert to float32 array in [-1, 1].
        arr = np.frombuffer(raw[: self._dimension * 4], dtype=np.float32)
        if len(arr) < self._dimension:
            # Pad with additional deterministic values.
            extra = rng.randn(self._dimension - len(arr)).astype(np.float32)
            arr = np.concatenate([arr, extra])
        # Map uint-like bytes to floats in [-1, 1].
        int_arr = arr.view(np.uint32).astype(np.float64)
        max_val = float(np.iinfo(np.uint32).max)
        vec = (int_arr / max_val) * 2.0 - 1.0
        # L2-normalise so that cosine similarity is meaningful.
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return [float(v) for v in vec[: self._dimension]]

    def encode(self, text: str) -> list[float]:
        """Encode a single text to a deterministic vector.

        Args:
            text: Input text.

        Returns:
            A list of floats of length *dimension*.
        """
        return self._text_to_vector(text)

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode multiple texts.

        Args:
            texts: List of input strings.

        Returns:
            List of embedding vectors.
        """
        return [self._text_to_vector(t) for t in texts]

    @property
    def dimension(self) -> int:
        """Return the configured dimensionality."""
        return self._dimension


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class EmbeddingFactory:
    """Factory for creating :class:`EmbeddingProvider` instances.

    Supported provider identifiers:

    * ``"auto"`` -- try :class:`SentenceTransformerProvider`; fall back to
      :class:`FakeEmbeddingProvider` if the library is unavailable.
    * ``"sentence-transformer"`` / ``"st"`` --
      :class:`SentenceTransformerProvider`.
    * ``"openai"`` -- :class:`OpenAIProvider`.
    * ``"fake"`` -- :class:`FakeEmbeddingProvider`.

    Example::

        provider = EmbeddingFactory.create("auto", model_name="all-MiniLM-L6-v2")
    """

    @staticmethod
    def _is_sentence_transformers_available() -> bool:
        """Return ``True`` if the sentence-transformers package is importable."""
        try:
            import sentence_transformers  # noqa: F401, WPS433

            return True
        except (ImportError, ModuleNotFoundError):
            return False

    @staticmethod
    def create(
        provider: str = "auto",
        **kwargs: Any,
    ) -> EmbeddingProvider:
        """Instantiate and return an :class:`EmbeddingProvider`.

        Args:
            provider: Provider identifier (see class docstring).
            **kwargs: Additional keyword arguments forwarded to the
                provider constructor.

        Returns:
            A concrete :class:`EmbeddingProvider` instance.
        """
        key = provider.lower().strip()

        if key in ("sentence-transformer", "st"):
            model_name = kwargs.pop("model_name", "all-MiniLM-L6-v2")
            device = kwargs.pop("device", "auto")
            normalize_embeddings = kwargs.pop("normalize_embeddings", True)
            cache_size = kwargs.pop("cache_size", 1024)
            cache_dir = kwargs.pop("cache_dir", None)
            return SentenceTransformerProvider(
                model_name=model_name,
                device=device,
                normalize_embeddings=normalize_embeddings,
                cache_size=cache_size,
                cache_dir=cache_dir,
            )

        if key == "openai":
            api_key = kwargs.pop("api_key", None)
            model = kwargs.pop("model", "text-embedding-3-small")
            base_url = kwargs.pop("base_url", None)
            dimensions = kwargs.pop("dimensions", None)
            return OpenAIProvider(
                api_key=api_key,
                model=model,
                base_url=base_url,
                dimensions=dimensions,
            )

        if key == "fake":
            dimension = kwargs.pop("fake_dimension", kwargs.pop("dimension", 128))
            seed = kwargs.pop("seed", None)
            return FakeEmbeddingProvider(dimension=dimension, seed=seed)

        if key == "auto":
            # v5.1+: auto 模式默认要求真实嵌入模型
            if EmbeddingFactory._is_sentence_transformers_available():
                return EmbeddingFactory.create("sentence-transformer", **kwargs)
            raise RuntimeError(
                "Embedding provider 'auto' requires sentence-transformers. "
                "Install with: pip install sentence-transformers\n"
                "Or explicitly use provider='fake' for testing."
            )

        if key == "auto-fallback":
            # 旧行为：优先真实模型，不可用时回退到 fake
            if EmbeddingFactory._is_sentence_transformers_available():
                return EmbeddingFactory.create("sentence-transformer", **kwargs)
            return EmbeddingFactory.create("fake", **kwargs)

        raise ValueError(
            f"Unknown embedding provider: {provider!r}. "
            f"Supported: 'auto', 'auto-fallback', 'sentence-transformer'/'st', "
            f"'openai', 'fake'."
        )


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "EmbeddingConfig",
    "EmbeddingFactory",
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "OpenAIProvider",
    "SentenceTransformerProvider",
]
