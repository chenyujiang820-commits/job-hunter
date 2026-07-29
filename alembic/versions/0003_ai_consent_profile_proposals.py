"""Add AI consent and profile proposal storage."""

import sqlalchemy as sa
from alembic import op


revision = "0003_ai_consent_profile_proposals"
down_revision = "0002_sessions"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_column("users", "ai_consent_at"):
        op.add_column("users", sa.Column("ai_consent_at", sa.DateTime(), nullable=True))
    if not _has_column("users", "ai_processing_enabled"):
        op.add_column(
            "users",
            sa.Column("ai_processing_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if not _has_column("candidate_profiles", "source_refs"):
        op.add_column(
            "candidate_profiles",
            sa.Column("source_refs", sa.JSON(), nullable=False, server_default="[]"),
        )
    if not _has_column("candidate_profiles", "confirmed_at"):
        op.add_column("candidate_profiles", sa.Column("confirmed_at", sa.DateTime(), nullable=True))

    if not _has_table("profile_proposals"):
        op.create_table(
            "profile_proposals",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("proposed_data", sa.JSON(), nullable=False),
            sa.Column("source_refs", sa.JSON(), nullable=False),
            sa.Column("accepted_fields", sa.JSON(), nullable=False),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_profile_proposals_user_id", "profile_proposals", ["user_id"])


def downgrade() -> None:
    if _has_table("profile_proposals"):
        op.drop_index("ix_profile_proposals_user_id", table_name="profile_proposals")
        op.drop_table("profile_proposals")
    for column_name in ("confirmed_at", "source_refs"):
        if _has_column("candidate_profiles", column_name):
            op.drop_column("candidate_profiles", column_name)
    for column_name in ("ai_processing_enabled", "ai_consent_at"):
        if _has_column("users", column_name):
            op.drop_column("users", column_name)
