"""index evaluation supersedes relation

Revision ID: 7f33a86b9821
Revises: 103e182d1af9
Create Date: 2026-09-21
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = "7f33a86b9821"
down_revision: Union[str, Sequence[str], None] = "103e182d1af9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    index_name = "ix_evaluation_supersedes_evaluation_id"
    existing = {item["name"] for item in inspect(op.get_bind()).get_indexes("evaluation")}
    if index_name not in existing:
        op.create_index(index_name, "evaluation", ["supersedes_evaluation_id"], unique=False)


def downgrade() -> None:
    index_name = "ix_evaluation_supersedes_evaluation_id"
    existing = {item["name"] for item in inspect(op.get_bind()).get_indexes("evaluation")}
    if index_name in existing:
        op.drop_index(index_name, table_name="evaluation")
