"""
vectorstore/chroma_client.py

Chroma Cloud client.
- Connects using API key auth.
- Creates all 6 collections on first call if they do not exist.
- Provides upsert_chunks() to write embedding records.
- Provides write_chunks() which routes each chunk to the correct collection
  and marks ingestion_status = complete after all chunks are written.
"""

from __future__ import annotations

import chromadb

from core.logging_config import get_logger

from core.config import settings
from embeddings.image_embedder import EMBEDDING_DIM as IMAGE_DIM
from embeddings.text_embedder import EMBEDDING_DIM as TEXT_DIM

logger = get_logger(__name__)

# Collection name → expected embedding dimension
COLLECTIONS: dict[str, int] = {
    "text_chunks": TEXT_DIM,
    "ocr_chunks": TEXT_DIM,
    "audio_transcript_chunks": TEXT_DIM,
    "video_transcript_chunks": TEXT_DIM,
    "image_chunks": IMAGE_DIM,
    "video_keyframe_chunks": IMAGE_DIM,
}

# Map modality value → collection name
MODALITY_TO_COLLECTION: dict[str, str] = {
    "text": "text_chunks",
    "ocr": "ocr_chunks",
    "image": "image_chunks",
    "audio": "audio_transcript_chunks",
    "video_transcript": "video_transcript_chunks",
    "video_keyframe": "video_keyframe_chunks",
}

_client: chromadb.CloudClient | None = None


def get_chroma_client() -> "ChromaWrapper":
    return ChromaWrapper()


class ChromaWrapper:
    """
    Manages the Chroma Cloud connection and all collection handles.
    Store one instance in st.session_state["chroma_client"].
    """

    def __init__(self) -> None:
        global _client
        if _client is None:
            logger.info(
                "Initializing Chroma Cloud client for tenant=%s database=%s",
                settings.chroma_tenant,
                settings.chroma_database,
            )
            _client = chromadb.CloudClient(
                tenant=settings.chroma_tenant,
                database=settings.chroma_database,
                api_key=settings.chroma_api_key,
            )
        self._client = _client
        self._collections: dict[str, chromadb.Collection] = {}
        self._init_collections()

    def _init_collections(self) -> None:
        for name in COLLECTIONS:
            col = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
            self._collections[name] = col
            logger.info("Chroma collection ready: %s", name)

    def list_collection_names(self) -> list[str]:
        return sorted(self._collections.keys())

    def _get_collection(self, name: str) -> chromadb.Collection:
        if name not in self._collections:
            raise ValueError(f"Unknown collection '{name}'. Valid: {list(COLLECTIONS)}")
        return self._collections[name]

    def upsert_chunks(
        self,
        collection_name: str,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        documents: list[str],
    ) -> None:
        """
        Upsert records into the named collection.
        ids, embeddings, metadatas, documents must all be the same length.
        """
        col = self._get_collection(collection_name)
        col.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def write_chunks(self, chunks: list[dict]) -> None:
        """
        Write a list of chunk dicts produced by any parser.

        Each chunk dict must contain:
            chunk_id    str
            embedding   list[float]
            text        str   (empty string for image/keyframe chunks)
            metadata    dict  (must include 'modality' key)

        Sets ingestion_status = 'complete' on all metadata dicts after
        successful write.
        """
        if not chunks:
            logger.warning("write_chunks called with no chunks")
            return

        logger.info("Writing %d chunks to Chroma", len(chunks))

        # Group chunks by target collection
        grouped: dict[str, list[dict]] = {}
        for chunk in chunks:
            modality = chunk["metadata"]["modality"]
            col_name = MODALITY_TO_COLLECTION.get(modality)
            if col_name is None:
                raise ValueError(f"Unknown modality '{modality}' in chunk metadata.")
            chunk["metadata"]["ingestion_status"] = "pending"
            grouped.setdefault(col_name, []).append(chunk)

        try:
            # Phase 1: write pending records
            for col_name, col_chunks in grouped.items():
                self.upsert_chunks(
                    collection_name=col_name,
                    ids=[c["chunk_id"] for c in col_chunks],
                    embeddings=[c["embedding"] for c in col_chunks],
                    metadatas=[c["metadata"] for c in col_chunks],
                    documents=[c.get("text", "") for c in col_chunks],
                )

            # Phase 2: mark all successful records complete and persist again
            for chunk in chunks:
                chunk["metadata"]["ingestion_status"] = "complete"

            for col_name, col_chunks in grouped.items():
                self.upsert_chunks(
                    collection_name=col_name,
                    ids=[c["chunk_id"] for c in col_chunks],
                    embeddings=[c["embedding"] for c in col_chunks],
                    metadatas=[c["metadata"] for c in col_chunks],
                    documents=[c.get("text", "") for c in col_chunks],
                )
            logger.info("Successfully wrote and finalized %d chunks", len(chunks))
        except Exception:
            logger.exception("Failed to fully write chunks to Chroma")
            raise
