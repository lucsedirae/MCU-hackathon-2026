"""Versioned framework retrieval and owner-verified builder review workflow.

Legacy document endpoints remain intact. AI outputs are proposals, never project state.
"""
import hashlib
import io
import json
import re
import zipfile
from uuid import uuid4
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current, administrator, db
from app.database import engine
from app.models import (User, Workspace, Document, Revision, Original, Thread, Message,
    FrameworkVersion, BuilderWorkspace, BuilderEntry, BuilderTask, BuilderProposal, ReferenceVersion, SpecialistTask, now)
from app import knowledge
from app.uploads import read_upload
from app.documents import owner, get, fail, serialize, add_revision, doc_data
from app.content import import_file, text_of, text_units, fingerprint, markdown, export_bytes, MAX_UPLOAD
from app.llm import read_settings, request_completion

router = APIRouter(prefix="/api", tags=["Course builder"])
INSTRUCTIONS = Path(__file__).parent / "instructions"


def instructions(role):
    policy = (INSTRUCTIONS / "shared.md").read_text() + "\n\n" + (INSTRUCTIONS / f"{role}.md").read_text()
    if role in {"planner", "guidance"}:
        policy += "\n\n" + (INSTRUCTIONS / "conversation.md").read_text()
    return policy


def framework_data(f):
    return {**serialize(f, "id model version title content_hash filename published"), "created": f.created.isoformat()}


@router.get("/frameworks")
def frameworks(user: User = Depends(current), session: Session = Depends(db)):
    query = select(FrameworkVersion).order_by(FrameworkVersion.created.desc())
    if not user.admin:
        query = query.where(FrameworkVersion.published.is_(True))
    return [framework_data(f) for f in session.scalars(query)]


@router.post("/frameworks")
async def upload_framework(file: UploadFile = File(...), version: str = Form(...),
    model: Literal["ADDIE"] = Form(...), user: User = Depends(administrator), session: Session = Depends(db)):
    version = version.strip()
    if not version or len(version) > 80:
        fail("Provide a version of up to 80 characters.", 400)
    if session.scalar(select(FrameworkVersion).where(FrameworkVersion.model == model, FrameworkVersion.version == version)):
        fail("That framework version already exists. Use a new version; existing versions are immutable.")
    data = await file.read(MAX_UPLOAD + 1)
    content, _ = import_file(file.filename or "", data)
    if not text_of(content).strip():
        fail("Framework guidance must contain readable text.", 400)
    f = FrameworkVersion(model=model, version=version, title=f"{model} guidance", content=content,
        content_hash=fingerprint(content), original=data, filename=file.filename,
        author_id=user.id, published=False)
    session.add(f); session.flush()
    knowledge.index_content(session, "framework", f.id, content)
    session.commit()
    return framework_data(f)


@router.get("/frameworks/{fid}")
def framework_detail(fid: str, user: User = Depends(current), session: Session = Depends(db)):
    f = get(session, FrameworkVersion, fid)
    if not f.published and not user.admin:
        fail("Framework is not published.", 404)
    return {**framework_data(f), "content": f.content}


@router.post("/frameworks/{fid}/publish")
def publish_framework(fid: str, user: User = Depends(administrator), session: Session = Depends(db)):
    f = get(session, FrameworkVersion, fid)
    f.published = True
    session.commit()
    return framework_data(f)


def retrieve(f, query, limit=18000):
    """Deterministic lexical retrieval, preserving stable block IDs and omissions."""
    terms = set(re.findall(r"\w{3,}", query.lower()))
    units = [{"id": u["id"], "text": u.get("text", "")} for u in text_units(f.content) if u.get("text", "").strip()]
    ranked = sorted(enumerate(units), key=lambda x: (-len(terms & set(re.findall(r"\w{3,}", x[1]["text"].lower()))), x[0]))
    selected, used = [], 0
    for i, unit in ranked:
        if used + len(unit["text"]) <= limit:
            selected.append((i, unit)); used += len(unit["text"])
    return {"framework": framework_data(f), "passages": [u for _, u in sorted(selected)],
        "omitted_passages": len(units) - len(selected), "method": "lexical-block-ranking"}


@router.get("/frameworks/{fid}/search")
def search_framework(fid: str, q: str = "phase requirements exit criteria", user: User = Depends(current), session: Session = Depends(db)):
    f = get(session, FrameworkVersion, fid)
    if not f.published and not user.admin:
        fail("Framework is not published.", 404)
    return retrieve(f, q[:2000])


class NewWorkspace(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    mode: Literal["review", "creation"] = "review"
    framework_id: str | None = None


@router.post("/builder/workspaces")
def create_builder(payload: NewWorkspace, user: User = Depends(current), session: Session = Depends(db)):
    if not payload.title.strip():
        fail("Enter a workspace title.", 400)
    model = read_settings().get("instructional_model", "ADDIE")
    if model != "ADDIE":
        fail("The configured instructional model is not supported.")
    f = get(session, FrameworkVersion, payload.framework_id) if payload.framework_id else latest_guidance(session, model)
    if f and (not f.published or f.model != model):
        fail("Choose published guidance for the configured model.")
    w = Workspace(title=payload.title.strip(), owner_id=user.id)
    session.add(w); session.flush()
    session.add(BuilderWorkspace(workspace_id=w.id, mode=payload.mode, model=model, framework_id=f.id if f else None))
    session.commit()
    return {"id": w.id}


def latest_guidance(session, model):
    return session.scalar(select(FrameworkVersion).where(
        FrameworkVersion.model == model, FrameworkVersion.published.is_(True)
    ).order_by(FrameworkVersion.created.desc(), FrameworkVersion.id).limit(1))


def ensure_guidance(session, b):
    # Bind only once. Publishing a newer version never changes a pinned workspace.
    if not b.framework_id:
        f = latest_guidance(session, b.model)
        if f:
            b.framework_id = f.id


@router.post("/builder/workspaces/{wid}/prepare")
def prepare(wid: str, user: User = Depends(current), session: Session = Depends(db)):
    owner(session, wid, user)
    b = config(session, wid)
    ensure_guidance(session, b)
    session.commit()
    return {"framework_id": b.framework_id}


def config(session, wid):
    return get(session, BuilderWorkspace, wid)


def sources(session, wid):
    result = []
    for d in session.scalars(select(Document).where(Document.workspace_id == wid, Document.kind == "source").order_by(Document.created, Document.id)):
        r = get(session, Revision, d.current_id)
        result.append({"id": d.id, "title": d.title, "revision_id": r.id,
            "units": [{"id": u["id"], "text": u.get("text", "")} for u in text_units(r.content)], "warnings": r.content.get("warnings", []) + (["Source images are retained but are not analyzed by this review."] if any(x["type"] == "image" for x in r.content["blocks"]) else [])})
    return result


def entries(session, wid):
    return [serialize(e, "id role text created") for e in session.scalars(select(BuilderEntry).where(BuilderEntry.workspace_id == wid).order_by(BuilderEntry.created, BuilderEntry.id))]


@router.get("/builder/workspaces/{wid}")
def builder_detail(wid: str, user: User = Depends(current), session: Session = Depends(db)):
    b = config(session, wid)
    return {**serialize(b, "workspace_id mode model framework_id state state_version"),
        "framework": framework_data(get(session, FrameworkVersion, b.framework_id)) if b.framework_id else None,
        "entries": entries(session, wid), "sources": sources(session, wid),
        "tasks": [{**serialize(t, "id action status result error created"), "approval_current": bool(t.result.get("approval") and unchanged(session, t) and get(session, Document, t.result["report_id"]).current_id == t.result["report_revision_id"])} for t in session.scalars(select(BuilderTask).where(BuilderTask.workspace_id == wid).order_by(BuilderTask.created.desc()))],
        "proposals": [serialize(p, "id task_id title rationale impact material state_version status disposition verified_by verified_at created") for p in session.scalars(select(BuilderProposal).where(BuilderProposal.workspace_id == wid).order_by(BuilderProposal.created))]}


@router.get("/builder/workspaces/{wid}/progress")
def builder_progress(wid: str, user: User = Depends(current), session: Session = Depends(db)):
    """Persisted activity only; omit source text, prompts and private model reasoning."""
    b = config(session, wid)
    return {"model": b.model, "framework_ready": bool(b.framework_id),
        "events": [serialize(e, "id text created") for e in session.scalars(select(BuilderEntry).where(
            BuilderEntry.workspace_id == wid, BuilderEntry.role == "system").order_by(BuilderEntry.created, BuilderEntry.id))],
        "tasks": [{**serialize(t, "id action status created"),
            "coverage": {k: t.result.get("coverage", {}).get(k) for k in ("scope", "examined", "total", "complete")}}
            for t in session.scalars(select(BuilderTask).where(BuilderTask.workspace_id == wid).order_by(BuilderTask.created.desc()))]}


class BindFramework(BaseModel):
    framework_id: str


@router.post("/builder/workspaces/{wid}/framework")
def bind_framework(wid: str, payload: BindFramework, user: User = Depends(current), session: Session = Depends(db)):
    owner(session, wid, user); b = config(session, wid)
    if b.framework_id:
        fail("Guidance is already pinned. Changing its version is not supported in this release.")
    f = get(session, FrameworkVersion, payload.framework_id)
    if not f.published or f.model != b.model:
        fail("Choose published guidance matching this workspace's model.")
    b.framework_id = f.id
    session.commit()
    return {"ok": True}


@router.post("/builder/workspaces/{wid}/sources")
async def upload_source(wid: str, file: UploadFile = File(...), user: User = Depends(current), session: Session = Depends(db)):
    owner(session, wid, user); config(session, wid)
    content, comments, original = await read_upload(file, session)
    if not text_of(content).strip():
        fail("No readable source text was found. Submit a text-based document.", 400)
    d = Document(workspace_id=wid, kind="source", title=(file.filename or "Source")[:200])
    session.add(d); session.flush()
    r = add_revision(session, d, user, content, "Source upload; not verified project state")
    session.add(Original(revision_id=r.id, name=file.filename or "Source", **original))
    knowledge.index_content(session, "source", r.id, content)
    # Preserve imported comments as general review material, never established state.
    for c in comments:
        t = Thread(document_id=d.id, revision_id=r.id, author_id=user.id, quote=c.get("quote", ""))
        session.add(t); session.flush()
        session.add(Message(thread_id=t.id, author_name=c.get("author", "Imported reviewer"), text=c.get("text") or "(Empty imported comment)"))
    session.add(BuilderEntry(workspace_id=wid, role="system", text=f"Uploaded {d.title}. Stored as source material; project state unchanged."))
    session.commit()
    return doc_data(d)


class ChatInput(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    action: Literal["record", "interview", "review", "chat"] = "chat"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Finding(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=4000)
    impact: str = Field(min_length=1, max_length=4000)
    material: bool


class Comment(StrictModel):
    revision_id: str
    block_id: str
    quote: str = Field(max_length=5000)
    text: str = Field(min_length=1, max_length=5000)


class DocumentAssessment(StrictModel):
    revision_id: str
    confidence: Literal["High", "Moderate", "Low"]
    rationale: str = Field(min_length=1, max_length=4000)
    gaps: list[str] = Field(max_length=30)
    peer_review: str = Field(min_length=1, max_length=4000)


class CoordinatorOutput(StrictModel):
    reply: str = Field(min_length=1, max_length=20000)
    ready_for_review: bool
    report_markdown: str = Field(default="", max_length=100000)
    proposals: list[Finding] = Field(default_factory=list, max_length=30)
    comments: list[Comment] = Field(default_factory=list, max_length=80)
    assessments: list[DocumentAssessment] = Field(default_factory=list, max_length=100)


class QualityOutput(StrictModel):
    passed: bool
    findings: list[str] = Field(max_length=40)
    confidence: Literal["High", "Moderate", "Low"]
    rationale: str = Field(min_length=1, max_length=5000)
    peer_review: str = Field(min_length=1, max_length=5000)


def parse_output(text, schema):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return schema.model_validate_json(text)


def model_context(context):
    """A small orientation, not a claim that retrieved excerpts are complete evidence."""
    return {k: context[k] for k in ("mode", "model", "state_digest", "sources", "conversation",
        "conversation_omitted", "proposed_changes", "latest_report", "review_guidance", "references", "query")}


def snapshot(session, wid, query, require_sources=True):
    b = config(session, wid)
    if not b.framework_id:
        fail("Published guidance for this instructional model is not available yet. Your administrator must publish it; this workspace will use it automatically. Uploads and intake notes remain available.")
    f = get(session, FrameworkVersion, b.framework_id)
    knowledge.index_content(session, "framework", f.id, f.content)
    src = []
    for d in session.scalars(select(Document).where(Document.workspace_id == wid, Document.kind == "source").order_by(Document.created, Document.id)):
        r = get(session, Revision, d.current_id)
        passages = knowledge.index_content(session, "source", r.id, r.content)
        src.append({"id": d.id, "title": d.title, "revision_id": r.id, "passage_count": len(passages),
            "warnings": r.content.get("warnings", []) + (["Images are retained but not analyzed."] if any(x["type"] == "image" for x in r.content["blocks"]) else [])})
    if not src and require_sources:
        fail("Upload source documents first: existing curriculum, governing requirements, objectives, or assessment materials.")
    refs = []
    titles = set()
    for ref in session.scalars(select(ReferenceVersion).where(ReferenceVersion.published.is_(True)).order_by(ReferenceVersion.created.desc(), ReferenceVersion.id)):
        if ref.title in titles: continue
        titles.add(ref.title)
        knowledge.index_content(session, "reference", ref.id, ref.content)
        refs.append(knowledge.reference_data(ref))
    history = entries(session, wid)
    proposals = [serialize(p, "id title rationale impact material status disposition") for p in session.scalars(
        select(BuilderProposal).where(BuilderProposal.workspace_id == wid).order_by(BuilderProposal.created))]
    report = session.scalar(select(Document).where(Document.workspace_id == wid, Document.kind == "report").order_by(Document.created.desc()).limit(1))
    latest = None
    if report and report.current_id:
        r = get(session, Revision, report.current_id)
        knowledge.index_content(session, "report", r.id, r.content)
        latest = {"revision_id": r.id, "note": "Working report, not established state. Retrieve passages for details."}
    # Older conversation, full decisions and proposals remain retrievable, not silently lost.
    context_version = str(uuid4())
    context_text = json.dumps({"conversation": history, "verified_state": b.state, "proposals": proposals}, default=str)
    knowledge.index_content(session, "context", context_version, markdown(context_text))
    recent = [{"role": e["role"], "text": e["text"][:1500], "excerpt": len(e["text"]) > 1500} for e in history[-6:]]
    context = {"mode": b.mode, "model": b.model, "state": b.state, "state_version": b.state_version,
        "state_digest": [{"id": key, "title": value.get("title", "Verified decision")} for key, value in b.state.items()],
        "framework": {"framework": framework_data(f)}, "sources": src, "references": refs,
        "conversation": recent, "conversation_omitted": max(0, len(history)-6),
        "proposed_changes": [{k:p[k] for k in ("id", "title", "material", "status")} for p in proposals],
        "latest_report": latest, "query": query,
        "retrieval_scope": {"source": [x["revision_id"] for x in src], "framework": [f.id],
            "reference": [x["id"] for x in refs], "context": [context_version], "report": [report.current_id] if latest else []}}
    previous_guidance = next((task for task in session.scalars(select(BuilderTask).where(
        BuilderTask.workspace_id == wid, BuilderTask.status.in_(["completed", "needs_revision"])
    ).order_by(BuilderTask.created.desc())) if task.result.get("guidance")), None)
    context["review_guidance"] = ({"task_id": previous_guidance.id,
        "guidance": previous_guidance.result["guidance"], "evidence_current": unchanged(session, previous_guidance),
        "note": "Working review questions, not approved state. Check conversation for answers already given."} if previous_guidance else None)
    context["instructions"] = {role: instructions(role) for role in ("planner", "coordinator", "reviewer", "specialist", "guidance")}
    context["instruction_versions"] = {role: hashlib.sha256(value.encode()).hexdigest() for role, value in context["instructions"].items()}
    return context


@router.post("/builder/workspaces/{wid}/chat")
def chat(wid: str, payload: ChatInput, tasks: BackgroundTasks, user: User = Depends(current), session: Session = Depends(db)):
    owner(session, wid, user); b = config(session, wid)
    if not payload.text.strip():
        fail("Enter a message.", 400)
    if session.scalar(select(BuilderTask).where(BuilderTask.workspace_id == wid, BuilderTask.status == "running")):
        fail("Wait for the current task or stop it before sending another message.")
    if payload.action == "review" and b.mode != "review":
        fail("This is a creation workspace. Creation production is not enabled yet; use interview to prepare intake.")
    ensure_guidance(session, b)
    # Validate before saving a message so a rejected request is safe to retry.
    intake_only = payload.action == "chat" and not b.framework_id
    context = snapshot(session, wid, payload.text, require_sources=payload.action != "chat") if payload.action != "record" and not intake_only else None
    session.add(BuilderEntry(workspace_id=wid, role="user", text=payload.text.strip()))
    if context is None:
        if intake_only:
            session.add(BuilderEntry(workspace_id=wid, role="system", text="Your message is saved. The next step is to gather your existing course materials. Attach what you have; if you have no documents, describe the course and its learners. Instructional analysis is waiting for the administrator to publish the framework guidance. It will connect automatically; you do not need to configure it."))
        session.commit(); return {"saved": True}
    context["conversation"].append({"role": "user", "text": payload.text.strip()})
    context["owner_id"] = user.id
    task = BuilderTask(workspace_id=wid, author_id=user.id, action=payload.action, snapshot=context)
    session.add(task); session.commit()
    tasks.add_task(execute_task, task.id)
    return {"id": task.id}


def unchanged(session, task):
    b = config(session, task.workspace_id)
    w = get(session, Workspace, task.workspace_id)
    return (w.owner_id == task.author_id and b.state_version == task.snapshot["state_version"]
        and b.framework_id == task.snapshot["framework"]["framework"]["id"]
        and [(s["id"], s["revision_id"]) for s in sources(session, task.workspace_id)] == [(s["id"], s["revision_id"]) for s in task.snapshot["sources"]])


async def execute_task(tid):
    try:
        with Session(engine) as session:
            t = get(session, BuilderTask, tid)
            if t.status != "running": return
            context, action = dict(t.snapshot), t.action
            task_instructions = context.pop("instructions")
        from app.orchestration import orchestrate
        import sys
        context["instructions"] = task_instructions
        output, quality, provider_model, extra = await orchestrate(sys.modules[__name__], tid, context, action)
        with Session(engine) as session:
            t = get(session, BuilderTask, tid)
            # Lock workspace first, matching stop/approval/verification lock order.
            w = session.scalar(select(Workspace).where(Workspace.id == t.workspace_id).with_for_update())
            session.refresh(t, with_for_update=True)
            if t.status != "running": return
            if not unchanged(session, t):
                t.status = "stale"; t.error = "Sources, ownership or verified state changed. Run again against current evidence."
                session.commit(); return
            user = get(session, User, t.author_id)
            t.result = {**t.result, **extra, "coordinator": output.model_dump(), "quality": quality.model_dump() if quality else None,
                "provider_model": provider_model, "instruction_versions": context["instruction_versions"]}
            session.add(BuilderEntry(workspace_id=w.id, role="assistant", text=output.reply))
            for p in output.proposals:
                session.add(BuilderProposal(workspace_id=w.id, task_id=t.id, state_version=context["state_version"], **p.model_dump()))
            if quality and not quality.passed:
                t.status = "needs_revision"
                session.add(BuilderEntry(workspace_id=w.id, role="assistant", text="Quality review requires revision: " + "\n".join(quality.findings)))
            elif quality:
                report = Document(workspace_id=w.id, kind="report", title="Curriculum review report")
                session.add(report); session.flush()
                summary = ("\n\n## AI quality review\n\nEvidence confidence: " + quality.confidence + "\n\n" + quality.rationale
                    + "\n\nReadiness when generated: Needs review. Current owner approval is recorded separately in the application and export manifest.\n\nPeer review: " + quality.peer_review
                    + "\n\nFramework: " + context["framework"]["framework"]["title"] + " / " + context["framework"]["framework"]["version"])
                summary += "\n\n## Document confidence and readiness\n"
                names = {s["revision_id"]: s["title"] for s in context["sources"]}
                for a in output.assessments:
                    summary += ("\n### " + names[a.revision_id] + "\n\nRevision: " + a.revision_id
                        + "\n\nEvidence confidence: " + a.confidence + " — " + a.rationale
                        + "\n\nReadiness: Needs review.\n\nGaps: " + ("; ".join(a.gaps) or "None identified within assessed scope.")
                        + "\n\nPeer review: " + a.peer_review + "\n")
                r = add_revision(session, report, user, markdown(output.report_markdown + summary), "Coordinator draft checked by AI quality reviewer")
                t.result = {**t.result, "report_id": report.id, "report_revision_id": r.id}
                allowed = {s["revision_id"]: s for s in sources(session, w.id)}
                for c in output.comments:
                    if c.revision_id not in allowed: raise ValueError("Comment references an unknown source revision.")
                    source = allowed[c.revision_id]
                    units = {u["id"]: u["text"] for u in source["units"]}
                    found = c.quote and c.block_id in units and units[c.block_id].count(c.quote) == 1
                    start = units[c.block_id].index(c.quote) if found else None
                    thread = Thread(document_id=source["id"], revision_id=c.revision_id, author_id=None,
                        quote=c.quote if found else "", block_id=c.block_id if found else None,
                        start=start, end=start + len(c.quote) if found else None)
                    session.add(thread); session.flush()
                    text = c.text if found or not c.quote else "[Unplaced comment; verify original passage: " + c.quote + "]\n" + c.text
                    session.add(Message(thread_id=thread.id, author_name="Learning Expert (AI)", text=text))
                t.status = "completed"
            else:
                t.status = "completed" if action in ("interview", "chat") else "needs_information"
            session.commit()
    except Exception as exc:
        with Session(engine) as session:
            t = session.scalar(select(BuilderTask).where(BuilderTask.id == tid).with_for_update())
            if t and t.status == "running":
                t.status = "failed"
                from app.orchestration import Halt
                t.status = "incomplete" if isinstance(exc, Halt) else "failed"
                t.error = exc.detail if isinstance(exc, HTTPException) else str(exc) if isinstance(exc, (Halt, ValueError)) else "Review could not complete. Findings already recorded are retained; no final report was applied. Retry with current evidence."
                if isinstance(exc, ValidationError):
                    t.error = "The AI response did not satisfy the review contract: " + "; ".join(".".join(map(str, e["loc"])) + ": " + e["msg"] for e in exc.errors(include_input=False)[:3])
                session.add(BuilderEntry(workspace_id=t.workspace_id, role="system", text=t.error))
                session.commit()


@router.post("/builder/tasks/{tid}/stop")
def stop_task(tid: str, user: User = Depends(current), session: Session = Depends(db)):
    t = get(session, BuilderTask, tid); owner(session, t.workspace_id, user); session.refresh(t)
    if t.status != "running": fail("Task has already finished.")
    t.status = "stopped"
    for child in session.scalars(select(SpecialistTask).where(SpecialistTask.parent_id == tid, SpecialistTask.status.in_(["pending", "running"]))):
        child.status = "stopped"
    session.commit()
    return {"ok": True}


class VerifyInput(BaseModel):
    decision: Literal["verify", "decline"]
    reason: str = Field(min_length=1, max_length=4000)
    expected_state_version: int


@router.post("/builder/proposals/{pid}/verify")
def verify(pid: str, payload: VerifyInput, user: User = Depends(current), session: Session = Depends(db)):
    p = get(session, BuilderProposal, pid); owner(session, p.workspace_id, user)
    session.refresh(p)
    b = config(session, p.workspace_id)
    if p.status != "pending": fail("This proposal has already been resolved.")
    if payload.expected_state_version != b.state_version: fail("Project state changed. Refresh and review the impact before confirming.")
    if not payload.reason.strip(): fail("Record your verification or decline reason.", 400)
    p.status = "verified" if payload.decision == "verify" else "declined"
    p.disposition = payload.reason.strip(); p.verified_by = user.id; p.verified_at = now()
    if p.status == "verified":
        b.state = {**b.state, p.id: {"title": p.title, "rationale": p.rationale, "impact": p.impact, "material": p.material}}
        b.state_version += 1
    session.commit()
    return {"ok": True}


@router.get("/builder/workspaces/{wid}/export")
def export_package(wid: str, user: User = Depends(current), session: Session = Depends(db)):
    b = config(session, wid)
    transcript = "\n\n".join(f"{e['created'].isoformat()} — {e['role']}\n{e['text']}" for e in entries(session, wid))
    verified = list(session.scalars(select(BuilderProposal).where(BuilderProposal.workspace_id == wid, BuilderProposal.status == "verified").order_by(BuilderProposal.created)))
    history = "# Owner-verified project history\n\n" + "\n\n".join(f"## {p.title}\n\n{p.rationale}\n\nImpact: {p.impact}\n\nOwner verification: {p.disposition}\n\nVerified by: {p.verified_by} at {p.verified_at.isoformat() if p.verified_at else 'not recorded'}\n\nRecord: {p.id}" for p in verified)
    manifest = {"workspace_id": wid, "model": b.model, "framework_id": b.framework_id, "state_version": b.state_version, "documents": []}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("conversation.md", transcript)
        archive.writestr("verified-history.md", history)
        for d in session.scalars(select(Document).where(Document.workspace_id == wid, Document.kind == "report")):
            r = get(session, Revision, d.current_id)
            archive.writestr(f"report-{r.id}.docx", export_bytes(d.title, r, "docx", []))
            approval = None
            for candidate in session.scalars(select(BuilderTask).where(BuilderTask.workspace_id == wid)):
                if candidate.result.get("report_revision_id") == r.id and candidate.result.get("approval") and unchanged(session, candidate):
                    approval = candidate.result["approval"]
            manifest["documents"].append({"id": d.id, "revision_id": r.id, "content_hash": r.content_hash,
                "readiness": "Human-approved" if approval else "Needs review", "approval": approval})
        task_records = []
        for task in session.scalars(select(BuilderTask).where(BuilderTask.workspace_id == wid)):
            children = [serialize(c, "id role stage status assignment result error created") for c in session.scalars(select(SpecialistTask).where(SpecialistTask.parent_id == task.id))]
            task_records.append({"id": task.id, "status": task.status, "result": task.result, "specialists": children})
        archive.writestr("review-activity.json", json.dumps(task_records, indent=2, default=str))
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    return Response(stream.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="curriculum-review-package.zip"'})


def recover_builder_tasks():
    with Session(engine) as session:
        for t in session.scalars(select(BuilderTask).where(BuilderTask.status == "running")):
            t.status = "interrupted"; t.error = "Application restarted. Retry; no late result will be applied."
        for child in session.scalars(select(SpecialistTask).where(SpecialistTask.status.in_(["pending", "running"]))):
            child.status = "interrupted"; child.error = "Restarted; start a fresh review against current evidence."
        session.commit()


class ReportApproval(BaseModel):
    revision_id: str
    peer_review: Literal["requested", "completed", "declined"]
    reason: str = Field(min_length=1, max_length=4000)


@router.post("/builder/tasks/{tid}/approve-report")
def approve_report(tid: str, payload: ReportApproval, user: User = Depends(current), session: Session = Depends(db)):
    t = get(session, BuilderTask, tid); owner(session, t.workspace_id, user); session.refresh(t)
    if t.status != "completed" or not t.result.get("report_id") or not t.result.get("quality", {}).get("passed"):
        fail("A completed, quality-checked report is required.")
    if t.result.get("coverage", {}).get("scope") == "quick": fail("Quick screening cannot be approved as a completed review.")
    if not t.result.get("coverage", {}).get("complete"): fail("Required source coverage is incomplete.")
    if t.result.get("material_blockers", 0): fail("Material findings remain. Resolve the underlying evidence gaps and run a fresh review; declining a recommendation does not remove a blocker.")
    if t.result.get("approval"): fail("This report is already approved.")
    d = get(session, Document, t.result["report_id"])
    if payload.revision_id != d.current_id or payload.revision_id != t.result["report_revision_id"]:
        fail("The report revision changed; a fresh review is required.")
    if not unchanged(session, t): fail("Sources or verified state changed; run a fresh review before approval.")
    if not payload.reason.strip(): fail("Record your review disposition.", 400)
    t.result = {**t.result, "approval": {"revision_id": payload.revision_id, "owner_id": user.id,
        "peer_review": payload.peer_review, "reason": payload.reason.strip(), "approved_at": now().isoformat()}}
    session.commit()
    return {"ok": True}


@router.get('/builder/tasks/{tid}/specialists')
def specialist_activity(tid: str, user: User = Depends(current), session: Session = Depends(db)):
    task = get(session, BuilderTask, tid)
    # Workspaces are team-readable; only the owner may initiate/mutate work.
    return [serialize(c, 'id role stage status assignment result error created') for c in session.scalars(
        select(SpecialistTask).where(SpecialistTask.parent_id == task.id).order_by(SpecialistTask.created))]


@router.get('/builder/tasks/{tid}/evidence/{pid}')
def task_evidence(tid: str, pid: str, user: User = Depends(current), session: Session = Depends(db)):
    task = get(session, BuilderTask, tid)
    try:
        passage = knowledge.read_passages(session, task.snapshot['retrieval_scope'], [pid])[0]
        if passage['collection'] == 'source':
            revision = get(session, Revision, passage['version_id'])
            passage['title'] = get(session, Document, revision.document_id).title
        elif passage['collection'] == 'reference':
            ref = get(session, ReferenceVersion, passage['version_id'])
            passage.update(title=ref.title, authority=ref.authority, source_url=ref.source_url)
        return passage
    except (ValueError, KeyError):
        fail('Evidence is not available in this review.', 404)


@router.get('/builder/instructions')
def effective_instructions(user: User = Depends(administrator)):
    return [{'role': role, 'version': hashlib.sha256(instructions(role).encode()).hexdigest(), 'text': instructions(role)}
        for role in ('planner', 'coordinator', 'specialist', 'reviewer', 'guidance')]
