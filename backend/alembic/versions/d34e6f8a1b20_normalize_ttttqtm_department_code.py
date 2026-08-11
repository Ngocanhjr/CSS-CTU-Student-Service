"""Normalize the information technology department code.

Revision ID: d34e6f8a1b20
Revises: c12d4e7f9a10
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d34e6f8a1b20"
down_revision: Union[str, Sequence[str], None] = "c12d4e7f9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE css.departments "
        "SET code = 'TTTTQTM' "
        "WHERE code = 'TTTT&QTM'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE css.departments "
        "SET code = 'TTTT&QTM' "
        "WHERE code = 'TTTTQTM'"
    )
