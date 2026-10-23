# Engineering Approach — Tri9T CT-200 AI QA

## 1. Summary
The service ingests the provided CT-200 PDF, reconstructs a navigable section tree, stores immutable version-specific nodes, creates version-pinned selections, generates structured QA test-case ideas, and reports source-content staleness on retrieval.

## 2. PDF inspection and extraction
I inspected the supplied parsed text and page renderings. Both manuals contain selectable text and tables that appear visually as grids. I chose PyMuPDF native extraction with `sort=True` rather than OCRing every page: it preserves text more faithfully where a text layer exists and avoids OCR character errors. Pages with fewer than 30 extracted characters are flagged; this implementation does not automatically OCR those pages. That is a deliberate limitation to expose, not silently treat as complete extraction.

The parser recognizes numbered headings using a regular expression and uses the printed section-number depth to infer levels. It retains table rows as line-oriented body text. It does not reconstruct table cells as structured records, and it does not currently preserve figure images/captions as separate node types.

## 3. Observed structural irregularities
- Section numbering is inconsistent: `2.1.1.1 Battery Life Under Typical Use` is nested numerically below `2.1`, skipping `2.1.1` in the supplied text.
- Section 3.4 Auto Shutoff appears before section 3.3 Result Display and Classification in extracted reading order.
- Tables (specifications and error codes) are visually rendered tables and the text layer flattens rows/cells.
- Ligatures and glyph variants occur in words such as “Specifications”, “cuff”, “profile”, and “deflation”; normalization uses Unicode NFKC and whitespace/case normalization.
- V2 changes numerical safety/behavior requirements: battery life ~300 to ~250 cycles; low-battery threshold 15% to 10%; cuff inflation increment 40 to 30 mmHg; E3 deflation time 2 to 1.5 seconds. V2 adds E6 Bluetooth sync failure and section 5.3 Data Export.
- The PDF's section 4.3 text spans a page boundary in V2.
- The source contains the term “Anthropic recommends” in the calibration section; this is retained as written rather than corrected by the parser.

## 4. Hierarchy and identity
A node has a version-specific ID, logical ID, version ID, parent ID, heading, level, body, page range, type, and SHA-256 hash of normalized heading plus body. Logical IDs are matched using printed section number plus normalized heading, with a unique-heading fallback. Ambiguous candidates are left unmatched and receive new logical IDs. This prevents a forced but potentially incorrect match.

The current matching strategy is intentionally simple. It may fail if a section is renumbered, moved, renamed, or if the same heading appears more than once. A production design would record match confidence and support manual reconciliation. Content hashes detect textual change, not semantic significance; even punctuation changes can mark a node stale.

## 5. Selections and generations
Selections store explicit pairs of version-specific node ID and version ID. This makes a selection resolve to its original text after new versions are ingested. Generated records retain the source node ID, logical ID, version ID, heading, exact source text, and content hash.

The generation API requests 3–5 JSON test cases and validates the response with Pydantic. It retries once after provider, JSON, or schema errors, then returns a controlled error and does not store invalid output. If no API key is configured, a deterministic local fallback allows API-flow testing but is not represented as genuine LLM output. MongoDB is used when configured; otherwise JSONL is used as the permitted JSON-store alternative. Each submission creates a new generation ID rather than deduplicating calls.

## 6. Staleness
At retrieval time, the API finds the latest document version and compares each generation source's logical ID and content hash. Status is `unchanged`, `changed`, or `removed`; a diff summary exposes old and current text snippets when the requested node is changed. This is a conservative textual check. It cannot determine whether a change is clinically material, nor can it establish that a generated test case is still adequate. A one-word change is treated as stale just like a numeric threshold change; a future improvement would classify changed tokens/requirements and support impact review.

## 7. Validation
Unit tests cover section-number identity, deep heading numbering, threshold-sensitive hashes, text normalization, confident matching, and ambiguous matching. The API should additionally be exercised with the supplied v1 and v2 PDFs. Important expected differences include:
- Battery cycles: 300 → 250
- Low-battery icon threshold: 15% → 10%
- Inflation increments: 40 → 30 mmHg
- E3 deflation: 2 → 1.5 seconds
- E6 error code added
- Data export section 5.3 added

The current automated tests are focused unit tests and do not replace a page-by-page visual comparison. A stronger follow-up would add fixtures extracted from known pages and assertions on table cell counts and hierarchy.

## 8. Decision log
1. **Most likely silent failure:** A heading may be assigned the wrong parent while still looking like valid structured data. I would catch this using numbering/parent invariants, duplicate-heading tests, and a manual comparison of the extracted tree against rendered pages.
2. **Simplicity over correctness:** I chose rule-based numbering and a conservative path/title matcher rather than a general layout model or semantic matcher. Renumbered/moved headings are the first likely production failure; ambiguous matches should be reviewed rather than automatically trusted.
3. **Unsupported input:** A scanned page with no useful text layer is not OCRed in this implementation. It is reported in the ingestion warnings so the operator can inspect it; production should add OCR and visual validation before accepting the version.

## 9. What I would improve next
- OCR fallback (Tesseract) for image-only pages.
- Structured table extraction and figure/caption linkage.
- Better parent resolution and validation of skipped numbering.
- Match-confidence scoring and review queue.
- Semantic impact classification that prioritizes numerical thresholds and safety-critical requirements.
- Integration tests that launch the API, ingest both PDFs, generate a case, and verify stale retrieval.
