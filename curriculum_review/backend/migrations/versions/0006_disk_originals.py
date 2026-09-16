"""Store large Moodle originals in a persistent upload volume."""
from alembic import op
import sqlalchemy as sa
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('original_uploads', 'data', existing_type=sa.LargeBinary(), nullable=True)
    op.add_column('original_uploads', sa.Column('storage_key', sa.String(), nullable=True))


def downgrade():
    # Disk-backed originals cannot be losslessly converted to bytea automatically.
    connection = op.get_bind()
    if connection.execute(sa.text('SELECT count(*) FROM original_uploads WHERE storage_key IS NOT NULL')).scalar():
        raise RuntimeError('Export disk-backed originals before downgrading this schema.')
    op.drop_column('original_uploads', 'storage_key')
    op.alter_column('original_uploads', 'data', existing_type=sa.LargeBinary(), nullable=False)
