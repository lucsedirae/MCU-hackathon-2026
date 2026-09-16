"""Add isolated course-builder state without changing legacy workspaces."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("framework_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("model", sa.String(), nullable=False), sa.Column("version", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False), sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False), sa.Column("original", sa.LargeBinary(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False), sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("author_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("model", "version"))
    op.create_table("builder_workspaces",
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False), sa.Column("model", sa.String(), nullable=False),
        sa.Column("framework_id", sa.String(), sa.ForeignKey("framework_versions.id")),
        sa.Column("state", sa.JSON(), nullable=False), sa.Column("state_version", sa.Integer(), nullable=False))
    op.create_table("builder_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("role", sa.String(), nullable=False), sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False))
    op.create_table("builder_tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("author_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False), sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False), sa.Column("created", sa.DateTime(timezone=True), nullable=False))
    op.create_table("builder_proposals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("task_id", sa.String(), sa.ForeignKey("builder_tasks.id")),
        sa.Column("title", sa.String(), nullable=False), sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False), sa.Column("material", sa.Boolean(), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        sa.Column("disposition", sa.Text(), nullable=False),
        sa.Column("verified_by", sa.String(), sa.ForeignKey("users.id")),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    for name in ("builder_proposals", "builder_tasks", "builder_entries", "builder_workspaces", "framework_versions"):
        op.drop_table(name)
