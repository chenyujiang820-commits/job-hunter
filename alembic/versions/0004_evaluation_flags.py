"""Store visible risk flags with private job evaluations."""

import sqlalchemy as sa
from alembic import op


revision = "0004_evaluation_flags"
down_revision = "0003_ai_consent_profile_proposals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("user_job_evaluations")}
    if "flags" not in columns:
        op.add_column(
            "user_job_evaluations",
            sa.Column("flags", sa.JSON(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("user_job_evaluations")}
    if "flags" in columns:
        op.drop_column("user_job_evaluations", "flags")
