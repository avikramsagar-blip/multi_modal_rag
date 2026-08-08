# Flow 1 — Build Status Tracker

> **Purpose:** Track what has been built, what is in progress, and what errors are active.
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
| 1 | Project scaffold | all package dirs + `__init__.py` | ✅ | |
| 2 | Config and limits | `core/config.py`, `core/limits.py` | ✅ | depends on: 1 |
| 3 | File validators | `ingestion/validators.py` | ✅ | depends on: 1 |
| 4 | Chroma client | `vectorstore/chroma_client.py` | ✅ | depends on: 2 |
| 5 | Text embedder | `embeddings/text_embedder.py` | ✅ | depends on: 1 |
| 6 | Image embedder | `embeddings/image_embedder.py` | ✅ | depends on: 1 |
| 7 | Chunking engine | `ingestion/chunking.py` | ✅ | depends on: 1 |
| 8 | Metadata builder | `ingestion/metadata.py` | ✅ | depends on: 1 |
| 9 | OCR utility | `utils/ocr.py` | ✅ | depends on: 1 |
| 10 | Text parser | `ingestion/text_parser.py` | ✅ | depends on: 5, 7, 8 |
| 11 | PDF parser | `ingestion/pdf_parser.py` | ✅ | depends on: 5, 6, 7, 8, 9 |
| 12 | Image parser | `ingestion/image_parser.py` | ✅ | depends on: 6, 8, 9 |
| 13 | Audio parser | `ingestion/audio_parser.py` | ✅ | depends on: 5, 7, 8 |
| 14 | FFmpeg utility + Video parser | `utils/ffmpeg.py`, `ingestion/video_parser.py` | ✅ | depends on: 13, 6 |
| 15 | File store | `storage/file_store.py` | ✅ | depends on: 1 |
| 16 | Ingestion router | `ingestion/router.py` | ✅ | depends on: 10, 11, 12, 13, 14 |
| 17 | Chroma write (upsert flow) | `vectorstore/chroma_client.py` (upsert) | ✅ | depends on: 4, 16 |
| 18 | Upload UI + Status UI | `ui/upload.py`, `ui/status.py` | ✅ | depends on: 3, 15, 17 |
| 19 | App shell | `app.py` | ✅ | depends on: 5, 6, 4, 18 |

---

## Active Errors

_No active errors. Errors will be logged here during development with module name, error message, and root cause._

| Module | Error | Root cause | Status |
|---|---|---|---|
| — | — | — | — |

---

## Completed Verification Checklist

_Modules signed off after manual or automated test. Moved here once verified._

| Module | Verified by | Date |
|---|---|---|
| — | — | — |

---

## Flow 1 End-to-End Test Cases

These test cases are run after all 19 modules above are ✅. Each test must produce a verifiable result in Chroma Cloud.

---

### TC-01 — Plain text file ingestion

**Input:** upload a `.txt` file containing at least 3 paragraphs of English text
**Expected:**
- ingestion completes without error
- UI shows "Ready to chat" indicator
- Chroma collection `text_chunks` contains records with `source_file_name` matching the uploaded filename
- each record has `session_id`, `document_id`, `chunk_id`, `modality: text`, `ingestion_status: complete`
- chunk count ≥ 1

---

### TC-02 — Markdown file ingestion

**Input:** upload a `.md` file
**Expected:**
- same as TC-01 but `source_type: md`
- `text_chunks` collection updated

---

### TC-03 — Digital PDF ingestion (text-only pages)

**Input:** upload a born-digital PDF (selectable text, no scanned pages)
**Expected:**
- all pages classified as `digital_text_page`
- `text_chunks` collection updated with one or more records
- metadata contains correct `page_number` per chunk
- `parser_used: pymupdf`

---

### TC-04 — Scanned PDF ingestion (OCR path)

**Input:** upload a PDF where pages contain no selectable text (scanned)
**Expected:**
- pages classified as `scanned_page`
- `ocr_chunks` collection updated
- each record has `ocr_confidence` score in metadata
- `parser_used: paddleocr`

---

### TC-05 — Mixed PDF ingestion (text + embedded image)

**Input:** upload a PDF with at least one page containing both selectable text and an embedded image (e.g. a report with a chart)
**Expected:**
- text portion → `text_chunks` or `ocr_chunks` depending on page type
- image portion → `image_chunks`
- both records share the same `document_id` and `page_number`

---

### TC-06 — Image file ingestion

**Input:** upload a `.jpg` or `.png` file (a photo or diagram)
**Expected:**
- `image_chunks` collection updated with one record
- `modality: image`
- if image contains text: `ocr_chunks` also updated with corresponding text chunk

---

### TC-07 — Image file with text (OCR path)

**Input:** upload an image that clearly contains readable printed text (e.g. a screenshot of a document)
**Expected:**
- `ocr_chunks` updated with extracted text
- `ocr_confidence` score present and > 0
- `image_chunks` also updated with visual embedding

---

### TC-08 — Audio file ingestion

**Input:** upload an `.mp3` or `.wav` file containing clear spoken English (30–60 seconds)
**Expected:**
- `audio_transcript_chunks` collection updated
- transcript text is non-empty
- `start_time` and `end_time` present in metadata per chunk
- `modality: audio`

---

### TC-09 — Video file ingestion

**Input:** upload a short `.mp4` file (under 60 seconds) containing speech and visual content
**Expected:**
- `video_transcript_chunks` updated with transcript segments
- `video_keyframe_chunks` updated with at least 1 keyframe embedding
- keyframe records have `timestamp` in metadata
- transcript records have `start_time` and `end_time`

---

### TC-10 — Duplicate file detection

**Input:** upload the same file twice in the same session
**Expected:**
- second upload is rejected before ingestion starts
- UI shows "File already uploaded in this session" message
- Chroma collection is NOT written to twice for the same file

---

### TC-11 — Invalid file type rejection

**Input:** upload a `.exe` or `.docx` file
**Expected:**
- file is rejected at validation stage
- clear error message shown in UI
- no data written to Chroma

---

### TC-12 — Zero-byte file rejection

**Input:** upload an empty file (0 bytes)
**Expected:**
- rejected at validation stage with appropriate error message
- no data written to Chroma

---

### TC-13 — Oversized file rejection

**Input:** upload a file larger than the configured `MAX_UPLOAD_MB`
**Expected:**
- rejected before parsing starts
- UI shows file size error

---

### TC-14 — Corrupt file handling

**Input:** upload a file with `.pdf` extension but corrupted/invalid bytes
**Expected:**
- parser fails gracefully
- error is caught and shown in UI
- no partial data written to Chroma
- `ingestion_status` never set to `complete`

---

### TC-15 — Session isolation

**Input:** upload a file in session A. Open a new session (session B). Ask a question.
**Expected:**
- session B retrieval returns no results (empty state message)
- session A data is not visible to session B

---

## Notes

- All Chroma verification steps require direct inspection of the Chroma Cloud dashboard or a Python script querying the collection with `collection.get()` filtered by `session_id`.
- Test cases TC-10 through TC-14 are validation tests and should pass before any ingestion logic is reached.
- TC-15 requires Flow 2 to be partially built (query step only).
