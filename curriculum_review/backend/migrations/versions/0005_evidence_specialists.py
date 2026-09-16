"""Immutable evidence index, shared references and bounded specialist tasks."""
from alembic import op
from app.models import ReferenceVersion, EvidencePassage, SpecialistTask

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    for model in (ReferenceVersion, EvidencePassage, SpecialistTask):
        model.__table__.create(op.get_bind())


def downgrade():
    for model in (SpecialistTask, EvidencePassage, ReferenceVersion):
        model.__table__.drop(op.get_bind())
