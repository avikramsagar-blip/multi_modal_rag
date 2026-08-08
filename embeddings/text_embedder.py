"""
embeddings/text_embedder.py

Text embedding using BAAI/bge-small-en-v1.5 via sentence-transformers.
Model is loaded once and cached at module level.
"""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_model: SentenceTransformer | None = None

# BGE small embedding dimension
EMBEDDING_DIM = 384


def get_text_embedder() -> "TextEmbedder":
    return TextEmbedder()


class TextEmbedder:
    """Thin wrapper so app.py can store an instance in st.session_state."""

    def __init__(self) -> None:
        global _model
        if _model is None:
            _model = SentenceTransformer(_MODEL_NAME)
        self._model = _model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of strings.
        Returns a list of float vectors (length EMBEDDING_DIM each).
        Handles empty input gracefully.
        """
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]
