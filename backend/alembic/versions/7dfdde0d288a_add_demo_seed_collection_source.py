"""add_demo_seed_collection_source

Revision ID: 7dfdde0d288a
Revises: 19fd13563cb9
Create Date: 2026-06-30 15:17:33.216387

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7dfdde0d288a'
down_revision: Union[str, None] = '19fd13563cb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE collection_source_enum ADD VALUE 'DEMO_SEED'")



def downgrade() -> None:
    pass
