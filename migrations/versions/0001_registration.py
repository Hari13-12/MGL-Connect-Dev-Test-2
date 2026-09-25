"""initial registration tables"""

import sqlalchemy as sa
from alembic import op

revision = "0001_registration"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "app_user",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column("mobile_number", sa.String(32), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", name="userstatus"), nullable=False),
        sa.Column("preferred_language", sa.String(10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_app_user_mobile_number", "app_user", ["mobile_number"], unique=True)
    op.create_table(
        "otp_request",
        sa.Column("otp_request_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36)),
        sa.Column("purpose", sa.Enum("REGISTER", name="otppurpose"), nullable=False),
        sa.Column("destination_hash", sa.String(64), nullable=False),
        sa.Column("provider_reference", sa.String(128), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "VERIFIED", "EXPIRED", "FAILED", name="otpstatus"),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer, nullable=False),
        sa.Column("resend_count", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("account_sfid", sa.String(64), nullable=False),
        sa.Column("service_contract_sfid", sa.String(64), nullable=False),
        sa.Column("pending_password_hash", sa.String(512), nullable=False),
        sa.Column("pending_mobile_number", sa.String(32), nullable=False),
    )
    op.create_index("ix_otp_request_destination_hash", "otp_request", ["destination_hash"])
    op.create_index("ix_otp_request_expires_at", "otp_request", ["expires_at"])
    op.create_table(
        "user_access",
        sa.Column("user_access_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.user_id"), nullable=False),
        sa.Column("service_contract_sfid", sa.String(64), nullable=False),
        sa.Column("account_sfid", sa.String(64), nullable=False),
        sa.Column("is_primary", sa.Boolean, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "service_contract_sfid", "account_sfid"),
    )
    op.create_index("ix_user_access_user_id", "user_access", ["user_id"])
    op.create_index(
        "ix_user_access_contract_account", "user_access", ["service_contract_sfid", "account_sfid"]
    )


def downgrade():
    op.drop_table("user_access")
    op.drop_table("otp_request")
    op.drop_table("app_user")
