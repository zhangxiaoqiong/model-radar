"""Analytical warehouse baseline.

Revision ID: 20260923_warehouse
"""
from alembic import op
from backend_core.db import Base
import backend_core.domain  # noqa: F401
revision="20260923_warehouse"
down_revision=None
branch_labels=None
depends_on=None
def upgrade(): Base.metadata.create_all(bind=op.get_bind(),checkfirst=True)
def downgrade(): Base.metadata.drop_all(bind=op.get_bind(),checkfirst=True)
