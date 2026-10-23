import os, uuid, hashlib, json
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from dotenv import load_dotenv
try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None
from .database import Base, engine, get_db, SessionLocal
from .models import Document, DocumentVersion, Node, Selection, SelectionItem
from .schemas import SelectionCreate, GenerateRequest
from .services.tree_builder import parse_pdf, digest, norm
from .services.version_matcher import match_nodes
from .services.llm_service import generate
load_dotenv()
Base.metadata.create_all(bind=engine)
app=FastAPI(title="Tri9T CT-200 AI QA API",version="1.0.0",description="Versioned PDF tree, selection-pinned QA generation, and staleness checks.")
def mongo_collection():
    uri=os.getenv("MONGODB_URI")
    if uri and MongoClient is not None:
        return MongoClient(uri,serverSelectionTimeoutMS=1500)[os.getenv("MONGODB_DATABASE","tri9t_ct200")]["generations"]
    return None
def stable_json(obj): return json.dumps(obj,sort_keys=True,ensure_ascii=False,default=str)
def node_out(n,children=None):
    return {"id":n.id,"logical_id":n.logical_id,"version_id":n.version_id,"heading":n.heading,"level":n.level,"parent_id":n.parent_id,"body_text":n.body_text,"content_hash":n.content_hash,"node_type":n.node_type,"page_start":n.page_start,"page_end":n.page_end,"children":children or []}
@app.get("/")
def root(): return {"service":"Tri9T CT-200 AI QA API","docs":"/docs"}
@app.post("/documents/ingest")
async def ingest(file: UploadFile=File(...), document_id:str=Query("ct200"), db:Session=Depends(get_db)):
    suffix=Path(file.filename or "").suffix.lower()
    if suffix!=".pdf": raise HTTPException(400,"Upload a PDF file.")
    content=await file.read()
    if len(content)>30*1024*1024: raise HTTPException(413,"PDF exceeds 30 MB.")
    tmp=Path("data"); tmp.mkdir(exist_ok=True); path=tmp/f"{uuid.uuid4().hex}.pdf"; path.write_bytes(content)
    try:
        title, parsed, warnings=parse_pdf(str(path))
    except Exception as e:
        path.unlink(missing_ok=True); raise HTTPException(422,f"PDF extraction failed: {type(e).__name__}: {e}")
    finally:
        path.unlink(missing_ok=True)
    sha=hashlib.sha256(content).hexdigest()
    doc=db.get(Document,document_id)
    if not doc:
        doc=Document(id=document_id,title=title); db.add(doc); db.flush()
    existing=db.scalar(select(DocumentVersion).where(DocumentVersion.document_id==document_id).order_by(DocumentVersion.version_number.desc()))
    if existing and existing.source_sha256==sha:
        return {"document_id":document_id,"version_id":existing.id,"version_number":existing.version_number,"nodes_created":len(existing.nodes),"warnings":["Identical PDF already ingested; reused existing version."]}
    old_nodes=existing.nodes if existing else []
    matched=match_nodes(old_nodes,parsed) if old_nodes else [(p,None) for p in parsed]
    ver=DocumentVersion(document_id=document_id,version_number=(existing.version_number+1 if existing else 1),source_filename=file.filename or "uploaded.pdf",source_sha256=sha)
    db.add(ver); db.flush()
    # Map parser keys to stored IDs, preserving logical IDs on confident matches.
    node_map={}
    for p,logical in matched:
        node_id=str(uuid.uuid4())
        node=Node(id=node_id,logical_id=logical or str(uuid.uuid4()),version_id=ver.id,parent_id=None,heading=p.heading,level=p.level,body_text=p.body_text,content_hash=digest(p.heading+"\n"+p.body_text),node_type=p.node_type,page_start=p.page_start,page_end=p.page_end)
        db.add(node); node_map[p.logical_key]=node
    db.flush()
    for p,logical in matched:
        node=node_map[p.logical_key]
        parent=node_map.get(p.parent_key)
        node.parent_id=parent.id if parent else None
    db.commit()
    return {"document_id":document_id,"version_id":ver.id,"version_number":ver.version_number,"nodes_created":len(parsed),"warnings":warnings}
@app.get("/documents/{document_id}/versions")
def versions(document_id:str,db:Session=Depends(get_db)):
    doc=db.get(Document,document_id)
    if not doc: raise HTTPException(404,"Document not found")
    return [{"version_id":v.id,"version_number":v.version_number,"source_filename":v.source_filename,"created_at":v.created_at,"node_count":len(v.nodes)} for v in sorted(doc.versions,key=lambda x:x.version_number)]
def get_version(db,document_id,version):
    q=select(DocumentVersion).where(DocumentVersion.document_id==document_id)
    if version is not None: q=q.where(DocumentVersion.version_number==version)
    v=db.scalar(q.order_by(DocumentVersion.version_number.desc()))
    if not v: raise HTTPException(404,"Document version not found")
    return v
@app.get("/documents/{document_id}/sections")
def sections(document_id:str,version:int|None=None,db:Session=Depends(get_db)):
    v=get_version(db,document_id,version)
    return [node_out(n) for n in v.nodes if n.level<=1 and (n.level==0 or n.parent_id is None or db.get(Node,n.parent_id).level==0)]
@app.get("/nodes/search")
def search_nodes(q:str=Query(min_length=1),document_id:str="ct200",version:int|None=None,db:Session=Depends(get_db)):
    v=get_version(db,document_id,version); needle=norm(q)
    return [node_out(n) for n in v.nodes if needle in norm(n.heading) or needle in norm(n.body_text)]

@app.get("/nodes/{node_id}")
def get_node(node_id:str,db:Session=Depends(get_db)):
    n=db.get(Node,node_id)
    if not n: raise HTTPException(404,"Node not found")
    children=db.scalars(select(Node).where(Node.parent_id==node_id)).all()
    return node_out(n,[node_out(c) for c in children])
@app.get("/nodes/{node_id}/changes")
def node_changes(node_id:str,db:Session=Depends(get_db)):
    n=db.get(Node,node_id)
    if not n: raise HTTPException(404,"Node not found")
    peers=db.scalars(select(Node).where(Node.logical_id==n.logical_id)).all()
    peers.sort(key=lambda x:x.version_id)
    current=peers[-1]
    return {"logical_id":n.logical_id,"requested_node_id":n.id,"current_node_id":current.id,"changed":n.content_hash!=current.content_hash,"requested_hash":n.content_hash,"current_hash":current.content_hash,"versions":[{"node_id":x.id,"version_id":x.version_id,"heading":x.heading,"content_hash":x.content_hash} for x in peers],"diff_summary":({"old_heading":n.heading,"new_heading":current.heading,"old_text":n.body_text[:250],"new_text":current.body_text[:250]} if n.content_hash!=current.content_hash else None)}
@app.post("/selections")
def create_selection(data:SelectionCreate,db:Session=Depends(get_db)):
    nodes=[]
    for nid in data.node_ids:
        n=db.get(Node,nid)
        if not n: raise HTTPException(404,f"Node not found: {nid}")
        nodes.append(n)
    selection=Selection(id=str(uuid.uuid4()),name=data.name); db.add(selection); db.flush()
    for n in nodes: db.add(SelectionItem(selection_id=selection.id,node_id=n.id,version_id=n.version_id))
    db.commit()
    return {"selection_id":selection.id,"name":selection.name,"items":[{"node_id":n.id,"version_id":n.version_id,"heading":n.heading,"content_hash":n.content_hash} for n in nodes]}
@app.get("/selections/{selection_id}")
def get_selection(selection_id:str,db:Session=Depends(get_db)):
    s=db.get(Selection,selection_id)
    if not s: raise HTTPException(404,"Selection not found")
    items=db.scalars(select(SelectionItem).where(SelectionItem.selection_id==selection_id)).all()
    return {"selection_id":s.id,"name":s.name,"items":[{"node":node_out(db.get(Node,i.node_id)),"version_id":i.version_id} for i in items]}
@app.post("/generations")
async def create_generation(data:GenerateRequest,db:Session=Depends(get_db)):
    s=db.get(Selection,data.selection_id)
    if not s: raise HTTPException(404,"Selection not found")
    items=db.scalars(select(SelectionItem).where(SelectionItem.selection_id==s.id)).all()
    source_nodes=[db.get(Node,i.node_id) for i in items]
    source="\n\n".join(f"## {n.heading}\n{n.body_text}" for n in source_nodes)
    try: output,model=await generate(source)
    except Exception as e: raise HTTPException(502,f"Generation failed safely: {e}")
    source_version=db.get(DocumentVersion,source_nodes[0].version_id)
    generation={"generation_id":str(uuid.uuid4()),"document_id":source_version.document_id,"selection_id":s.id,"selection_name":s.name,"created_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),"model":model,"source_nodes":[{"node_id":n.id,"logical_id":n.logical_id,"version_id":n.version_id,"heading":n.heading,"content_hash":n.content_hash,"source_text":n.heading+"\n"+n.body_text} for n in source_nodes],"test_cases":output["test_cases"]}
    coll=mongo_collection()
    if coll:
        coll.insert_one({**generation,"_id":generation["generation_id"]})
        storage="mongodb"
    else:
        # JSON fallback is explicit and persisted; acceptable per assignment if justified.
        out=Path("data/generations.jsonl"); out.parent.mkdir(exist_ok=True)
        with out.open("a",encoding="utf-8") as f: f.write(stable_json(generation)+"\n")
        storage="jsonl-fallback"
    return {"generation_id":generation["generation_id"],"selection_id":s.id,"model":model,"storage":storage,"test_cases":output["test_cases"],"source_hashes":[n.content_hash for n in source_nodes]}
def all_generations():
    coll=mongo_collection()
    if coll: return list(coll.find({},{"_id":0}))
    p=Path("data/generations.jsonl")
    if not p.exists(): return []
    out=[]
    for line in p.read_text(encoding="utf-8").splitlines():
        try: out.append(json.loads(line))
        except json.JSONDecodeError: continue
    return out
def with_staleness(g,db):
    latest=get_version(db,g.get("document_id","ct200"),None)
    statuses=[]
    latest_by_logical={n.logical_id:n for n in latest.nodes}
    for src in g["source_nodes"]:
        now=latest_by_logical.get(src["logical_id"])
        status="removed" if now is None else ("unchanged" if now.content_hash==src["content_hash"] else "changed")
        statuses.append({"source_node_id":src["node_id"],"logical_id":src["logical_id"],"source_version_id":src["version_id"],"current_node_id":now.id if now else None,"status":status,"current_hash":now.content_hash if now else None})
    g["staleness"]={"is_stale":any(x["status"]!="unchanged" for x in statuses),"sources":statuses}
    return g
@app.get("/generations")
def retrieve_generations(selection_id:str|None=None,node_id:str|None=None,db:Session=Depends(get_db)):
    if not selection_id and not node_id: raise HTTPException(400,"Provide selection_id or node_id")
    gs=all_generations()
    if selection_id: gs=[g for g in gs if g.get("selection_id")==selection_id]
    if node_id: gs=[g for g in gs if any(s.get("node_id")==node_id or s.get("logical_id")==node_id for s in g.get("source_nodes",[]))]
    return [with_staleness(g,db) for g in gs]
