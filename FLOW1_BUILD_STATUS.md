# Flow 1 — Build Status Tracker

> **Purpose:** Track Flow 1 ingestion progress against PROJECT_SCOPE.md and INFRA_SCOPE.md.
> **Rule:** When an error is resolved, remove it from the Active Errors section. When a module is complete and verified, move it from In Progress → Built.

---

## Legend

| Symbol | Meaning |
|---|---|
| ⬜ | not started |
| 🔄 | in progress |
| ✅ | built and verified |
| ❌ | blocked — active error |

---

## Build Checklist

| # | Module | File(s) | Status | Notes |
|---|---|---|---|---|
| 1 | Project scaffold | `core/`, `ingestion/`, `retrieval/`, `ui/`, `vectorstore/` | ✅ | package structure and imports are present |
| 2 | Config and limits | `core/config.py`, `core/limits.py` | ✅ | GROK/GROQ naming is supported via fallback values |
| 3 | File validators | `ingestion/validators.py` | ✅ | extension/MIME mismatch guard and empty/size checks |
| 4 | Chroma client | `vectorstore/chroma_client.py` | ✅ | fixed collections created and chunk writes are two-phase |
| 5 | Text embedder | `embeddings/text_embedder.py` | ✅ | BGE embedding path is wired |
| 6 | Image embedder | `embeddings/image_embedder.py` | ✅ | OpenCLIP embedding path is wired |
| 7 | Chunking engine | `ingestion/chunking.py` | ✅ | unit-tested and used by text/audio parsers |
| 8 | Metadata builder | `ingestion/metadata.py` | ✅ | metadata includes document_id, chunk_id, session_id, modality |
| 9 | OCR utility | `utils/ocr.py` | ✅ | Tesseract-based OCR path is implemented |
| 10 | Text parser | `ingestion/text_parser.py` | ✅ | text files are parsed and chunked |
| 11 | PDF parser | `ingestion/pdf_parser.py` | ✅ | page-numbered parsing and OCR/text handling are implemented |
| 12 | Image parser | `ingestion/image_parser.py` | ✅ | OCR + image embedding pipeline is implemented |
| 13 | Audio parser | `ingestion/audio_parser.py` | 🔄 | implemented; end-to-end transcription still depends on the local runtime |
| 14 | FFmpeg utility + Video parser | `utils/ffmpeg.py`, `ingestion/video_parser.py` | 🔄 | implemented; FFmpeg availability affects full runtime verification |
| 15 | File store | `storage/file_store.py` | ✅ | staging, sanitization, and cleanup helpers are in place |
| 16 | Ingestion router | `ingestion/router.py` | ✅ | dispatches to the correct parser for each file type |
| 17 | Chroma write (upsert flow) | `vectorstore/chroma_client.py` | ✅ | chunk writes are persisted and finalized with `ingestion_status=complete` |
| 18 | Upload UI + Status UI | `ui/upload.py`, `ui/status.py` | ✅ | upload progress, duplicate handling, and per-file status are implemented |
| 19 | App shell | `app.py` | ✅ | upload/chat tabs and startup initialization are wired |
| 20 | Centralized logging | `core/logging_config.py` | ✅ | structured logging to console and file is configured |
| 21 | Preflight checks | `core/preflight.py` | ✅ | FFmpeg, Tesseract, and import availability checks are present |
| 22 | Session lifecycle | `core/state.py` | ✅ | new-session isolation resets per-session state |

---

## Active Errors

_No active errors._

---

## Completed Verification Checklist

| Module | Verified by | Date |
|---|---|---|
| Chunking + metadata + validators | `pytest -q` (8 passed) | 2026-08-10 |
| Text file ingestion path | code review + parser/router wiring | 2026-08-10 |
| Session isolation | code review + new-session reset logic | 2026-08-10 |
| Chroma write finalization | code review of two-phase write flow | 2026-08-10 |

---

## Remaining Runtime Verification

| Scenario | Blocker |
|---|---|
| Audio transcription end-to-end | local Faster-Whisper runtime and model download |
| Video transcription/keyframe extraction end-to-end | local FFmpeg installation / PATH |
| OCR-heavy PDF/image runtime validation | local Tesseract installation |
