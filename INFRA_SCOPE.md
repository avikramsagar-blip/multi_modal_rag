# Infrastructure Scope: Single-Service Multimodal RAG with Streamlit

## 1) Objective

This document defines the **infrastructure scope** for the multimodal RAG chatbot. All constraints below are locked for MVP.

| Constraint | Decision |
|---|---|
| UI and application runtime | Streamlit — single deployable application |
| Preprocessing, chunking, embeddings | inside the same application |
| Chat history persistence | SQLite inside the same application |
| External dependencies | Chroma Cloud (vector DB) and Grok API only |
| OCR, transcription, frame extraction | inside the same application — no external API |
| Vector DB type | cloud-based, open-source ecosystem |

> **Design constraint:** OCR, transcription, video extraction, and embeddings running inside the same Streamlit-hosted process will increase CPU, memory, and latency pressure. This architecture is valid for MVP and controlled workloads, but file size, concurrency, and model loading must be tightly controlled.

---

## 2) Architecture Decisions

### 2.1 Single application scope

One Streamlit-based application handles all of the following:

- file upload and validation
- parsing (text, PDF, image, audio, video)
- OCR and transcription
- video frame extraction
- metadata extraction
- chunking
- embedding generation
- vector DB writes
- query routing and retrieval orchestration
- Grok prompt assembly and answer rendering
- SQLite chat history persistence

### 2.2 External boundary

Only two external calls are permitted:

| External service | Purpose |
|---|---|
| Chroma Cloud | vector storage and similarity search |
| Grok API | final answer generation |

No external OCR API, no external transcription API, no external embedding API.

### 2.3 Internal module structure

The application is one deployable unit but organized as separate internal modules:

```text
app.py
ui/
  upload.py
  chat.py
  status.py
core/
  config.py
  limits.py
  state.py
ingestion/
  router.py
  validators.py
  text_parser.py
  pdf_parser.py
  image_parser.py
  audio_parser.py
  video_parser.py
  metadata.py
  chunking.py
embeddings/
  text_embedder.py
  image_embedder.py
vectorstore/
  chroma_client.py
retrieval/
  search.py
  router.py
  merge.py
  citations.py
llm/
  grok_client.py
storage/
  sqlite_chat.py
  file_store.py
utils/
  ffmpeg.py
  ocr.py
```

---

## 3) Internal Components

### 3.1 Shared components

| Component | Purpose | Scope |
|---|---|---|
| Streamlit UI | upload, progress, chat, preview | mandatory |
| Config layer | API keys, DB endpoint, model names, limits | mandatory |
| File storage layer | temporary file handling and local staging | mandatory |
| Metadata layer | per-document and per-chunk metadata | mandatory |
| SQLite layer | chat history persistence | mandatory |
| Logging layer | ingestion errors, retrieval latency, Grok failures | mandatory |

### 3.2 Flow 1 — Ingestion components

| Component | Purpose | Scope |
|---|---|---|
| Upload handler | receive files from UI | mandatory |
| File validator | extension, MIME, size, corruption checks | mandatory |
| File router | txt / pdf / image / audio / video routing | mandatory |
| Text parser | plain text, markdown, CSV, JSON parsing | mandatory |
| PDF parser | digital PDF text extraction via PyMuPDF | mandatory |
| OCR processor | scanned PDF and image text extraction via PaddleOCR | mandatory |
| Audio transcription processor | audio to transcript via Faster-Whisper | mandatory if audio is in scope |
| Video processor | extract audio and keyframes via FFmpeg | mandatory if video is in scope |
| Metadata builder | page number, timestamp, parser type, OCR confidence | mandatory |
| Chunking engine | sentence-boundary-aware chunking with overlap | mandatory |
| Embedding engine | BGE (text) and OpenCLIP (image) — both inside the app | mandatory |
| Vector DB writer | push vectors and metadata payloads to Chroma Cloud | mandatory |

### 3.3 Flow 2 — Retrieval components

| Component | Purpose | Scope |
|---|---|---|
| Chat handler | accept user messages from Streamlit UI | mandatory |
| Query router | deterministic keyword-based collection selector | mandatory |
| Vector retriever | search Chroma Cloud collections | mandatory |
| Filter layer | session, document, modality metadata filters | mandatory |
| Context builder | assemble ranked chunks for Grok prompt | mandatory |
| Grok client | send context + query to Grok, receive answer | mandatory |
| Citation builder | format source file, page, timestamp per answer | mandatory |
| SQLite chat writer | persist conversation turns and session state | mandatory |

---

## 4) Parsers and Embedding Models

### 4.1 Parser and model footprint

All sizes are approximate operational footprints. Actual values vary by OS, Python environment, and model variant.

| Area | Tool / Model | Role | Approx footprint | MVP decision |
|---|---|---|---|---|
| PDF parsing | PyMuPDF | digital PDF text extraction | tens of MB; no model download | use |
| OCR | PaddleOCR | scanned PDF and image text extraction | 100 MB – 300 MB+ with OCR models | use with file limits |
| Audio transcription | Faster-Whisper | speech-to-text for audio and video | `base` ~150 MB, `small` ~500 MB | start with `base` |
| Video extraction | FFmpeg | audio extraction and keyframe capture | tens to low hundreds of MB | use |
| Text embeddings | `BAAI/bge-small-en-v1.5` | text, OCR text, transcript embeddings | ~100 MB – 200 MB | primary text model |
| Image embeddings | OpenCLIP ViT-B/32 | image and video keyframe embeddings | few hundred MB | primary image model |

### 4.2 Embedding model strategy

Two models are used — not one universal model.

| Model | Handles |
|---|---|
| `BAAI/bge-small-en-v1.5` (BGE) | plain text chunks, OCR text chunks, audio transcript chunks, video transcript chunks |
| OpenCLIP ViT-B/32 | uploaded images, PDF-embedded image blocks, video keyframes |

Both models are loaded once at app start and cached in `st.session_state`. They are not reloaded per request.

---

## 5) File-Type Processing Flows

### 5.1 Text files (txt, md, csv, json)

1. load file and normalize encoding
2. split into logical text blocks
3. chunk with sentence-boundary splitting
4. embed with BGE text model
5. write to `text_chunks` collection in Chroma

### 5.2 PDF files

Per-page classification — classify each page individually, not the document as a whole:

| Page type | Detection | Processing |
|---|---|---|
| `digital_text_page` | character count ≥ threshold via PyMuPDF | extract text, chunk, embed with BGE |
| `scanned_page` | character count < threshold | render to image, run PaddleOCR, embed text with BGE |
| `mixed_text_image_page` | text above threshold AND image blocks detected | extract text with PyMuPDF + run OCR and OpenCLIP on image blocks |
| `image_only_page` | page is one large embedded image | run PaddleOCR for text + OpenCLIP for image embedding |
| `table_heavy_page` | structured grid detected | chunk by row if parseable; fall back to OCR |

Text output → `text_chunks` or `ocr_chunks`
Image output → `image_chunks`
All records linked by `document_id` and `page_number`.

### 5.3 Image files (jpg, png, tiff, webp)

1. load image; convert RGBA to RGB if needed
2. check resolution — skip OCR if below minimum
3. run PaddleOCR if text is likely present; store result in `ocr_chunks`
4. generate OpenCLIP embedding regardless
5. store image embedding in `image_chunks`
6. link both records by `source_file_name` and `document_id`

### 5.4 Audio files (mp3, wav, m4a, flac)

1. load audio file
2. transcribe with Faster-Whisper (`base` model for MVP)
3. segment transcript by timestamps
4. chunk transcript segments
5. embed with BGE text model
6. store in `audio_transcript_chunks`

MVP constraint: transcript-first only; no raw audio embedding.

### 5.5 Video files (mp4, mkv, avi, mov)

1. load video and check for audio stream presence
2. extract audio track via FFmpeg → transcribe → store in `video_transcript_chunks`
3. extract keyframes at adaptive interval (e.g. 1 frame per N seconds)
4. discard blank or near-duplicate frames
5. embed remaining keyframes with OpenCLIP → store in `video_keyframe_chunks`
6. link transcript chunks and keyframe records by `timestamp`

MVP constraint: no dedicated video-language models; transcript + keyframe only.

---

## 6) Chroma Cloud Collection Design

### 6.1 Collection layout

| Collection | Embedding model | Content |
|---|---|---|
| `text_chunks` | BGE | born-digital text from txt, md, csv, json, digital PDF pages |
| `ocr_chunks` | BGE | OCR-extracted text from scanned PDFs and images |
| `image_chunks` | OpenCLIP | uploaded images and PDF-embedded image blocks |
| `audio_transcript_chunks` | BGE | audio file transcription segments |
| `video_transcript_chunks` | BGE | video audio transcription segments |
| `video_keyframe_chunks` | OpenCLIP | video keyframe image embeddings |

Separate collections are required because BGE and OpenCLIP output different embedding dimensions. Mixing them in one collection is not valid.

### 6.2 Metadata stored per record

Every record in every collection includes:

| Field | Purpose |
|---|---|
| `document_id` | unique identifier for the source document |
| `chunk_id` | unique identifier for this chunk |
| `source_file_name` | original uploaded file name |
| `source_type` | file extension type |
| `modality` | text / ocr / image / audio / video\_transcript / video\_keyframe |
| `page_number` | for PDF and multi-page sources |
| `start_time` | for audio and video segments |
| `end_time` | for audio and video segments |
| `parser_used` | which parser produced this chunk |
| `ocr_confidence` | OCR confidence score where applicable |
| `session_id` | Streamlit session identifier for scoping retrieval |
| `ingestion_status` | pending / complete — to detect partial ingestion |

### 6.3 Chroma Cloud limitations

- Chroma Cloud is not a forever-free tier; new accounts receive starting credits
- If future requirements need multi-vector-per-record or named-vector patterns, another DB may suit better

---

## 7) Flow 1 — Ingestion Execution Path

**upload → validation → classify → parse → chunk → embed → write to Chroma → mark ready**

1. user uploads file in Streamlit UI
2. app validates: MIME type, extension, file size, byte integrity, duplicate hash check
3. app routes file to the correct parser based on type
4. app extracts content (text, OCR text, image blocks, transcript, keyframes)
5. app builds per-chunk metadata
6. app chunks content with sentence-boundary-aware splitting
7. app generates embeddings (BGE or OpenCLIP depending on content type)
8. app writes embeddings + metadata to the correct Chroma collection
9. app sets `ingestion_status = complete` in metadata
10. UI shows ready-to-chat indicator

### 7.1 Operational limits for Flow 1 (MVP)

| Limit | Reason |
|---|---|
| max upload file size | prevent memory exhaustion |
| max PDF page count | prevent OCR blocking the app for too long |
| max image resolution | prevent PIL/OpenCLIP memory spikes |
| max audio duration | prevent transcription from blocking the UI |
| max video duration | prevent FFmpeg + transcription from blocking the UI |
| max files per upload batch | bound total ingestion time per session |
| one ingestion job per user session at a time | prevent concurrent heavy processing |

---

## 8) Flow 2 — Retrieval Execution Path

**user question → route → embed → search Chroma → assemble context → Grok → answer + citations → store in SQLite**

1. user sends question in Streamlit chat UI
2. query router inspects query for modality intent signals
3. router selects the set of Chroma collections to search
4. app embeds query with BGE (for text collections) and/or OpenCLIP (for image collections)
5. app queries selected Chroma collections filtered by `session_id`
6. app deduplicates chunks by `chunk_id`
7. app assembles context — text-family and image-family results labeled separately
8. app enforces max context token count before sending to Grok
9. app sends context + query to Grok API
10. app renders answer with citations (source file, page, timestamp)
11. app writes conversation turn to SQLite

### 8.1 Query router — deterministic signal rules

| Signal category | Trigger keywords | Collections searched |
|---|---|---|
| Default (always) | any query | `text_chunks` |
| OCR intent | scanned, scan, handwritten, OCR, printed text, text in image | `text_chunks` + `ocr_chunks` |
| Image intent | image, chart, diagram, figure, graph, screenshot, photo, visual, depicted | `text_chunks` + `image_chunks` + `video_keyframe_chunks` |
| Audio intent | audio, recording, call, meeting, transcript, what was said, spoken, voice | `text_chunks` + `audio_transcript_chunks` |
| Video intent | video, clip, frame, keyframe, scene, timestamp, at minute, at second | `text_chunks` + `video_transcript_chunks` + `video_keyframe_chunks` |
| Mixed intent | multiple signals in one query | all matching collections; results merged before context assembly |

### 8.2 SQLite chat schema fields

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

---

## 9) Infra Advantages and Limitations

### Advantages

- one deployable application; no multi-service orchestration
- fewer moving parts; easier to develop, debug, and deploy
- only two external integrations (Chroma Cloud and Grok)
- all preprocessing logic lives in one codebase
- cloud DB persistence is independent of Streamlit container lifecycle
- open-source parsers and embedding models; no external embedding API cost

### Limitations

- Streamlit runtime bears the full preprocessing workload (OCR, transcription, embeddings)
- OCR and audio/video transcription can block UI responsiveness in MVP
- embedding models loaded in-process increase memory footprint
- SQLite is not suitable for high write concurrency beyond MVP scale
- Chroma Cloud free tier is credit-based, not permanent
- scaling ingestion and chat independently requires a different architecture later

---

## 10) Locked MVP Stack

| Layer | Choice |
|---|---|
| UI and application shell | Streamlit |
| PDF parsing | PyMuPDF |
| OCR | PaddleOCR |
| Audio transcription | Faster-Whisper (`base` model) |
| Video extraction | FFmpeg |
| Text embedding model | `BAAI/bge-small-en-v1.5` |
| Image embedding model | OpenCLIP ViT-B/32 |
| Vector DB | Chroma Cloud |
| LLM answer generation | Grok API |
| Chat history | SQLite (inside same application) |

### MVP build order

| Step | Work |
|---|---|
| 1 | Streamlit upload and chat shell with session state |
| 2 | SQLite chat history — create DB and schema on first run |
| 3 | Chroma Cloud connection and collection initialization |
| 4 | text file parsing, chunking, BGE embeddings, Chroma write |
| 5 | digital PDF parsing with PyMuPDF |
| 6 | PDF page classification and PaddleOCR for scanned pages |
| 7 | image file OCR and OpenCLIP embedding |
| 8 | deterministic query router and Chroma retrieval |
| 9 | context assembly and Grok answer generation with citations |
| 10 | audio transcription with Faster-Whisper |
| 11 | video keyframe and transcript pipeline with FFmpeg |

### Minimum hardware for local development

| Requirement | Reason |
|---|---|
| Modern CPU (4+ cores recommended) | OCR, FFmpeg, embedding all run in-process |
| 16 GB RAM minimum | OCR + embedding models loaded together |
| Adequate disk space | temp files: PDFs, audio tracks, keyframes, SQLite, model caches |

---

## 11) Web3

Web3 is **not required** for this scope. None of the described components need blockchain or wallet integration.

---

## 12) Edge Cases: Full Consolidated Reference

This section captures every edge case and design decision discussed during scoping. These are implementation constraints that must be handled before the application can be considered production-ready for MVP.

---

### 12.1 Flow 1 — File Upload and Validation Edge Cases

| Edge case | What can go wrong | How to handle it |
|---|---|---|
| File extension mismatch | A `.pdf` file is actually a renamed `.jpg` | Validate using MIME type (magic bytes), not just file extension |
| Zero-byte file uploaded | Empty file passes extension check | Reject files with zero or near-zero byte size before parsing begins |
| Corrupt file | PDF or audio file is truncated or malformed | Wrap parsers in try/except; fail gracefully with a user-visible message |
| Duplicate upload in same session | Same file uploaded twice | Check by file hash (MD5/SHA256) before parsing; skip and notify user |
| Unsupported file variant | `.doc` uploaded instead of `.docx`, or `.ogg` audio | Detect at MIME-check stage; reject with a clear list of supported types |
| Upload timeout | Large file times out during upload via Streamlit | Enforce max size before upload completes; Streamlit has no streaming upload natively |
| Filename with special characters | Spaces, Unicode, or path-separator characters in file name | Sanitize file name before writing to disk; store original name in metadata |

---

### 12.2 Flow 1 — PDF Mixed-Content Edge Cases

This is the most complex parser edge case in the system. A single PDF can contain:

- born-digital selectable text
- embedded raster images
- scanned pages with no selectable text
- mixed pages with both selectable text and embedded images
- tables rendered as images, not HTML
- pages with only whitespace or decorative elements

#### Page-level classification strategy

Do **not** classify at the document level. Classify at the **page level**.

| Page type | Detection rule | Processing strategy |
|---|---|---|
| `digital_text_page` | text extraction yields above a minimum character threshold | use PyMuPDF text extraction only |
| `scanned_page` | text extraction yields below threshold; page is a rasterised image | render page to image, run PaddleOCR |
| `mixed_text_image_page` | text extraction yields some text AND page contains embedded image blocks | extract text from PyMuPDF, extract image blocks separately, run image through OpenCLIP, OCR if needed |
| `image_only_page` | entire page is one large embedded image, no selectable text | render to image, run PaddleOCR for text + OpenCLIP for image embedding |
| `table_heavy_page` | page has structured grid/table rendering detected | mark as table type in metadata; chunk by table rows if parseable, fall back to OCR |

#### How to detect page type

Use PyMuPDF to extract text per page. Measure character count:

- if `len(text.strip()) >= minimum_threshold` → treat as `digital_text_page`
- if `len(text.strip()) < minimum_threshold` → render page as image → classify as `scanned_page` or `image_only_page`
- if text above threshold **and** page has image blocks detected by PyMuPDF → `mixed_text_image_page`

#### Edge case: OCR confidence below threshold

After running OCR on a scanned page, confidence may be too low to be useful.

- Store the raw OCR text but tag with `ocr_confidence` score in metadata
- If confidence is below a defined threshold (e.g. < 0.5), flag the chunk as low-confidence
- Low-confidence chunks can still be stored but should be ranked lower or filtered in retrieval

#### Edge case: Image blocks inside text PDF

Some PDFs embed charts, figures, or logos inside otherwise digital pages.

- Use PyMuPDF's image extraction API to pull embedded image blocks
- Each image block becomes a separate pipeline: OCR (if it contains text) and OpenCLIP embedding
- Store image embeddings in `image_chunks` collection
- Store OCR text from that image block in `ocr_chunks`
- Link both by `page_number` and `document_id` in metadata

---

### 12.3 Flow 1 — Image File Edge Cases

| Edge case | What can go wrong | How to handle it |
|---|---|---|
| Image with no readable text | Photo or diagram with no text content | Skip OCR step, proceed directly to OpenCLIP embedding; store with `ocr_text: null` in metadata |
| Very low resolution image | Blurry scan or thumbnail; OCR yields garbage | Apply minimum resolution check before OCR; warn in metadata |
| Image file is a chart or graph | OCR reads axis labels only; misses the visual meaning | Always generate both OCR text chunk (if any) and image embedding regardless |
| Large image (e.g. full A0 poster scan) | Memory pressure from loading full image into PIL/OpenCLIP | Resize before embedding; store original dimensions in metadata |
| Multi-page TIFF | A single TIFF file contains multiple pages | Iterate over frames, treat each frame as a separate page |
| Transparent or RGBA images | OpenCLIP may not handle alpha channel correctly | Convert RGBA to RGB before embedding |

---

### 12.4 Flow 1 — Audio File Edge Cases

| Edge case | What can go wrong | How to handle it |
|---|---|---|
| Audio file is silence or noise | Faster-Whisper produces empty or junk transcript | Check transcript word count after transcription; discard if below minimum threshold |
| Audio is in a non-English language | Default Whisper model may misread non-English speech | For MVP, mark as unsupported or allow user to specify language; Faster-Whisper supports multilingual |
| Audio has multiple speakers | Transcript is a flat stream; no speaker labels | For MVP, do not diarize; store as flat text; document this limitation clearly |
| Audio file is very long (e.g. 2-hour podcast) | Transcription takes minutes; app appears frozen | Enforce max audio duration limit; show progress indicator in Streamlit |
| Audio is low bitrate or compressed heavily | Transcription quality degrades | Store audio quality metadata; warn user if bitrate is below a threshold |
| Audio has background noise | Whisper picks up noise as words | Faster-Whisper handles noise reasonably at `base` and `small` model size; no special handling for MVP |

---

### 12.5 Flow 1 — Video File Edge Cases

| Edge case | What can go wrong | How to handle it |
|---|---|---|
| Video has no audio track | FFmpeg audio extraction yields nothing | Check for audio stream presence before transcription; skip audio pipeline, continue with keyframes |
| Video is entirely static (slideshow) | Keyframes are identical or near-identical | Use perceptual hash or frame diff to deduplicate similar keyframes before embedding |
| Video is very long | Too many keyframes extracted; memory pressure | Enforce max video duration; cap keyframe count; use adaptive interval (e.g. 1 keyframe per N seconds) |
| Video codec is unsupported by FFmpeg | FFmpeg returns error | Catch FFmpeg errors; reject file; show user a list of supported container formats |
| Keyframe is mostly black/blank | Dark scene transitions captured as keyframes | Apply minimum brightness check before embedding; discard blank frames |
| Video without meaningful visual content | Screencast or audio-only with static background | Embed keyframes anyway; transcript will carry the semantic weight |

---

### 12.6 Flow 1 — Chunking Edge Cases

| Edge case | What can go wrong | How to handle it |
|---|---|---|
| Chunk is too small | Single-word or single-sentence chunk; embedding is not meaningful | Enforce minimum chunk token count; merge with adjacent chunk if below threshold |
| Chunk is too large | Entire document is one chunk; retrieval returns too much context | Enforce maximum chunk token count; split at sentence or paragraph boundary |
| Chunk splits in the middle of a sentence | Semantic meaning is broken | Use sentence-boundary-aware splitting; do not split mid-sentence on fixed character count |
| Table row split across chunks | Row data is severed | Detect table regions from PDF/OCR and keep rows intact as one chunk |
| Chunk from scanned page has no clean paragraph break | OCR text has no structure markers | Fall back to fixed-size chunking with overlap when structure is not detectable |
| Overlap creates duplicate context in retrieval | Overlapping chunks cause repeated context to Grok | Deduplicate by `chunk_id` at retrieval time; do not send the same chunk twice |

---

### 12.7 Flow 2 — Deterministic Query Router Edge Cases

The router uses keyword signals to select Chroma collections (full signal table in §8.1). The following edge cases apply.

#### Edge case: mixed intent query

Example: *"What image was discussed in the call?"*

- Signals both `image` and `audio` intent
- Router must select: `text_chunks` + `image_chunks` + `audio_transcript_chunks` + `video_keyframe_chunks`
- Both BGE and OpenCLIP searches are triggered
- Results merged by relevance score before assembly

#### Edge case: ambiguous keyword overlap

The word **"transcript"** appears in both audio and video signal lists.

- A query like *"summarise the transcript"* without a modality qualifier triggers both audio and video transcript collections
- This is acceptable for MVP: returning more relevant chunks is safer than missing them
- If precision is needed later, the router can be extended to accept a user-specified modality filter

#### Edge case: no signal detected

If a query contains none of the signal words:

- router defaults to `text_chunks` only
- this is the safest fallback: text chunks cover all born-digital plain text

#### Edge case: query in non-English

- keyword matching is English-only
- non-English queries will default to `text_chunks`
- document this as a known MVP limitation

#### Edge case: query references a file by name

Example: *"What does the invoice.pdf say?"*

- file name is not a modality signal
- router still picks collections by modality; the app layer can apply a `source_file_name` metadata filter to narrow results post-routing
- do not conflate file filtering with collection routing

---

### 12.8 Flow 2 — Dual-Model Query Handling Edge Cases

When a query triggers both image and text collections, two separate query embeddings are needed:

- BGE to embed the query for `text_chunks`, `ocr_chunks`, `audio_transcript_chunks`, `video_transcript_chunks`
- OpenCLIP to embed the query for `image_chunks`, `video_keyframe_chunks`

#### Edge case: text and image results have incompatible score scales

- BGE cosine similarity scores and OpenCLIP cosine similarity scores are not directly comparable
- Do **not** rank them together by raw score
- Merge strategy for MVP: retrieve top-N from each family separately, then concatenate and pass to Grok as separate labelled context blocks

#### Edge case: no results from image collection

- If image collection search returns zero results (e.g. no images indexed in session), fall back to text results only
- Do not send an empty context block to Grok

#### Edge case: session has no indexed data

If the user asks a question before any file has been ingested:

- vector DB query returns nothing
- app must detect empty result set and inform user rather than sending an empty context to Grok
- show message: "No documents have been indexed in this session yet."

---

### 12.9 Flow 2 — Retrieval and Context Assembly Edge Cases

| Edge case | What can go wrong | How to handle it |
|---|---|---|
| Retrieved chunks are from different documents | Context mixes unrelated content | Group chunks by `document_id` in metadata; label them separately in the context sent to Grok |
| Retrieved chunk has low OCR confidence | Low-quality OCR text is sent to Grok as fact | Include `ocr_confidence` in chunk metadata; optionally filter out chunks below a threshold before context assembly |
| Context exceeds Grok token limit | Grok receives too many tokens | Enforce a max context token count; truncate or reduce top-N retrieved chunks before sending |
| Same chunk retrieved multiple times | Overlap in chunking causes duplicates | Deduplicate by `chunk_id` before context assembly |
| Grok returns a hallucinated citation | Grok invents a source that was not in the context | Only present citations that are from chunks actually retrieved; validate source references before rendering |
| Grok API call fails | Network error, rate limit, or key expiry | Catch all API errors; show a clear error message to the user; do not crash the app |

---

### 12.10 Flow 2 — SQLite Chat History Edge Cases

| Edge case | What can go wrong | How to handle it |
|---|---|---|
| SQLite file not present on first run | Chat history write fails | Create DB and tables on first start if they do not exist |
| Concurrent writes from multiple Streamlit sessions | SQLite write lock contention | For MVP, limit to one active session; document SQLite concurrency limitation |
| Message contains special characters | SQL injection or encoding error | Use parameterised queries at all times |
| Session expires without explicit close | Partial conversation left in DB | Store session state with a `session_status` flag; mark incomplete sessions on load |
| Chat history grows indefinitely | DB file size grows without a bound | For MVP, implement a simple max message count per session or periodic cleanup |

---

### 12.11 General Streamlit Runtime Edge Cases

| Edge case | What can go wrong | How to handle it |
|---|---|---|
| App reruns on every widget interaction | Streamlit re-executes the full script on any UI event | Use `st.session_state` to preserve model loading state between reruns |
| Embedding models loaded on every request | Each user interaction re-loads BGE or OpenCLIP | Load models once at app start and store in `st.session_state`; do not reload per request |
| Multiple users on same Streamlit deployment | Shared process state causes data leakage | Isolate session data using `st.session_state` keyed to session token or user; do not use global variables for user data |
| Long-running ingestion blocks UI | PaddleOCR or Faster-Whisper occupies main thread | Use `st.spinner` for UX feedback; for MVP this is acceptable; note it as a known limitation |
| App crashes mid-ingestion | Partial data written to vector DB | Tag ingestion run with a `status` field in metadata; only mark as ready-to-chat once all chunks are confirmed written |

---

### 12.12 Edge Case Summary by Severity

| Severity | Edge case | Must handle before MVP launch |
|---|---|---|
| Critical | session has no indexed data — empty result sent to Grok | yes |
| Critical | corrupt or malformed file crashes the parser | yes |
| Critical | SQLite does not exist on first run | yes |
| Critical | partial ingestion written to vector DB, file marked ready | yes |
| Critical | Grok API failure crashes the app | yes |
| High | PDF page type not classified correctly, wrong pipeline used | yes |
| High | embedding model loaded on every Streamlit rerun | yes |
| High | chunk overlap causes duplicate context to Grok | yes |
| High | context exceeds Grok token limit | yes |
| Medium | OCR confidence below threshold stored as fact | recommended |
| Medium | audio transcript from silence or noise | recommended |
| Medium | video keyframe is black/blank embedded | recommended |
| Medium | file name with special characters breaks disk write | recommended |
| Low | non-English query defaults silently to text collection | document as known limitation |
| Low | ambiguous transcript keyword triggers both audio and video | acceptable for MVP |

