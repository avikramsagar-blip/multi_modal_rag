# Flow 2 — Build Status Tracker

> **Purpose:** Track Flow 2 retrieval and chat progress against INFRA_SCOPE.md §3.3, §8, §12.7–12.12.
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
| 1 | SQLite chat persistence | `storage/sqlite_chat.py` | ✅ | creates the DB on first run, enforces a 200-message limit, and uses parameterized queries |
| 2 | Query router | `retrieval/router.py` | ✅ | defaults to `text_chunks`; OCR, image, audio, and video signals add the relevant families |
| 3 | Vector retriever | `retrieval/search.py` | ✅ | applies `session_id` filtering and uses the correct embedder per family |
| 4 | Result merger | `retrieval/merge.py` | ✅ | deduplicates chunk IDs, drops incomplete chunks, and keeps text/image families separate |
| 5 | Citation builder | `retrieval/citations.py` | ✅ | citations are built only from retrieved chunks that were actually sent to Grok |
| 6 | Grok client | `llm/grok_client.py` | ✅ | API errors are caught and the prompt context is truncated to `MAX_CONTEXT_TOKENS` |
| 7 | Context assembler | `retrieval/merge.py` | ✅ | token-limited context is assembled with labeled text + image sections |
| 8 | Chat UI | `ui/chat.py` | ✅ | uses Streamlit chat primitives, loads history, shows citations, and preserves the input-at-bottom layout |
| 9 | App shell wiring | `app.py` | ✅ | upload + chat tabs are available, and SQLite init runs at startup |

---

## Active Errors

_No active errors._

---

## Completed Verification Checklist

| Module | Verified by | Date |
|---|---|---|
| Query-router default behavior | direct runtime check (`text_chunks` only by default) | 2026-08-10 |
| OCR-intent routing | direct runtime check (`ocr_chunks` added when OCR keywords are present) | 2026-08-10 |
| Context-token enforcement | code review of `llm/grok_client.py` + `retrieval/merge.py` | 2026-08-10 |
| Unit test baseline | `pytest -q` (8 passed) | 2026-08-10 |

---

## Pending Manual Tests

| TC | Description | Blocker |
|---|---|---|
| FTC-03 | Ask a question before uploading any file — empty-state guard | not yet exercised in a live UI run |
| FTC-04 | Session isolation — Session A docs not visible in Session B | needs a live browser run |
| FTC-05 | Image-intent query after uploading image | requires an image file to be ingested |
| FTC-06 | Audio-intent query after uploading audio | requires audio runtime dependencies |
| FTC-07 | Video-intent query — transcript + keyframe collections | requires FFmpeg/runtime support |
| FTC-09 | Grok API failure handling | needs a simulated API failure |
