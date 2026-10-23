"""PDF extraction using native text first; page-level OCR fallback is intentionally reported as unsupported.
This CT-200 input contains selectable text and embedded table text, so PyMuPDF is appropriate.
"""
import fitz, re
def extract_pages(path: str):
    doc=fitz.open(path); result=[]
    for i,page in enumerate(doc):
        text=page.get_text("text", sort=True)
        blocks=page.get_text("blocks", sort=True)
        result.append({"page":i+1,"text":text,"blocks":blocks,"needs_ocr":len(text.strip()) < 30})
    return result
def extract_document_text(path: str):
    pages=extract_pages(path)
    return pages, "\n".join(p["text"] for p in pages)
