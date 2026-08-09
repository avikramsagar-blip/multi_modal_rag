# Flow 2 — Build Status Tracker

> **Purpose:** Track retrieval and chat pipeline build progress against INFRA_SCOPE.md §3.3, §8, §12.7–12.12.
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

## Execution Path

```
user question → query router → embed query → search Chroma (session_id filter)
→ deduplicate chunks → assemble context → Grok API → answer + citations → SQLite
```

---

## Build Checklist

| # | Module | File(s) | Status | Notes |
|---|---|---|---|---|
| 1 | SQLite chat persistence | `storage/sqlite_chat.py` | ✅ | create-on-first-run; 200-message limit; parameterized queries |
| 2 | Query router | `retrieval/router.py` | ✅ | all 5 signal families incl. audio + video; ocr_chunks in default |
| 3 | Vector retriever | `retrieval/search.py` | ✅ | session_id filter; BGE for text-family; OpenCLIP for image-family |
| 4 | Result merger | `retrieval/merge.py` | ✅ | dedup by chunk_id; text/image families separate; drops incomplete chunks |
| 5 | Citation builder | `retrieval/citations.py` | ✅ | source_file_name, page_number, timestamps, low-OCR warning |
| 6 | Grok client | `llm/grok_client.py` | ✅ | all API errors caught; grok_request_id returned |
| 7 | Context assembler | `retrieval/merge.py` | ✅ | MAX_CONTEXT_TOKENS enforced; labeled text + image blocks |
| 8 | Chat UI | `ui/chat.py` | ✅ | container fix applied; input always below messages |
| 9 | App shell wiring | `app.py` | ✅ | Upload + Chat tabs; SQLite init on start |

---

## Active Errors

_No active errors._

---

## Completed Verification Checklist

| Module | Verified by | Date |
|---|---|---|
| Chat UI — message ordering fix | manual test — chat input stays below messages | 2026-08-09 |
| Text + OCR retrieval | query returned results from both text_chunks and ocr_chunks | 2026-08-09 |
| Session-scoped retrieval | chat only shows documents from current session | 2026-08-09 |
| Citation rendering | source filenames shown below answer | 2026-08-09 |
| SQLite persistence | conversation history reloads on page refresh | 2026-08-09 |
| TXT file end-to-end chat | upload → ingest → query → grounded answer with citations | 2026-08-09 |
| PDF file end-to-end chat | upload → ingest → query → OCR content retrieved from ocr_chunks | 2026-08-09 |

---

## Pending Tests (Not Yet Run)

| TC | Description | Blocker |
|---|---|---|
| FTC-03 | Ask question before uploading any file — empty state guard | not yet tested |
| FTC-04 | Session isolation — Session A docs not visible in Session B | not yet tested |
| FTC-05 | Image-intent query after uploading image | deferred |
| FTC-06 | Audio-intent query after uploading audio file | FFmpeg PATH refresh required in Streamlit terminal |
| FTC-07 | Video-intent query — transcript + keyframe collections | FFmpeg PATH refresh required in Streamlit terminal |
| FTC-08 | Mixed-intent query (audio + image keywords) | requires audio/video files ingested |
| FTC-09 | Grok API failure handling | needs simulated key failure |
| FTC-10 | Context token limit truncation | needs large document |

---

## Module Specifications

### 1 — SQLite Chat Persistence (`storage/sqlite_chat.py`)

**Schema fields (INFRA §8.2):**

| Field | Purpose |
|---|---|
| `conversation_id` | groups all messages in a session |
| `message_id` | unique message identifier |
| `role` | user or assistant |
| `message_text` | full message content |
| `created_at` | timestamp |
| `session_id` | Streamlit session linkage |
| `document_scope` | which documents were in scope for this turn |
| `grok_request_id` | auditability of Grok calls |

**Critical requirements:**
- Create DB and tables on first run if not present (§12.10).
- Use parameterized queries — no string interpolation.
- Implement max message count per session to prevent unbounded growth.

---

### 2 — Query Router (`retrieval/router.py`)

**Signal rules (INFRA §8.1):**

| Signal | Trigger keywords | Collections |
|---|---|---|
| Default | any query | `text_chunks` |
| OCR intent | scanned, scan, handwritten, OCR, printed text, text in image | `text_chunks` + `ocr_chunks` |
| Image intent | image, chart, diagram, figure, graph, screenshot, photo, visual, depicted | `text_chunks` + `image_chunks` + `video_keyframe_chunks` |
| Audio intent | audio, recording, call, meeting, transcript, what was said, spoken, voice | `text_chunks` + `audio_transcript_chunks` |
| Video intent | video, clip, frame, keyframe, scene, timestamp, at minute, at second | `text_chunks` + `video_transcript_chunks` + `video_keyframe_chunks` |
| Mixed | multiple signals in one query | all matching collections |

**Edge cases to handle (INFRA §12.7):**
- Mixed intent: trigger all relevant collections and both embedders.
- Ambiguous keyword "transcript": trigger both audio and video transcript collections.
- No signal detected: default to `text_chunks` only.
- Non-English query: default to `text_chunks` (document as known limitation).
- Query references file by name: apply `source_file_name` filter post-routing, not in router.

---

### 3 — Vector Retriever (`retrieval/search.py`)

**Requirements:**
- Apply `session_id == current_session_id` filter on every Chroma query.
- Use BGE embedder for text-family collections (`text_chunks`, `ocr_chunks`, `audio_transcript_chunks`, `video_transcript_chunks`).
- Use OpenCLIP embedder for image-family collections (`image_chunks`, `video_keyframe_chunks`).
- Return empty list (not error) when collection has no session data.
- Detect when all results are empty and surface "No documents indexed in this session" message.

---

### 4 — Result Merger (`retrieval/merge.py`)

**Requirements:**
- Never rank BGE and OpenCLIP scores together — incompatible cosine scale (INFRA §12.8).
- Retrieve top-N per collection family separately, then concatenate as labeled blocks.
- Deduplicate by `chunk_id` before passing to context assembler.
- Drop chunks with `ingestion_status != complete`.
- If image collection returns zero results, fall back to text results only.

---

### 5 — Citation Builder (`retrieval/citations.py`)

**Per chunk, extract:**
- `source_file_name`
- `page_number` (for PDF)
- `start_time` / `end_time` (for audio/video)
- `modality` (label context type)
- `ocr_confidence` (flag low-confidence chunks)

**Critical:** Only present citations from chunks that were actually retrieved and sent to Grok. Never construct citations from Grok output.

---

### 6 — Grok Client (`llm/grok_client.py`)

**Requirements:**
- Read `GROK_API_KEY`, `GROK_API_BASE_URL`, `GROK_MODEL` from `settings` (already in `core/config.py`).
- Enforce `MAX_CONTEXT_TOKENS` before sending (INFRA §12.9).
- Catch all API errors — network, rate limit, key expiry — never crash the app.
- Return `grok_request_id` for SQLite audit trail.

---

### 7 — Context Assembler (extend `retrieval/merge.py`)

**Requirements:**
- Label text-family and image-family results as separate sections in the prompt.
- Group chunks by `document_id` with labeled separators.
- Enforce `MAX_CONTEXT_TOKENS` — truncate top-N before sending.

---

### 8 — Chat UI (`ui/chat.py`)

**Requirements:**
- Use `st.chat_input` and `st.chat_message`.
- Load and display SQLite conversation history on page load.
- Show spinner while waiting for Grok.
- Render citations below each assistant answer.
- Show "No documents indexed in this session" guard when retrieval returns empty.

---

### 9 — App Shell Wiring (`app.py`)

**Requirements:**
- Add Chat tab/section alongside Upload.
- Initialize SQLite DB on app start.
- Disable or message Chat tab until at least one file is ingested in current session.

---

## Flow 2 End-to-End Test Cases

| TC | Input | Expected |
|---|---|---|
| FTC-01 | Ask a question after uploading a TXT | Answer grounded in TXT content; `text_chunks` queried; citation shows filename |
| FTC-02 | Ask a question after uploading a scanned PDF | Answer grounded in OCR content; `ocr_chunks` queried; `ocr_confidence` in citation |
| FTC-03 | Ask question before uploading any file | "No documents indexed" message; no Grok call made |
| FTC-04 | Ask question in Session A; switch to Session B | Session B sees no results from Session A uploads |
| FTC-05 | Ask image-intent query after uploading an image | `image_chunks` + `video_keyframe_chunks` queried; OpenCLIP used for query embedding |
| FTC-06 | Ask audio-intent query after uploading audio | `audio_transcript_chunks` queried; timestamps shown in citations |
| FTC-07 | Ask mixed-intent query | Multiple collections queried; results from both families in context |
| FTC-08 | Ask a question referencing a specific filename | `source_file_name` filter applied; results scoped to that document |
| FTC-09 | Simulate Grok API key failure | Error message shown in UI; app does not crash; SQLite not written |
| FTC-10 | Upload large document producing many chunks | Context truncated to `MAX_CONTEXT_TOKENS`; no Grok error |

---

## Critical Edge Cases (Must Pass Before Launch)

| Priority | Edge case | INFRA ref |
|---|---|---|
| Critical | Empty session — no data indexed | §12.8, §12.12 |
| Critical | Grok API failure | §12.9, §12.12 |
| Critical | Context exceeds token limit | §12.9, §12.12 |
| Critical | SQLite not present on first run | §12.10, §12.12 |
| High | Duplicate chunks from overlapping embeddings | §12.9 |
| High | BGE and OpenCLIP score scales mixed | §12.8 |
| High | Low OCR confidence chunk sent as fact | §12.9 |
| Medium | Non-English query silently defaults to text_chunks | §12.7 |
| Medium | Query references filename not as modality signal | §12.7 |
