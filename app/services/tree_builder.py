import re, hashlib, unicodedata, uuid
from dataclasses import dataclass, field
from .pdf_extractor import extract_pages
HEADING_RE=re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(.+?)\s*$")
@dataclass
class ParsedNode:
    logical_key:str
    heading:str
    level:int
    body_text:str=""
    parent_key:str|None=None
    node_type:str="section"
    page_start:int|None=None
    page_end:int|None=None
    children:list=field(default_factory=list)
def norm(s):
    s=unicodedata.normalize("NFKC",s).replace("\ufb01","fi").replace("\u2011","-")
    return re.sub(r"\s+"," ",s).strip().casefold()
def digest(s): return hashlib.sha256(norm(s).encode()).hexdigest()
def parse_pdf(path):
    pages=extract_pages(path)
    nodes=[]; stack=[]; current=None; warnings=[]
    title="CardioTrack CT-200 Home Blood Pressure Monitor — Technical & User Manual"
    root=ParsedNode("title:"+norm(title),title,0,node_type="document",page_start=1,page_end=len(pages)); nodes.append(root)
    for pg in pages:
        if pg["needs_ocr"]:
            warnings.append(f"Page {pg['page']} has little extractable text; OCR fallback is not configured.")
        lines=pg["text"].splitlines()
        for raw in lines:
            line=raw.strip()
            if not line or line.startswith("<IMAGE") or line.startswith("<PARSED"): continue
            # discard PDF page furniture and table column headers; preserve table rows in body
            if line.lower() in {"parameter value","code meaning device behavior"}: continue
            m=HEADING_RE.match(line)
            # numbered headings only when heading text resembles a short label; lists with colon stay body
            is_heading=bool(m and len(m.group(2))<85 and not re.match(r"(Normal|Elevated|Hypertension|Hypertensive\s+Crisis)",m.group(2),re.I))
            if is_heading:
                num,label=m.group(1),m.group(2).strip()
                # The observed manual contains 2.1.1.1 under 2.1 and 3.4 before 3.3.
                # Keep printed numbering as identity evidence but assign hierarchy from numbering depth.
                level=len(num.split("."))
                key="sec:"+num+":"+norm(label)
                node=ParsedNode(key, f"{num} {label}",level,"",None,"section",pg["page"],pg["page"])
                # parent by nearest existing numeric prefix; special fallback to document root
                parts=num.split(".")
                parent=root
                # Walk from the closest possible numeric prefix toward the document root.
                for depth in range(len(parts)-1, 0, -1):
                    prefix=".".join(parts[:depth])
                    candidate=next((n for n in reversed(nodes) if n.logical_key.startswith("sec:"+prefix+":")),None)
                    if candidate is not None:
                        parent=candidate
                        break
                node.parent_key=parent.logical_key
                nodes.append(node); stack.append(node); current=node
                continue
            if current is None: current=root
            # Numeric lists remain body content; table rows retained as line-oriented text.
            current.body_text += (line+"\n")
            current.page_end=pg["page"]
    # prune accidental page furniture and trim text
    for n in nodes: n.body_text=n.body_text.strip()
    # Add structural parent links later; repeated heading instances get distinct IDs via version+sequence.
    return title,nodes,warnings
