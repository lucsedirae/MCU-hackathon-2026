"""Local, version-scoped retrieval. Indexes evidence, never establishes project state."""
import hashlib
import math
import re
from collections import Counter

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import administrator, current, db
from app.content import MAX_UPLOAD, import_file, text_of, text_units, fingerprint
from app.documents import fail, get, serialize
from app.models import EvidencePassage, ReferenceVersion, User

router = APIRouter(prefix="/api/references", tags=["Shared reference library"])
CHUNK_CHARS = 2400
INDEX_VERSION = 1


def terms(text):
    return re.findall(r"\w{2,}", text.lower())


def index_content(session, collection, version_id, content):
    existing = list(session.scalars(select(EvidencePassage).where(
        EvidencePassage.collection == collection, EvidencePassage.version_id == version_id
    ).order_by(EvidencePassage.ordinal)))
    if existing:
        return existing
    passages = []
    pdf = any(w.startswith("PDF text extracted by page") for w in content.get("warnings", []))
    pages = {b["id"]: i+1 for i,b in enumerate(content["blocks"])} if pdf else {}
    for unit in text_units(content):
        text = unit.get("text", "")
        for start in range(0, len(text), CHUNK_CHARS):
            chunk = text[start:start + CHUNK_CHARS]
            if not chunk.strip():
                continue
            pid = hashlib.sha256(f"{INDEX_VERSION}:{collection}:{version_id}:{unit['id']}:{start}".encode()).hexdigest()[:32]
            p = EvidencePassage(id=pid, collection=collection, version_id=version_id,
                block_id=unit['id'], ordinal=len(passages), start=start, text=chunk,
                terms=dict(Counter(terms(chunk))), index_version=INDEX_VERSION, page=pages.get(unit["id"]))
            session.add(p); passages.append(p)
    session.flush()
    return passages


def passage_data(p):
    return serialize(p, "id collection version_id block_id ordinal start text index_version page")


def allowed_passages(session, scope):
    # Never accept collection/version permissions from a model response.
    result = []
    for collection, versions in scope.items():
        if versions:
            result.extend(session.scalars(select(EvidencePassage).where(
                EvidencePassage.collection == collection, EvidencePassage.version_id.in_(versions)
            ).order_by(EvidencePassage.version_id, EvidencePassage.ordinal)))
    return result


def search(session, scope, query, limit=6):
    """BM25 lexical ranking over authorized immutable versions; no network/provider calls."""
    rows = allowed_passages(session, scope)
    query_terms = set(terms(query[:2000]))
    if not rows or not query_terms:
        return []
    avg = sum(sum(p.terms.values()) for p in rows) / len(rows) or 1
    frequencies = {term: sum(term in p.terms for p in rows) for term in query_terms}
    def score(p):
        length = sum(p.terms.values())
        return sum(math.log(1 + (len(rows) - frequencies[t] + .5) / (frequencies[t] + .5))
            * p.terms.get(t, 0) * 2.2 / (p.terms.get(t, 0) + 1.2 * (.25 + .75 * length / avg)) for t in query_terms)
    ranked = sorted(((score(p), p) for p in rows), key=lambda x: (-x[0], x[1].id))
    return [passage_data(p) for weight, p in ranked[:min(limit, 12)] if weight > 0]


def read_passages(session, scope, ids):
    allowed = {p.id: p for p in allowed_passages(session, scope)}
    if len(ids) > 12 or any(pid not in allowed for pid in ids):
        raise ValueError("Passage read is outside the assignment scope or exceeds its limit.")
    return [passage_data(allowed[pid]) for pid in ids]


def read_surrounding(session, scope, pid):
    rows = allowed_passages(session, scope)
    target = next((p for p in rows if p.id == pid), None)
    if target is None:
        raise ValueError("Passage is outside the assignment scope.")
    return [passage_data(p) for p in rows if p.collection == target.collection
        and p.version_id == target.version_id and abs(p.ordinal - target.ordinal) <= 1]


def reference_data(r):
    return {**serialize(r, "id title subject authority version source_url filename content_hash published"), "created": r.created.isoformat()}


@router.get("")
def references(user: User = Depends(current), session: Session = Depends(db)):
    q = select(ReferenceVersion).order_by(ReferenceVersion.created.desc())
    if not user.admin:
        q = q.where(ReferenceVersion.published.is_(True))
    return [reference_data(r) for r in session.scalars(q)]


@router.post("")
async def upload_reference(file: UploadFile = File(...), title: str = Form(..., max_length=200),
    subject: str = Form(..., max_length=200), authority: str = Form(..., max_length=300),
    version: str = Form(..., max_length=80), source_url: str = Form("", max_length=2000),
    user: User = Depends(administrator), session: Session = Depends(db)):
    if not all(x.strip() for x in (title, subject, authority, version)):
        fail("Provide a title, subject, authority and version.", 400)
    if source_url and not source_url.startswith("https://"):
        fail("Use an https source link, or leave it blank.", 400)
    if session.scalar(select(ReferenceVersion).where(ReferenceVersion.title == title.strip(), ReferenceVersion.version == version.strip())):
        fail("That reference version already exists. Supply a new version.")
    data = await file.read(MAX_UPLOAD + 1)
    content, _ = import_file(file.filename or "", data)
    if not text_of(content).strip():
        fail("No readable reference text. Supply a text-based document.", 400)
    r = ReferenceVersion(title=title.strip(), subject=subject.strip(), authority=authority.strip(),
        version=version.strip(), source_url=source_url, content=content, original=data,
        filename=file.filename, content_hash=fingerprint(content), author_id=user.id)
    session.add(r); session.flush()
    index_content(session, "reference", r.id, content)
    session.commit()
    return reference_data(r)


@router.get("/{rid}")
def reference_detail(rid: str, user: User = Depends(current), session: Session = Depends(db)):
    r = get(session, ReferenceVersion, rid)
    if not r.published and not user.admin:
        fail("Reference is not published.", 404)
    return {**reference_data(r), "content": r.content}


@router.post("/{rid}/publish")
def publish_reference(rid: str, user: User = Depends(administrator), session: Session = Depends(db)):
    r = get(session, ReferenceVersion, rid)
    r.published = True
    session.commit()
    return reference_data(r)
