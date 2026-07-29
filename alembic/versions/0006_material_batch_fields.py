"""Store material batch ownership and review outputs."""

import sqlalchemy as sa
from alembic import op


revision = "0006_material_batch_fields"
down_revision = "0005_task_payload"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    batch_columns = _columns("material_batches")
    if "template_id" not in batch_columns:
        op.add_column(
            "material_batches",
            sa.Column("template_id", sa.String(length=36), nullable=True),
        )
    draft_columns = _columns("material_drafts")
    for name, column in (
        ("fit_data", sa.Column("fit_data", sa.JSON(), nullable=False, server_default="{}")),
        ("review_data", sa.Column("review_data", sa.JSON(), nullable=False, server_default="{}")),
        ("output_file_ids", sa.Column("output_file_ids", sa.JSON(), nullable=False, server_default="[]")),
    ):
        if name not in draft_columns:
            op.add_column("material_drafts", column)


def downgrade() -> None:
    draft_columns = _columns("material_drafts")
    for name in ("output_file_ids", "review_data", "fit_data"):
        if name in draft_columns:
            op.drop_column("material_drafts", name)
    if "template_id" in _columns("material_batches"):
        op.drop_column("material_batches", "template_id")
