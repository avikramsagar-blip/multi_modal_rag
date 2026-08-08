"""
ingestion/video_parser.py

Parses video files (mp4, mkv, avi, mov, webm).

Pipeline:
  1. Stage video to temp file
  2. Check duration against MAX_VIDEO_SEC
  3. Extract audio → transcribe (reuses audio_parser logic) → video_transcript_chunks
  4. Extract keyframes → deduplicate by perceptual hash → embed → video_keyframe_chunks
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import imagehash
import streamlit as st
from PIL import Image

from core.limits import (
    KEYFRAME_INTERVAL_SEC,
    MAX_KEYFRAMES,
    MAX_VIDEO_SEC,
    MIN_TRANSCRIPT_WORDS,
)
from ingestion.audio_parser import parse_audio
from ingestion.chunking import chunk_text
from ingestion.metadata import build_metadata
from utils.ffmpeg import extract_audio, extract_keyframes, get_video_duration

# Perceptual hash distance threshold for near-duplicate frame detection
_HASH_DISTANCE_THRESHOLD = 10


def _deduplicate_frames(
    frames: list[tuple[float, Image.Image]],
) -> list[tuple[float, Image.Image]]:
    """Remove near-duplicate frames using perceptual hashing."""
    seen_hashes: list[imagehash.ImageHash] = []
    unique: list[tuple[float, Image.Image]] = []

    for ts, img in frames:
        h = imagehash.phash(img)
        if all(abs(h - s) > _HASH_DISTANCE_THRESHOLD for s in seen_hashes):
            seen_hashes.append(h)
            unique.append((ts, img))

    return unique


def parse_video(
    file_bytes: bytes,
    filename: str,
    session_id: str,
    document_id: str,
) -> list[dict]:
    """
    Parse a video file and return chunk dicts for transcript + keyframes.
    """
    image_embedder = st.session_state["image_embedder"]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "video"

    # Stage video to disk (FFmpeg needs a file path)
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(file_bytes)
        video_path = Path(tmp.name)

    results: list[dict] = []

    try:
        # Duration guard
        duration = get_video_duration(video_path)
        if duration > MAX_VIDEO_SEC:
            raise ValueError(
                f"Video duration {duration:.0f}s exceeds limit of {MAX_VIDEO_SEC}s."
            )

        # ── Audio / transcript pipeline ────────────────────────────────
        audio_path: Path | None = None
        try:
            audio_path = extract_audio(video_path)
            audio_bytes = audio_path.read_bytes()
            # Re-use audio_parser; modality will be 'audio'
            # We remap modality to 'video_transcript' after parsing
            audio_chunks = parse_audio(
                audio_bytes,
                filename=filename,
                session_id=session_id,
                document_id=document_id,
            )
            for chunk in audio_chunks:
                chunk["metadata"]["modality"] = "video_transcript"
                chunk["metadata"]["source_type"] = ext
                # Regenerate chunk_id to avoid collision with audio_parser ids
                old_id = chunk["chunk_id"]
                new_id = old_id.replace("_audio_", "_vtranscript_")
                chunk["chunk_id"] = new_id
                chunk["metadata"]["chunk_id"] = new_id
            results.extend(audio_chunks)
        except ValueError:
            # No audio track — skip transcript pipeline
            pass
        finally:
            if audio_path:
                audio_path.unlink(missing_ok=True)

        # ── Keyframe pipeline ──────────────────────────────────────────
        frames = extract_keyframes(
            video_path,
            interval_sec=KEYFRAME_INTERVAL_SEC,
            max_frames=MAX_KEYFRAMES,
        )
        unique_frames = _deduplicate_frames(frames)

        if unique_frames:
            pil_images = [img for _, img in unique_frames]
            timestamps = [ts for ts, _ in unique_frames]

            embeddings = image_embedder.embed_images(pil_images)

            for i, (ts, embedding) in enumerate(zip(timestamps, embeddings)):
                chunk_id = f"{document_id}_vkf_{i}"
                meta = build_metadata(
                    document_id=document_id,
                    chunk_id=chunk_id,
                    source_file_name=filename,
                    source_type=ext,
                    modality="video_keyframe",
                    session_id=session_id,
                    start_time=ts,
                    end_time=ts,
                    parser_used="openclip_keyframe",
                )
                results.append(
                    {"chunk_id": chunk_id, "embedding": embedding, "text": "", "metadata": meta}
                )

    finally:
        video_path.unlink(missing_ok=True)

    return results
