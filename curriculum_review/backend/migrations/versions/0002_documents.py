"""Accounts, document history, proposals, and collaboration."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE users (
	id VARCHAR NOT NULL, 
	email VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	password TEXT NOT NULL, 
	admin BOOLEAN NOT NULL, 
	must_change BOOLEAN NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
)

""")
    op.execute("""
CREATE TABLE login_sessions (
	token_hash VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	expires TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

""")
    op.execute("""
CREATE TABLE workspaces (
	id VARCHAR NOT NULL, 
	title VARCHAR NOT NULL, 
	owner_id VARCHAR NOT NULL, 
	created TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
)

""")
    op.execute("""
CREATE TABLE audit_events (
	id VARCHAR NOT NULL, 
	workspace_id VARCHAR, 
	user_id VARCHAR NOT NULL, 
	action VARCHAR NOT NULL, 
	target_id VARCHAR NOT NULL, 
	detail JSON, 
	created TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

""")
    op.execute("""
CREATE TABLE documents (
	id VARCHAR NOT NULL, 
	workspace_id VARCHAR NOT NULL, 
	kind VARCHAR NOT NULL, 
	title VARCHAR NOT NULL, 
	current_id VARCHAR, 
	created TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)

""")
    op.execute("CREATE INDEX ix_documents_workspace_id ON documents (workspace_id)")
    op.execute("""
CREATE TABLE document_revisions (
	id VARCHAR NOT NULL, 
	document_id VARCHAR NOT NULL, 
	number INTEGER NOT NULL, 
	base_id VARCHAR, 
	author_id VARCHAR NOT NULL, 
	content JSON NOT NULL, 
	content_hash VARCHAR NOT NULL, 
	description TEXT, 
	status VARCHAR NOT NULL, 
	selected_comments JSON, 
	created TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (document_id, number), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(base_id) REFERENCES document_revisions (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
)

""")
    op.execute(
        "CREATE INDEX ix_document_revisions_document_id ON document_revisions (document_id)"
    )
    op.execute("""
CREATE TABLE comment_threads (
	id VARCHAR NOT NULL, 
	document_id VARCHAR NOT NULL, 
	revision_id VARCHAR NOT NULL, 
	author_id VARCHAR, 
	quote TEXT, 
	block_id VARCHAR, 
	start INTEGER, 
	"end" INTEGER, 
	resolved BOOLEAN NOT NULL, 
	created TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(revision_id) REFERENCES document_revisions (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
)

""")
    op.execute(
        "CREATE INDEX ix_comment_threads_document_id ON comment_threads (document_id)"
    )
    op.execute("""
CREATE TABLE document_exports (
	id VARCHAR NOT NULL, 
	revision_id VARCHAR NOT NULL, 
	key VARCHAR NOT NULL, 
	format VARCHAR NOT NULL, 
	snapshot JSON NOT NULL, 
	data BYTEA NOT NULL, 
	created TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(revision_id) REFERENCES document_revisions (id), 
	UNIQUE (key)
)

""")
    op.execute("""
CREATE TABLE original_uploads (
	id VARCHAR NOT NULL, 
	revision_id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	data BYTEA NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(revision_id) REFERENCES document_revisions (id)
)

""")
    op.execute("""
CREATE TABLE review_runs (
	id VARCHAR NOT NULL, 
	workspace_id VARCHAR NOT NULL, 
	revision_id VARCHAR, 
	author_id VARCHAR NOT NULL, 
	kind VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	was_proposal BOOLEAN, 
	entries JSON, 
	report_id VARCHAR, 
	result_id VARCHAR, 
	transcript_id VARCHAR, 
	created TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	FOREIGN KEY(revision_id) REFERENCES document_revisions (id), 
	FOREIGN KEY(author_id) REFERENCES users (id), 
	FOREIGN KEY(report_id) REFERENCES documents (id), 
	FOREIGN KEY(result_id) REFERENCES document_revisions (id), 
	FOREIGN KEY(transcript_id) REFERENCES documents (id)
)

""")
    op.execute("""
CREATE TABLE comment_messages (
	id VARCHAR NOT NULL, 
	thread_id VARCHAR NOT NULL, 
	author_id VARCHAR, 
	author_name VARCHAR NOT NULL, 
	text TEXT NOT NULL, 
	source_date VARCHAR, 
	created TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(thread_id) REFERENCES comment_threads (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
)

""")
    op.execute(
        "CREATE INDEX ix_comment_messages_thread_id ON comment_messages (thread_id)"
    )


def downgrade():
    op.drop_table("comment_messages")
    op.drop_table("review_runs")
    op.drop_table("original_uploads")
    op.drop_table("document_exports")
    op.drop_table("comment_threads")
    op.drop_table("document_revisions")
    op.drop_table("documents")
    op.drop_table("audit_events")
    op.drop_table("workspaces")
    op.drop_table("login_sessions")
    op.drop_table("users")
