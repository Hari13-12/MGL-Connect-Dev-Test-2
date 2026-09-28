"""Initial application registration tables.

Revision ID: 20260925_01
Revises:
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260925_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS app")
    op.create_table(
        "app_user",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("mobile_number", sa.String(32), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("preferred_language", sa.String(16)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        schema="app",
    )
    op.create_table(
        "otp_request",
        sa.Column("otp_request_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("destination_hash", sa.String(64), nullable=False),
        sa.Column("provider_reference", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("resend_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema="app",
    )
    op.create_index(
        "ix_app_otp_request_destination_hash",
        "otp_request",
        ["destination_hash"],
        schema="app",
    )
    op.create_table(
        "user_access",
        sa.Column("user_access_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app.app_user.user_id"),
            nullable=False,
        ),
        sa.Column("service_contract_sfid", sa.String(18), nullable=False),
        sa.Column("account_sfid", sa.String(18), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id",
            "service_contract_sfid",
            "account_sfid",
            name="uq_user_access_scope",
        ),
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("user_access", schema="app")
    op.drop_index(
        "ix_app_otp_request_destination_hash", table_name="otp_request", schema="app"
    )
    op.drop_table("otp_request", schema="app")
    op.drop_table("app_user", schema="app")
