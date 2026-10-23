# Tri9T CT-200 AI QA API

A FastAPI backend that extracts the supplied CT-200 PDF, stores a hierarchical document tree with hashes, versions re-ingested manuals, pins selections to exact version-specific nodes, generates structured QA test-case ideas, and exposes source staleness during retrieval.

## Requirements
- Python 3.11+
- Optional MongoDB Atlas/local MongoDB (otherwise JSONL persistence is used and reported)
- Optional Groq API key for live LLM output (otherwise deterministic local fallback lets the end-to-end flow run offline)

## Setup
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # Windows; on macOS/Linux use cp
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs.

Set `GROQ_API_KEY` for live LLM generation. Set `MONGODB_URI` to persist generations in MongoDB. With no Mongo URI, the app stores generated records in `data/generations.jsonl`; this is the documented JSON-store alternative.

## Ingest v1 then v2
In Swagger, call `POST /documents/ingest` twice with the corresponding PDF and `document_id=ct200`. Or:
```bash
curl -F "file=@data/ct200_manual.pdf" "http://127.0.0.1:8000/documents/ingest?document_id=ct200"
curl -F "file=@data/ct200_manual_v2.pdf" "http://127.0.0.1:8000/documents/ingest?document_id=ct200"
```
The first upload creates Version 1; the second creates Version 2. Identical file bytes reuse the existing version. Then call `GET /documents/ct200/versions`, browse `/documents/ct200/sections?version=1`, and search `/nodes/search?q=battery&version=1`.

## End-to-end selection and staleness demo
1. Select node IDs returned from the browse/search API and call `POST /selections`:
```json
{"name":"Battery requirements v1","node_ids":["PASTE_NODE_ID"]}
```
2. Generate cases:
```json
{"selection_id":"PASTE_SELECTION_ID","regenerate":true}
```
3. Re-ingest v2 (if not already done), then retrieve:
`GET /generations?selection_id=PASTE_SELECTION_ID`
The response includes each source's `unchanged`, `changed`, or `removed` status and whether the generation is stale.
4. Retrieve a selection with `GET /selections/{selection_id}` to verify it still points to the original version-specific node/text.

## API overview
- `POST /documents/ingest`
- `GET /documents/{document_id}/versions`
- `GET /documents/{document_id}/sections?version=1`
- `GET /nodes/{node_id}`
- `GET /nodes/search?q=pressure&version=1`
- `GET /nodes/{node_id}/changes`
- `POST /selections`, `GET /selections/{selection_id}`
- `POST /generations`
- `GET /generations?selection_id=...` or `?node_id=...`

## Parsing notes and known limitations
The supplied PDFs have selectable text plus embedded rendered tables. The parser uses PyMuPDF native text extraction with sorted reading order; OCR is not configured, and low-text pages are flagged. Tables are retained as line-oriented text rather than reconstructed into cell-level structures. Heading numbering is used to infer hierarchy, with the document's unusual `2.1.1.1` numbering and the `3.4` appearing before `3.3` preserved as observed. This is CT-200-specific, not a generic parser. Manual inspection remains necessary for safety-critical content.

The source PDFs visibly differ in Version 2: battery life changes from ~300 to ~250 cycles and low-battery threshold from 15% to 10%; cuff inflation increments change from 40 to 30 mmHg; E3 auto-deflation changes from 2 to 1.5 seconds; E6 and data export section 5.3 are added. Use these as manual validation cases.

## Data model
SQLite: documents, document_versions, nodes (version-specific IDs and logical IDs), selections, selection_items. MongoDB/JSONL: generated output with selection ID, source node IDs/logical IDs, source hashes, source text, model and generated cases.

## LLM validation and duplicate submissions
The live Groq path requests JSON mode, validates with Pydantic, retries once on request/parse/schema failure, and returns a controlled 502 if both attempts fail. Each generation call creates a distinct generation ID, preserving repeat runs. Without a configured API key, deterministic local fallback output is clearly labeled `local-fallback` and intended for local demonstration only.

## Tests
```bash
pytest -q
```

## Git
Commit incremental working milestones rather than a single final dump. Do not commit `.env`, keys, local DBs, or PDFs unless permitted by the assignment.

## Submission email
A copy-ready email template is available at `docs/SUBMISSION_EMAIL.md`. Replace the placeholders with your public GitHub URL and repository link to the approach document before sending.
