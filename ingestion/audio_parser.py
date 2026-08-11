"""
ingestion/audio_parser.py

Parses audio files (mp3, wav, m4a, flac, ogg).
Transcribes with Faster-Whisper (base model).
Produces transcript chunks → audio_transcript_chunks collection.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from core.limits import MAX_AUDIO_SEC, MIN_TRANSCRIPT_WORDS
from core.logging_config import get_logger
from ingestion.chunking import chunk_text
from ingestion.metadata import build_metadata

logger = get_logger(__name__)

_whisper_model = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        # base model for MVP; device="cpu" for Streamlit Cloud compatibility
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


class AudioDurationExceeded(ValueError):
    """Raised when an audio file exceeds MAX_AUDIO_SEC. Caller may treat this
    as a user-facing validation error rather than a crash."""


def parse_audio(
    file_bytes: bytes,
    filename: str,
    session_id: str,
    document_id: str,
) -> list[dict]:
    """
    Transcribe an audio file and return chunk dicts.

    Each chunk captures a contiguous set of transcript sentences with
    start_time and end_time from Whisper segment timestamps.

    Never raises for transcription failures (model load errors, corrupt
    audio, unsupported codecs, OOM, etc.) — those are logged and an empty
    list is returned so a single bad file can't take down ingestion.

    Raises AudioDurationExceeded if the file is longer than MAX_AUDIO_SEC —
    this is treated as an expected validation error, not a crash, and callers
    (e.g. app.py's upload dispatcher) should catch it and show the user a
    clear message.
    """
    text_embedder = st.session_state["text_embedder"]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "audio"
    logger.info("Parsing audio | file=%s", filename)

    # Write to a temp file so Whisper can read it
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        try:
            model = _get_whisper()
            segments, info = model.transcribe(
                tmp_path,
                beam_size=5,
                condition_on_previous_text=False,
            )
        except Exception:
            # Model load failure, corrupt/unsupported audio, OOM, etc.
            logger.exception("Whisper transcription failed | file=%s", filename)
            return []

        # Enforce duration limit — intentional validation error, re-raised
        # so the caller can decide how to surface it (not swallowed here).
        if info.duration > MAX_AUDIO_SEC:
            logger.warning(
                "Audio exceeds duration limit | file=%s | duration=%.2f | max=%d",
                filename,
                info.duration,
                MAX_AUDIO_SEC,
            )
            raise AudioDurationExceeded(
                f"Audio duration {info.duration:.0f}s exceeds limit of {MAX_AUDIO_SEC}s."
            )

        try:
            seg_list = list(segments)
        except Exception:
            # Segment iteration can itself fail mid-stream on malformed audio
            logger.exception("Failed while reading Whisper segments | file=%s", filename)
            return []
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not seg_list:
        return []

    # Build timestamp-aware chunks
    # Group consecutive segments into chunks of ~CHUNK_SIZE_TOKENS
    results: list[dict] = []
    buffer_text: list[str] = []
    buffer_start: float = seg_list[0].start
    buffer_end: float = seg_list[0].end
    chunk_index = 0

    def _flush_buffer(buf_text, buf_start, buf_end, idx):
        combined = " ".join(buf_text).strip()
        word_count = len(combined.split())
        if word_count < MIN_TRANSCRIPT_WORDS:
            logger.warning(
                "Transcript buffer dropped due to low word count | file=%s | words=%d",
                filename,
                word_count,
            )
            return None
        sub_chunks = chunk_text(combined)
        out = []
        for sub_i, sub_chunk in enumerate(sub_chunks):
            cid = f"{document_id}_audio_{idx}_{sub_i}"
            try:
                [embedding] = text_embedder.embed([sub_chunk])
            except Exception:
                logger.exception(
                    "Embedding failed for audio chunk — skipped | file=%s | chunk_id=%s",
                    filename,
                    cid,
                )
                continue
            meta = build_metadata(
                document_id=document_id,
                chunk_id=cid,
                source_file_name=filename,
                source_type=ext,
                modality="audio",
                session_id=session_id,
                start_time=round(buf_start, 2),
                end_time=round(buf_end, 2),
                parser_used="faster_whisper",
            )
            out.append({"chunk_id": cid, "embedding": embedding, "text": sub_chunk, "metadata": meta})
        return out

    SEGMENT_BUFFER_LIMIT = 10  # flush every N segments

    for seg in seg_list:
        buffer_text.append(seg.text.strip())
        buffer_end = seg.end

        if len(buffer_text) >= SEGMENT_BUFFER_LIMIT:
            flushed = _flush_buffer(buffer_text, buffer_start, buffer_end, chunk_index)
            if flushed:
                results.extend(flushed)
                chunk_index += 1
            buffer_text = []
            buffer_start = seg.end

    # Flush remaining
    if buffer_text:
        flushed = _flush_buffer(buffer_text, buffer_start, buffer_end, chunk_index)
        if flushed:
            results.extend(flushed)

    logger.info("Audio parsed | file=%s | chunks=%d", filename, len(results))
    return results