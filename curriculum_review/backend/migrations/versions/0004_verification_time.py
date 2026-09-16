"""Record owner disposition time independently of proposal creation time."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("builder_proposals", sa.Column("verified_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("builder_proposals", "verified_at")
