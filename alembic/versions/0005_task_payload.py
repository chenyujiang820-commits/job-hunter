"""Store task input needed by background workers."""

import sqlalchemy as sa
from alembic import op


revision = "0005_task_payload"
down_revision = "0004_evaluation_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("tasks")}
    if "payload" not in columns:
        op.add_column("tasks", sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("tasks")}
    if "payload" in columns:
        op.drop_column("tasks", "payload")
