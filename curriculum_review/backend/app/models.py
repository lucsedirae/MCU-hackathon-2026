"""Persistent collaboration records. Revision content is append-only through the API."""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    LargeBinary,
    UniqueConstraint,
)
from app.database import Base


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=uid)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    password = Column(Text, nullable=False)
    admin = Column(Boolean, default=False, nullable=False)
    must_change = Column(Boolean, default=True, nullable=False)
    active = Column(Boolean, default=True, nullable=False)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash = Column(String, primary_key=True)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    expires = Column(DateTime(timezone=True), nullable=False)


class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(String, primary_key=True, default=uid)
    title = Column(String, nullable=False)
    owner_id = Column(ForeignKey("users.id"), nullable=False)
    created = Column(DateTime(timezone=True), default=now, nullable=False)


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(ForeignKey("workspaces.id"), nullable=False, index=True)
    kind = Column(String, nullable=False)
    title = Column(String, nullable=False)
    current_id = Column(String)
    created = Column(DateTime(timezone=True), default=now, nullable=False)


class Revision(Base):
    __tablename__ = "document_revisions"
    __table_args__ = (UniqueConstraint("document_id", "number"),)
    id = Column(String, primary_key=True, default=uid)
    document_id = Column(ForeignKey("documents.id"), nullable=False, index=True)
    number = Column(Integer, nullable=False)
    base_id = Column(ForeignKey("document_revisions.id"))
    author_id = Column(ForeignKey("users.id"), nullable=False)
    content = Column(JSON, nullable=False)
    content_hash = Column(String, nullable=False)
    description = Column(Text, default="")
    status = Column(String, nullable=False)
    selected_comments = Column(JSON, default=list)
    created = Column(DateTime(timezone=True), default=now, nullable=False)


class Original(Base):
    __tablename__ = "original_uploads"
    id = Column(String, primary_key=True, default=uid)
    revision_id = Column(ForeignKey("document_revisions.id"), nullable=False)
    name = Column(String, nullable=False)
    data = Column(LargeBinary)
    storage_key = Column(String)


class ReviewRun(Base):
    __tablename__ = "review_runs"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(ForeignKey("workspaces.id"), nullable=False)
    revision_id = Column(ForeignKey("document_revisions.id"))
    author_id = Column(ForeignKey("users.id"), nullable=False)
    kind = Column(String, nullable=False)
    status = Column(String, default="running", nullable=False)
    was_proposal = Column(Boolean, default=False)
    entries = Column(JSON, default=list)
    report_id = Column(ForeignKey("documents.id"))
    result_id = Column(ForeignKey("document_revisions.id"))
    transcript_id = Column(ForeignKey("documents.id"))
    created = Column(DateTime(timezone=True), default=now)


class Thread(Base):
    __tablename__ = "comment_threads"
    id = Column(String, primary_key=True, default=uid)
    document_id = Column(ForeignKey("documents.id"), nullable=False, index=True)
    revision_id = Column(ForeignKey("document_revisions.id"), nullable=False)
    author_id = Column(ForeignKey("users.id"))
    quote = Column(Text, default="")
    block_id = Column(String)
    start = Column(Integer)
    end = Column(Integer)
    resolved = Column(Boolean, default=False, nullable=False)
    created = Column(DateTime(timezone=True), default=now)


class Message(Base):
    __tablename__ = "comment_messages"
    id = Column(String, primary_key=True, default=uid)
    thread_id = Column(ForeignKey("comment_threads.id"), nullable=False, index=True)
    author_id = Column(ForeignKey("users.id"))
    author_name = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    source_date = Column(String)
    created = Column(DateTime(timezone=True), default=now)


class Export(Base):
    __tablename__ = "document_exports"
    id = Column(String, primary_key=True, default=uid)
    revision_id = Column(ForeignKey("document_revisions.id"), nullable=False)
    key = Column(String, unique=True, nullable=False)
    format = Column(String, nullable=False)
    snapshot = Column(JSON, nullable=False)
    data = Column(LargeBinary, nullable=False)
    created = Column(DateTime(timezone=True), default=now)


class Audit(Base):
    __tablename__ = "audit_events"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(ForeignKey("workspaces.id"))
    user_id = Column(ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    target_id = Column(String, nullable=False)
    detail = Column(JSON, default=dict)
    created = Column(DateTime(timezone=True), default=now)


class FrameworkVersion(Base):
    __tablename__ = "framework_versions"
    id = Column(String, primary_key=True, default=uid)
    model = Column(String, nullable=False)
    version = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content = Column(JSON, nullable=False)
    content_hash = Column(String, nullable=False)
    original = Column(LargeBinary, nullable=False)
    filename = Column(String, nullable=False)
    published = Column(Boolean, default=False, nullable=False)
    author_id = Column(ForeignKey("users.id"), nullable=False)
    created = Column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (UniqueConstraint("model", "version"),)


class BuilderWorkspace(Base):
    __tablename__ = "builder_workspaces"
    workspace_id = Column(ForeignKey("workspaces.id"), primary_key=True)
    mode = Column(String, nullable=False)
    model = Column(String, nullable=False)
    framework_id = Column(ForeignKey("framework_versions.id"))
    state = Column(JSON, default=dict, nullable=False)
    state_version = Column(Integer, default=0, nullable=False)


class BuilderEntry(Base):
    __tablename__ = "builder_entries"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(ForeignKey("workspaces.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    created = Column(DateTime(timezone=True), default=now, nullable=False)


class BuilderTask(Base):
    __tablename__ = "builder_tasks"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(ForeignKey("workspaces.id"), nullable=False, index=True)
    author_id = Column(ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    status = Column(String, default="running", nullable=False)
    snapshot = Column(JSON, nullable=False)
    result = Column(JSON, default=dict, nullable=False)
    error = Column(Text, default="", nullable=False)
    created = Column(DateTime(timezone=True), default=now, nullable=False)


class BuilderProposal(Base):
    __tablename__ = "builder_proposals"
    id = Column(String, primary_key=True, default=uid)
    workspace_id = Column(ForeignKey("workspaces.id"), nullable=False, index=True)
    task_id = Column(ForeignKey("builder_tasks.id"))
    title = Column(String, nullable=False)
    rationale = Column(Text, nullable=False)
    impact = Column(Text, nullable=False)
    material = Column(Boolean, default=False, nullable=False)
    state_version = Column(Integer, nullable=False)
    status = Column(String, default="pending", nullable=False)
    disposition = Column(Text, default="", nullable=False)
    verified_by = Column(ForeignKey("users.id"))
    verified_at = Column(DateTime(timezone=True))
    created = Column(DateTime(timezone=True), default=now, nullable=False)


class ReferenceVersion(Base):
    __tablename__ = "reference_versions"
    id = Column(String, primary_key=True, default=uid)
    title = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    authority = Column(String, nullable=False)
    version = Column(String, nullable=False)
    source_url = Column(Text, default="", nullable=False)
    content = Column(JSON, nullable=False)
    original = Column(LargeBinary, nullable=False)
    filename = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    published = Column(Boolean, default=False, nullable=False)
    author_id = Column(ForeignKey("users.id"), nullable=False)
    created = Column(DateTime(timezone=True), default=now, nullable=False)
    __table_args__ = (UniqueConstraint("title", "version"),)


class EvidencePassage(Base):
    __tablename__ = "evidence_passages"
    id = Column(String, primary_key=True)
    collection = Column(String, nullable=False, index=True)
    version_id = Column(String, nullable=False, index=True)
    block_id = Column(String, nullable=False)
    ordinal = Column(Integer, nullable=False)
    start = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    terms = Column(JSON, nullable=False)
    index_version = Column(Integer, default=1, nullable=False)
    page = Column(Integer)


class SpecialistTask(Base):
    __tablename__ = "specialist_tasks"
    id = Column(String, primary_key=True, default=uid)
    parent_id = Column(ForeignKey("builder_tasks.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    stage = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    assignment = Column(JSON, nullable=False)
    result = Column(JSON, default=dict, nullable=False)
    error = Column(Text, default="", nullable=False)
    created = Column(DateTime(timezone=True), default=now, nullable=False)
