# Flow 1 � Build Status Tracker

> **Purpose:** Track what has been built, what is in progress, and what errors are active.
> **Rule:** When an error is resolved, remove it from the Active Errors section. When a module is complete and verified, move it from In Progress ? Built.

---

## Legend

| Symbol | Meaning |
|---|---|
| ? | not started |
| ?? | in progress |
| ? | built and verified |
| ? | blocked � active error |

---

## Build Checklist

| # | Module | File(s) | Status | Notes |
|---|---|---|---|---|
| 1 | Project scaffold | all package dirs + `__init__.py` | ? | |
| 2 | Config and limits | `core/config.py`, `core/limits.py` | ? | GROK/GROQ naming aligned |
| 3 | File validators | `ingestion/validators.py` | ? | extension-MIME mismatch guard added |
| 4 | Chroma client | `vectorstore/chroma_client.py` | ? | two-phase write; collection visibility in sidebar |
| 5 | Text embedder | `embeddings/text_embedder.py` | ? | |
| 6 | Image embedder | `embeddings/image_embedder.py` | ? | |
| 7 | Chunking engine | `ingestion/chunking.py` | ? | dead Iterator import removed |
| 8 | Metadata builder | `ingestion/metadata.py` | ? | |
| 9 | OCR utility | `utils/ocr.py` | ? | replaced PaddleOCR with pytesseract/Tesseract |
| 10 | Text parser | `ingestion/text_parser.py` | ? | |
| 11 | PDF parser | `ingestion/pdf_parser.py` | ? | page numbers 1-based; table row chunking; fitz?pymupdf |
| 12 | Image parser | `ingestion/image_parser.py` | ? | low-resolution OCR skip warning added |
| 13 | Audio parser | `ingestion/audio_parser.py` | ? | |
| 14 | FFmpeg utility + Video parser | `utils/ffmpeg.py`, `ingestion/video_parser.py` | ? | blank/dark frame filtering added |
| 15 | File store | `storage/file_store.py` | ? | |
| 16 | Ingestion router | `ingestion/router.py` | ? | |
| 17 | Chroma write (upsert flow) | `vectorstore/chroma_client.py` (upsert) | ? | |
| 18 | Upload UI + Status UI | `ui/upload.py`, `ui/status.py` | ? | ingestion lock; new session button; per-file status |
| 19 | App shell | `app.py` | ? | preflight checks; sidebar collection list |
| 20 | Centralized logging | `core/logging_config.py` | ? | new � console + file log with structured format |
| 21 | Preflight checks | `core/preflight.py` | ? | new � FFmpeg, Tesseract, module availability checks |
| 22 | Session lifecycle | `core/state.py` | ? | new � start_new_session() for document isolation |

---

## Active Errors

_No active errors._

---

## Completed Verification Checklist

| Module | Verified by | Date |
|---|---|---|
| text_chunks ingestion (TXT) | manual upload � Chroma Cloud UI | 2026-08-09 |
| duplicate detection | manual re-upload same session | 2026-08-09 |
| new session isolation | manual session rotate + re-upload | 2026-08-09 |
| ocr_chunks ingestion (scanned PDF) | manual upload � Chroma Cloud UI | 2026-08-09 |
| two-phase Chroma status write | Chroma dashboard shows ingestion_status: complete | 2026-08-09 |

---

## Post-Build Fixes Applied During Testing

| Fix | File(s) | Reason |
|---|---|---|
| PaddleOCR replaced with pytesseract | `utils/ocr.py`, `requirements.txt` | PaddleOCR 3.7.0 + oneDNN crash on Windows |
| `import fitz` ? `import pymupdf as fitz` | `ingestion/pdf_parser.py` | PyMuPDF deprecated fitz module alias |
| `ffmpeg-python` removed from requirements | `requirements.txt` | unused; subprocess calls binary directly |
| Tesseract path hardcoded for Windows AppData | `utils/ocr.py` | winget installs to user AppData, not system PATH |
| NoneType crash on sidebar collection list | `app.py` | session state pre-set to None; fixed with .get() is None |

---

## Remaining Test Cases (Not Yet Run)

| TC | Description | Blocker |
|---|---|---|
| TC-03 | Digital PDF � selectable text pages | need a born-digital PDF |
| TC-05 | Mixed PDF � text + embedded image | need a mixed-content PDF |
| TC-06 | Image file ingestion | deferred |
| TC-08 | Audio file ingestion | FFmpeg PATH must be refreshed in Streamlit terminal |
| TC-09 | Video file ingestion | FFmpeg PATH must be refreshed in Streamlit terminal |
| TC-13 | Oversized file rejection | need a file larger than MAX_UPLOAD_MB |
| TC-14 | Corrupt file handling | need a crafted corrupt file |
| TC-15 | Session isolation | partially verified — new session uploads are isolated in chat |

---

## Runtime and Troubleshooting Notes

- Logs write to console and `logs/app.log`.
- Preflight warns when `ffmpeg`, `ffprobe`, or `tesseract` are missing.
- Chroma collections shown in Streamlit sidebar after init.
- If collections are missing, check `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE` in `.env`.
- Start Streamlit with PATH refresh to pick up FFmpeg and Tesseract in the same process.
- Flow 2 retrieval must enforce `session_id` filter so users chat only with current-session uploads.
