# Multi Modal RAG

Lightweight multimodal RAG app built with Streamlit for ingestion, retrieval, and grounded chat.

## Current scope

The application currently covers the MVP scope described in the project and infrastructure documents:

- Upload and validate text, PDF, image, audio, and video files.
- Route files through modality-specific ingestion parsers.
- Embed content into Chroma Cloud collections with session-aware metadata.
- Retrieve relevant chunks in Flow 2 with a deterministic query router.
- Assemble context for Grok, render citations, and persist chat turns in SQLite.

## Current implementation status

- Flow 1 ingestion is implemented and repo-validated.
- Flow 2 retrieval and chat are implemented and aligned with the current scope documents.
- The query router defaults to `text_chunks` only, and OCR intent adds `ocr_chunks` as required by the infra spec.
- Grok prompt assembly truncates context to `MAX_CONTEXT_TOKENS` before the request is sent.

## Validation

The current repository test baseline passes:

```bash
python -m pytest -q
```

Expected result: `8 passed`.

## Quick start

1. Create a `.env` file from `env.example` and provide your Chroma and Grok credentials.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   streamlit run app.py
   ```

## Notes

- Audio and video pipelines depend on local runtime tools such as Faster-Whisper and FFmpeg for full end-to-end verification.
- The Streamlit UI uses the current session ID to keep uploads and chat scoped to the active session.
