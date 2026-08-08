"""
embeddings/image_embedder.py

Image (and image-query) embedding using OpenCLIP ViT-B/32.
Model is loaded once and cached at module level.
"""

from __future__ import annotations

import open_clip
import torch
from PIL import Image

_model_instance = None
_preprocess_fn = None
_tokenizer = None

MODEL_NAME = "ViT-B-32"
PRETRAINED = "openai"

# OpenCLIP ViT-B/32 output dimension
EMBEDDING_DIM = 512


def _load_model():
    global _model_instance, _preprocess_fn, _tokenizer
    if _model_instance is None:
        _model_instance, _, _preprocess_fn = open_clip.create_model_and_transforms(
            MODEL_NAME, pretrained=PRETRAINED
        )
        _tokenizer = open_clip.get_tokenizer(MODEL_NAME)
        _model_instance.eval()


def get_image_embedder() -> "ImageEmbedder":
    return ImageEmbedder()


class ImageEmbedder:
    """Thin wrapper so app.py can store an instance in st.session_state."""

    def __init__(self) -> None:
        _load_model()
        self._model = _model_instance
        self._preprocess = _preprocess_fn
        self._tokenizer = _tokenizer

    def embed_images(self, pil_images: list[Image.Image]) -> list[list[float]]:
        """
        Embed a list of PIL Images.
        Returns a list of float vectors (length EMBEDDING_DIM each).
        """
        if not pil_images:
            return []
        tensors = torch.stack(
            [self._preprocess(img) for img in pil_images]
        )
        with torch.no_grad():
            features = self._model.encode_image(tensors)
            features = features / features.norm(dim=-1, keepdim=True)
        return features.cpu().tolist()

    def embed_text(self, texts: list[str]) -> list[list[float]]:
        """
        Embed text strings using CLIP's text encoder.
        Used at query time when searching image/keyframe collections.
        """
        if not texts:
            return []
        tokens = self._tokenizer(texts)
        with torch.no_grad():
            features = self._model.encode_text(tokens)
            features = features / features.norm(dim=-1, keepdim=True)
        return features.cpu().tolist()
