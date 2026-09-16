"""Workspace, proposal, run and comment APIs with owner-authorized mutations."""

import hashlib
import logging
import json
from uuid import uuid4
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    BackgroundTasks,
)
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app.auth import db, current, administrator
from app.database import engine
from app.models import (
    User,
    Workspace,
    Document,
    Revision,
    Original,
    ReviewRun,
    Thread,
    Message,
    Export,
    Audit,
    now,
    BuilderWorkspace,
)
from app.content import (
    import_file,
    fingerprint,
    stable_ids,
    text_of,
    anchor,
    compare,
    export_bytes,
    markdown,
    text_units,
    MAX_TEXT,
    as_markdown,
)
from app.llm import request_completion

router = APIRouter(prefix="/api", tags=["Documents"])


def fail(detail, code=409):
    raise HTTPException(code, detail)


def get(session, model, id):
    obj = session.get(model, id)
    if not obj:
        fail("Record not found.", 404)
    return obj


def owner(session, workspace_id, user):
    workspace = session.scalar(
        select(Workspace).where(Workspace.id == workspace_id).with_for_update()
    )
    if not workspace:
        fail("Workspace not found.", 404)
    if workspace.owner_id != user.id:
        fail("Only the workspace owner can do this.", 403)
    return workspace


def audit(session, user, workspace, action, target, **detail):
    session.add(
        Audit(
            user_id=user.id,
            workspace_id=workspace,
            action=action,
            target_id=target,
            detail=detail,
        )
    )


def serialize(obj, fields):
    return {k: getattr(obj, k) for k in fields.split()}


def doc_data(d):
    return serialize(d, "id workspace_id kind title current_id created")


def rev_data(r):
    return serialize(
        r,
        "id document_id number base_id author_id status description selected_comments created",
    )


def revision_for(session, doc_id, revision_id):
    r = get(session, Revision, revision_id)
    if r.document_id != doc_id:
        fail("Revision does not belong to this document.", 404)
    return r


def add_revision(
    session, document, user, content, description="", base_id=None, selected=None
):
    session.flush()
    # Caller holds the workspace row lock; this serializes revision numbers and acceptance.
    previous = get(session, Revision, base_id) if base_id else None
    if previous and previous.document_id != document.id:
        fail("Invalid base revision.", 400)
    if previous:
        content = stable_ids(content, previous.content)
    number = (
        session.scalar(
            select(func.max(Revision.number)).where(Revision.document_id == document.id)
        )
        or 0
    ) + 1
    r = Revision(
        document_id=document.id,
        number=number,
        base_id=base_id,
        author_id=user.id,
        content=content,
        content_hash=fingerprint(content),
        description=description,
        status="pending" if document.kind == "curriculum" else "saved",
        selected_comments=selected or [],
    )
    session.add(r)
    session.flush()
    if document.kind != "curriculum":
        document.current_id = r.id
    audit(session, user, document.workspace_id, "revision_created", r.id)
    return r


def ancestors(session, revision):
    ids, pending = set(), [revision.id]
    while pending:
        rid = pending.pop()
        if not rid or rid in ids:
            continue
        ids.add(rid)
        r = session.get(Revision, rid)
        if r and r.base_id:
            pending.append(r.base_id)
        for event in session.scalars(
            select(Audit).where(
                Audit.target_id == rid, Audit.action == "proposal_accepted"
            )
        ):
            if event.detail.get("previous"):
                pending.append(event.detail["previous"])
    return ids


def threads_for(session, document, revision):
    result = []
    lineage = ancestors(session, revision)
    for t in session.scalars(
        select(Thread).where(Thread.document_id == document.id).order_by(Thread.created)
    ):
        if t.revision_id not in lineage:
            continue
        data = serialize(
            t,
            "id document_id revision_id author_id quote block_id start end resolved created",
        )
        data["anchor"] = anchor(t, revision.content)
        data["messages"] = [
            serialize(m, "id author_id author_name text source_date created")
            for m in session.scalars(
                select(Message)
                .where(Message.thread_id == t.id)
                .order_by(Message.created, Message.id)
            )
        ]
        result.append(data)
    return result


class WorkspaceInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    owner_id: str


class OwnerInput(BaseModel):
    owner_id: str


@router.get("/workspaces")
def workspaces(user: User = Depends(current), session: Session = Depends(db)):
    return [
        serialize(w, "id title owner_id created")
        for w in session.scalars(select(Workspace).order_by(Workspace.created.desc()))
    ]


@router.post("/workspaces")
def create_workspace(
    payload: WorkspaceInput,
    user: User = Depends(administrator),
    session: Session = Depends(db),
):
    get(session, User, payload.owner_id)
    w = Workspace(title=payload.title, owner_id=payload.owner_id)
    session.add(w)
    session.flush()
    d = Document(workspace_id=w.id, title=payload.title, kind="curriculum")
    session.add(d)
    session.flush()
    audit(session, user, w.id, "workspace_created", w.id)
    session.commit()
    return serialize(w, "id title owner_id created")


@router.put("/workspaces/{workspace_id}/owner")
def transfer(
    workspace_id: str,
    payload: OwnerInput,
    user: User = Depends(administrator),
    session: Session = Depends(db),
):
    w = session.scalar(
        select(Workspace).where(Workspace.id == workspace_id).with_for_update()
    )
    if not w:
        fail("Workspace not found.", 404)
    get(session, User, payload.owner_id)
    old = w.owner_id
    w.owner_id = payload.owner_id
    audit(
        session,
        user,
        w.id,
        "ownership_transferred",
        w.id,
        previous=old,
        owner_id=w.owner_id,
    )
    session.commit()
    return {"ok": True}


@router.get("/workspaces/{workspace_id}")
def workspace_detail(
    workspace_id: str, user: User = Depends(current), session: Session = Depends(db)
):
    w = get(session, Workspace, workspace_id)
    return {
        **serialize(w, "id title owner_id created"),
        "builder_mode": (session.get(BuilderWorkspace, w.id).mode if session.get(BuilderWorkspace, w.id) else None),
        "owner_name": get(session, User, w.owner_id).name,
        "documents": [
            doc_data(d)
            for d in session.scalars(
                select(Document)
                .where(Document.workspace_id == w.id)
                .order_by(Document.created)
            )
        ],
        "runs": [
            serialize(
                r,
                "id revision_id kind status was_proposal entries report_id result_id transcript_id created",
            )
            for r in session.scalars(
                select(ReviewRun)
                .where(ReviewRun.workspace_id == w.id)
                .order_by(ReviewRun.created.desc())
            )
        ],
    }


@router.get("/documents/{doc_id}")
def document_detail(
    doc_id: str, user: User = Depends(current), session: Session = Depends(db)
):
    d = get(session, Document, doc_id)
    revisions = list(
        session.scalars(
            select(Revision)
            .where(Revision.document_id == doc_id)
            .order_by(Revision.number.desc())
        )
    )
    run = session.scalar(
        select(ReviewRun).where(
            or_(ReviewRun.report_id == d.id, ReviewRun.transcript_id == d.id)
        )
    )
    source = (
        get(session, Revision, run.revision_id) if run and run.revision_id else None
    )
    context = (
        {
            "run_id": run.id,
            "revision_id": source.id if source else None,
            "document_id": source.document_id if source else None,
            "number": source.number if source else None,
            "was_proposal": run.was_proposal,
        }
        if run
        else None
    )
    return {
        **doc_data(d),
        "source": context,
        "revisions": [
            {
                **rev_data(r),
                "author_name": get(session, User, r.author_id).name,
                "outdated": r.status in ("pending", "rejected")
                and r.base_id != d.current_id,
            }
            for r in revisions
        ],
    }


@router.get("/documents/{doc_id}/revisions/{revision_id}")
def revision_detail(
    doc_id: str,
    revision_id: str,
    user: User = Depends(current),
    session: Session = Depends(db),
):
    d = get(session, Document, doc_id)
    r = revision_for(session, doc_id, revision_id)
    return {
        **rev_data(r),
        "content": r.content,
        "threads": threads_for(session, d, r),
        "originals": [
            dict(o)
            for o in session.execute(
                select(Original.id, Original.name).where(Original.revision_id == r.id)
            ).mappings()
        ],
        "exports": [
            dict(e)
            for e in session.execute(
                select(Export.id, Export.format, Export.created)
                .where(Export.revision_id == r.id)
                .order_by(Export.created.desc())
            ).mappings()
        ],
    }


@router.post("/documents/{doc_id}/upload")
async def upload(
    doc_id: str,
    file: UploadFile = File(...),
    base_id: str = Form(""),
    expected_current: str = Form(""),
    description: str = Form("Uploaded revision"),
    user: User = Depends(current),
    session: Session = Depends(db),
):
    d = get(session, Document, doc_id)
    owner(session, d.workspace_id, user)
    session.refresh(d)
    if d.kind == "transcript":
        fail("Run transcripts cannot be edited.", 403)
    if (d.current_id or "") != expected_current:
        fail("The current revision changed. Refresh before uploading.")
    from app.uploads import read_upload
    content, imported, original_storage = await read_upload(file, session)
    base = base_id or d.current_id
    previous = revision_for(session, d.id, base) if base else None
    # Preserve every original upload, even when its normalized content is unchanged.
    r = (
        previous
        if previous and previous.content_hash == fingerprint(content) and not imported
        else add_revision(session, d, user, content, description[:2000], base)
    )
    session.add(
        Original(
            revision_id=r.id,
            name=(file.filename or "upload").split("/")[-1].split("\\")[-1],
            **original_storage,
        )
    )
    imported_by_id = {c["source_id"]: c for c in imported}
    imported_threads = {}
    # Reconnect unchanged comments from our own exported snapshots instead of
    # duplicating the same discussion on each Word round-trip.
    inherited = {t['id'] for t in threads_for(session,d,previous)} if previous else set()
    exported_comments = {}
    if imported and inherited:
        snapshots = session.scalars(select(Export.snapshot).join(Revision,Export.revision_id==Revision.id).where(Revision.document_id==d.id))
        for snapshot in snapshots:
            for thread in snapshot:
                if thread['id'] not in inherited: continue
                messages = thread['messages']
                forms = [
                    '\n\n'.join(f"{m['author_name']} ({m['source_date'] or m['created']}): {m['text']}" for m in messages),
                    '\n\n'.join(m['author_name']+': '+m['text'] for m in messages),
                ]
                for value in forms:
                    exported_comments[(thread['quote'],value)] = thread['id']
    for c in imported:
        root = c
        seen = set()
        while root.get("parent_id") in imported_by_id and root["source_id"] not in seen:
            seen.add(root["source_id"])
            root = imported_by_id[root["parent_id"]]
        root_id = root["source_id"]
        existing_id = exported_comments.get((root['quote'],root['text']))
        if existing_id:
            imported_threads[root_id]=get(session,Thread,existing_id)
            if c['source_id']==root_id: continue
        if root_id not in imported_threads:
            t = Thread(
                document_id=d.id,
                revision_id=r.id,
                author_id=None,
                quote="" if root.get("scope")=="general" else root["quote"] or "(Original passage unavailable)",
                resolved=root.get("resolved", False),
            )
            a = anchor(t, r.content)
            if a["status"] == "attached":
                t.block_id = a["block_id"]
                t.start = a["start"]
                t.end = a["end"]
            session.add(t)
            session.flush()
            imported_threads[root_id] = t
        t = imported_threads[root_id]
        session.add(
            Message(
                thread_id=t.id,
                author_name=c["author"],
                text=c["text"] or "(Empty imported comment)",
                source_date=c["date"],
            )
        )
    session.commit()
    return rev_data(r)


@router.get("/originals/{original_id}")
def original(
    original_id: str, user: User = Depends(current), session: Session = Depends(db)
):
    o = get(session, Original, original_id)
    if o.storage_key:
        from app.uploads import stored_path
        path = stored_path(o.storage_key)
        if not path.is_file():
            fail("Original backup file is unavailable. Restore the upload volume from backup.", 404)
        return FileResponse(path, filename=o.name, media_type="application/octet-stream")
    return download(o.data, o.name, "application/octet-stream")


class ComparisonInput(BaseModel):
    against_id: str | None = None


@router.post("/documents/{doc_id}/revisions/{revision_id}/compare")
def comparison(
    doc_id: str,
    revision_id: str,
    payload: ComparisonInput,
    user: User = Depends(current),
    session: Session = Depends(db),
):
    d = get(session, Document, doc_id)
    r = revision_for(session, doc_id, revision_id)
    previous = (
        revision_for(session, doc_id, payload.against_id)
        if payload.against_id
        else None
    )
    if payload.against_id is None and d.current_id:
        previous = get(session, Revision, d.current_id)
    token = str(uuid4())
    audit(
        session,
        user,
        d.workspace_id,
        "comparison_viewed",
        r.id,
        against_id=previous.id if previous else None,
        token=token,
    )
    session.commit()
    return {
        "token": token,
        "against_id": previous.id if previous else None,
        "changes": compare(previous.content if previous else {"blocks": []}, r.content),
    }


class AcceptInput(BaseModel):
    comparison_token: str
    expected_current: str | None = None
    resolve_threads: list[str] = Field(default_factory=list, max_length=200)


@router.post("/documents/{doc_id}/revisions/{revision_id}/accept")
def accept(
    doc_id: str,
    revision_id: str,
    payload: AcceptInput,
    user: User = Depends(current),
    session: Session = Depends(db),
):
    d = get(session, Document, doc_id)
    owner(session, d.workspace_id, user)
    session.refresh(d)
    r = revision_for(session, doc_id, revision_id)
    if d.kind != "curriculum" or r.status != "pending":
        fail("Only pending curriculum proposals can be accepted.")
    if d.current_id != payload.expected_current:
        fail("The current curriculum changed. Compare again before accepting.")
    events = session.scalars(
        select(Audit).where(
            Audit.user_id == user.id,
            Audit.target_id == r.id,
            Audit.action == "comparison_viewed",
        )
    ).all()
    if not any(
        e.detail.get("token") == payload.comparison_token
        and e.detail.get("against_id") == d.current_id
        for e in events
    ):
        fail("Preview a fresh comparison before acceptance.")
    for tid in payload.resolve_threads:
        if tid not in r.selected_comments:
            fail(
                "Only comments selected for this proposal can be resolved during acceptance.",
                400,
            )
        t = get(session, Thread, tid)
        if t.document_id != d.id:
            fail("Invalid comment.", 400)
        t.resolved = True
        audit(session, user, d.workspace_id, "comment_resolved", tid)
    d.current_id = r.id
    r.status = "accepted"
    audit(
        session,
        user,
        d.workspace_id,
        "proposal_accepted",
        r.id,
        previous=payload.expected_current,
    )
    session.commit()
    return rev_data(r)


class StateInput(BaseModel):
    action: str


@router.post("/documents/{doc_id}/revisions/{revision_id}/state")
def state(
    doc_id: str,
    revision_id: str,
    payload: StateInput,
    user: User = Depends(current),
    session: Session = Depends(db),
):
    d = get(session, Document, doc_id)
    owner(session, d.workspace_id, user)
    r = revision_for(session, doc_id, revision_id)
    if d.kind != "curriculum":
        fail("Only curriculum proposals have approval states.", 400)
    transitions = {("pending", "reject"): "rejected", ("rejected", "reopen"): "pending"}
    new = transitions.get((r.status, payload.action))
    if not new:
        fail("Invalid proposal transition.")
    r.status = new
    audit(session, user, d.workspace_id, "proposal_" + payload.action, r.id)
    session.commit()
    return rev_data(r)


@router.post("/documents/{doc_id}/revisions/{revision_id}/restore")
def restore(
    doc_id: str,
    revision_id: str,
    user: User = Depends(current),
    session: Session = Depends(db),
):
    d = get(session, Document, doc_id)
    owner(session, d.workspace_id, user)
    r = revision_for(session, doc_id, revision_id)
    if d.kind == "transcript":
        fail("Transcripts are permanent run records.", 403)
    restored = add_revision(
        session,
        d,
        user,
        json.loads(json.dumps(r.content)),
        f"Restored from revision {r.number}",
        d.current_id,
    )
    session.commit()
    return rev_data(restored)


class CommentInput(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    block_id: str | None = None
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)


@router.post("/documents/{doc_id}/revisions/{revision_id}/comments")
def comment(
    doc_id: str,
    revision_id: str,
    payload: CommentInput,
    user: User = Depends(current),
    session: Session = Depends(db),
):
    d = get(session, Document, doc_id)
    r = revision_for(session, doc_id, revision_id)
    if d.kind == "transcript":
        fail("Comments are available on curricula and reports.", 400)
    quote = ""
    if payload.block_id:
        b = next(
            (b for b in text_units(r.content) if b["id"] == payload.block_id), None
        )
        if (
            not b
            or payload.start is None
            or payload.end is None
            or not 0 <= payload.start < payload.end <= len(b.get("text", ""))
        ):
            fail("Select a passage within one text block.", 400)
        quote = b["text"][payload.start : payload.end]
    t = Thread(
        document_id=d.id,
        revision_id=r.id,
        author_id=user.id,
        quote=quote,
        block_id=payload.block_id,
        start=payload.start,
        end=payload.end,
    )
    session.add(t)
    session.flush()
    session.add(
        Message(
            thread_id=t.id, author_id=user.id, author_name=user.name, text=payload.text
        )
    )
    audit(session, user, d.workspace_id, "comment_created", t.id)
    session.commit()
    return {"id": t.id}


class ReplyInput(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


@router.post("/comments/{thread_id}/replies")
def reply(
    thread_id: str,
    payload: ReplyInput,
    user: User = Depends(current),
    session: Session = Depends(db),
):
    t = get(session, Thread, thread_id)
    session.add(
        Message(
            thread_id=t.id, author_id=user.id, author_name=user.name, text=payload.text
        )
    )
    session.commit()
    return {"ok": True}


class ResolveInput(BaseModel):
    resolved: bool


@router.put("/comments/{thread_id}/state")
def resolve(
    thread_id: str,
    payload: ResolveInput,
    user: User = Depends(current),
    session: Session = Depends(db),
):
    t = get(session, Thread, thread_id)
    d = get(session, Document, t.document_id)
    w = get(session, Workspace, d.workspace_id)
    if session.get(BuilderWorkspace, w.id) and user.id != w.owner_id:
        fail("Only the workspace owner can resolve builder review comments.", 403)
    if user.id not in (t.author_id, w.owner_id):
        fail(
            "Only the thread author or workspace owner can resolve or reopen this discussion.",
            403,
        )
    t.resolved = payload.resolved
    audit(
        session,
        user,
        w.id,
        "comment_resolved" if t.resolved else "comment_reopened",
        t.id,
    )
    session.commit()
    return {"ok": True}


@router.get("/documents/{doc_id}/revisions/{revision_id}/export")
def export(
    doc_id: str,
    revision_id: str,
    format: str = "docx",
    comments: bool = False,
    user: User = Depends(current),
    session: Session = Depends(db),
):
    if format not in ("docx", "md"):
        fail("Choose docx or md.", 400)
    d = get(session, Document, doc_id)
    r = revision_for(session, doc_id, revision_id)
    snapshot = (
        [t for t in threads_for(session, d, r) if not t["resolved"]] if comments else []
    )
    snapshot = json.loads(json.dumps(snapshot, default=str))
    key = hashlib.sha256(
        json.dumps([r.id, format, "exporter-3", snapshot], sort_keys=True).encode()
    ).hexdigest()
    # Serialize cache creation across concurrent identical requests.
    session.execute(select(Revision).where(Revision.id == r.id).with_for_update())
    saved = session.scalar(select(Export).where(Export.key == key))
    if not saved:
        saved = Export(
            revision_id=r.id,
            key=key,
            format=format,
            snapshot=snapshot,
            data=export_bytes(d.title, r, format, snapshot),
        )
        session.add(saved)
        session.commit()
    return download(
        saved.data,
        f"{d.kind}-revision-{r.number}.{format}",
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if format == "docx"
            else "text/markdown; charset=utf-8"
        ),
    )


@router.get("/exports/{export_id}")
def saved_export(
    export_id: str, user: User = Depends(current), session: Session = Depends(db)
):
    saved = get(session, Export, export_id)
    r = get(session, Revision, saved.revision_id)
    d = get(session, Document, r.document_id)
    return download(
        saved.data,
        f"{d.kind}-revision-{r.number}.{saved.format}",
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if saved.format == "docx"
            else "text/markdown; charset=utf-8"
        ),
    )


def download(data, name, mime):
    from urllib.parse import quote

    return Response(
        data,
        media_type=mime,
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(name, safe=""),
            "X-Content-Type-Options": "nosniff",
        },
    )


class RunInput(BaseModel):
    revision_id: str | None = None
    kind: str = "review"
    instructions: str = Field(default="", max_length=16000)
    comment_ids: list[str] = Field(default_factory=list, max_length=100)


@router.post("/workspaces/{workspace_id}/runs")
def start_run(
    workspace_id: str,
    payload: RunInput,
    tasks: BackgroundTasks,
    user: User = Depends(current),
    session: Session = Depends(db),
):
    owner(session, workspace_id, user)
    if session.get(BuilderWorkspace, workspace_id):
        fail("Use the Builder workflow for this workspace; legacy runs cannot bypass its guidance and review checks.")
    if payload.kind not in ("review", "generate"):
        fail("Invalid run type.", 400)
    curriculum = session.scalar(
        select(Document).where(
            Document.workspace_id == workspace_id, Document.kind == "curriculum"
        )
    )
    r = (
        revision_for(session, curriculum.id, payload.revision_id)
        if payload.revision_id
        else None
    )
    if payload.kind == "review" and not r:
        fail("Select a curriculum revision to review.", 400)
    if not r and not payload.instructions.strip():
        fail("Provide instructions for the initial curriculum.", 400)
    selected = []
    visible = {t["id"] for t in threads_for(session, curriculum, r)} if r else set()
    for tid in payload.comment_ids:
        t = get(session, Thread, tid)
        if tid not in visible or t.resolved:
            fail("Select unresolved comments on the chosen revision.", 400)
        selected.append(
            {
                "quote": t.quote,
                "messages": [
                    m.text
                    for m in session.scalars(
                        select(Message)
                        .where(Message.thread_id == tid)
                        .order_by(Message.created)
                    )
                ],
            }
        )
    prompt = (
        "Review this curriculum using the configured rubric. Return a structured Markdown review report with findings, evidence, and recommendations. Do not claim to have reviewed sources not provided."
        if payload.kind == "review"
        else "Return the complete revised curriculum in Markdown. Address the instructions and selected feedback. Preserve unaffected content."
    )
    source_content = json.loads(json.dumps(r.content)) if r else {"blocks": []}
    for b in source_content["blocks"]:
        if b["type"] == "image":
            b.update(type="paragraph", text="[[IMAGE:" + b["id"] + "]]")
    prompt += " Preserve any [[IMAGE:...]] markers in their original positions."
    prompt += (
        "\n\nOwner instructions:\n"
        + payload.instructions
        + "\n\nCurriculum (source material):\n"
        + (as_markdown(source_content) if r else "(Create an initial curriculum.)")
        + "\n\nSelected comments:\n"
        + json.dumps(selected)
    )
    run = ReviewRun(
        workspace_id=workspace_id,
        revision_id=r.id if r else None,
        author_id=user.id,
        kind=payload.kind,
        was_proposal=bool(r and r.status == "pending"),
        entries=[
            {"timestamp": now().isoformat(), "text": "Run started. Request:\n" + prompt}
        ],
    )
    session.add(run)
    session.flush()
    audit(session, user, workspace_id, "run_started", run.id)
    session.commit()
    tasks.add_task(execute_run, run.id, prompt, payload.comment_ids)
    return {"id": run.id}


def freeze_transcript(session, run, user):
    d = Document(
        workspace_id=run.workspace_id,
        kind="transcript",
        title=f"{run.kind.title()} run transcript",
    )
    session.add(d)
    session.flush()
    content = {
        "blocks": [
            {
                "id": str(uuid4()),
                "type": "paragraph",
                "text": entry["timestamp"] + " — " + entry["text"],
            }
            for entry in run.entries
        ],
        "warnings": [],
    }
    add_revision(session, d, user, content, "Permanent run transcript")
    run.transcript_id = d.id


async def execute_run(run_id, prompt, comment_ids):
    try:
        result = await request_completion(prompt)
        with Session(engine) as session:
            run = session.scalar(
                select(ReviewRun).where(ReviewRun.id == run_id).with_for_update()
            )
            if run.status != "running":
                return
            w = session.scalar(
                select(Workspace)
                .where(Workspace.id == run.workspace_id)
                .with_for_update()
            )
            user = get(session, User, run.author_id)
            content = markdown(result["text"])
            if run.kind == "generate" and run.revision_id:
                source = get(session, Revision, run.revision_id)
                images = {
                    b["id"]: b for b in source.content["blocks"] if b["type"] == "image"
                }
                kept = set()
                for index, b in enumerate(content["blocks"]):
                    for image_id, image in images.items():
                        if b.get("text", "").strip() == "[[IMAGE:" + image_id + "]]":
                            content["blocks"][index] = image
                            kept.add(image_id)
                if len(kept) < len(images):
                    content["warnings"].append(
                        "This generated proposal omits source images. Check the original before acceptance."
                    )
            if not text_of(content).strip() or len(text_of(content)) > MAX_TEXT:
                raise ValueError("Provider returned an empty or oversized document.")
            if run.kind == "review":
                d = Document(
                    workspace_id=w.id,
                    kind="report",
                    title="Review report " + run.created.strftime("%Y-%m-%d %H:%M"),
                )
                session.add(d)
                session.flush()
                run.report_id = d.id
            else:
                d = session.scalar(
                    select(Document).where(
                        Document.workspace_id == w.id, Document.kind == "curriculum"
                    )
                )
            r = add_revision(
                session,
                d,
                user,
                content,
                "Generated by " + result["model"],
                run.revision_id if run.kind == "generate" else None,
                comment_ids,
            )
            run.result_id = r.id
            run.status = "completed"
            run.entries = run.entries + [
                {"timestamp": now().isoformat(), "text": result["text"]}
            ]
            freeze_transcript(session, run, user)
            session.commit()
    except Exception as exc:
        logging.getLogger(__name__).exception("Document run failed: %s", run_id)
        with Session(engine) as session:
            run = session.scalar(
                select(ReviewRun).where(ReviewRun.id == run_id).with_for_update()
            )
            if not run or run.status != "running":
                return
            run.status = "failed"
            run.entries = run.entries + [
                {
                    "timestamp": now().isoformat(),
                    "text": (
                        exc.detail
                        if isinstance(exc, HTTPException)
                        else "Run failed while processing the result. Retry or check server logs."
                    ),
                }
            ]
            freeze_transcript(session, run, get(session, User, run.author_id))
            session.commit()


@router.post("/runs/{run_id}/stop")
def stop(run_id: str, user: User = Depends(current), session: Session = Depends(db)):
    run = session.scalar(
        select(ReviewRun).where(ReviewRun.id == run_id).with_for_update()
    )
    if not run:
        fail("Run not found.", 404)
    owner(session, run.workspace_id, user)
    if run.status != "running":
        fail("This run has already stopped.")
    run.status = "stopped"
    run.entries = run.entries + [
        {
            "timestamp": now().isoformat(),
            "text": "Stopped by the workspace owner. Any later provider response will be discarded.",
        }
    ]
    freeze_transcript(session, run, user)
    audit(session, user, run.workspace_id, "run_stopped", run.id)
    session.commit()
    return {"ok": True}


def recover_runs():
    with Session(engine) as session:
        for run in session.scalars(
            select(ReviewRun).where(ReviewRun.status == "running").with_for_update()
        ):
            run.status = "interrupted"
            run.entries = run.entries + [
                {
                    "timestamp": now().isoformat(),
                    "text": "Run interrupted by application restart.",
                }
            ]
            freeze_transcript(session, run, get(session, User, run.author_id))
        session.commit()
