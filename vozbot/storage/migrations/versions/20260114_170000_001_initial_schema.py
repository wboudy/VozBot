"""Initial schema - calls and callback_tasks tables.

Revision ID: 001
Revises:
Create Date: 2026-01-14 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create calls and callback_tasks tables."""
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"

    # For PostgreSQL, create enum types first
    if is_postgresql:
        op.execute("CREATE TYPE language_enum AS ENUM ('en', 'es')")
        op.execute("CREATE TYPE customer_type_enum AS ENUM ('new', 'existing', 'unknown')")
        op.execute(
            "CREATE TYPE call_status_enum AS ENUM ("
            "'init', 'greet', 'language_select', 'classify_customer_type', "
            "'intent_discovery', 'info_collection', 'confirmation', "
            "'create_callback_task', 'transfer_or_wrapup', 'end', "
            "'completed', 'transferred', 'failed')"
        )
        op.execute(
            "CREATE TYPE task_status_enum AS ENUM ("
            "'pending', 'in_progress', 'completed', 'cancelled')"
        )
        op.execute("CREATE TYPE task_priority_enum AS ENUM ('1', '2', '3', '4')")

    # Column definitions vary by dialect
    if is_postgresql:
        from sqlalchemy.dialects import postgresql

        id_type = postgresql.UUID(as_uuid=False)
        costs_type = postgresql.JSON(astext_type=sa.Text())
        language_type = sa.Enum("en", "es", name="language_enum", create_constraint=False)
        customer_type_type = sa.Enum(
            "new", "existing", "unknown", name="customer_type_enum", create_constraint=False
        )
        call_status_type = sa.Enum(
            "init",
            "greet",
            "language_select",
            "classify_customer_type",
            "intent_discovery",
            "info_collection",
            "confirmation",
            "create_callback_task",
            "transfer_or_wrapup",
            "end",
            "completed",
            "transferred",
            "failed",
            name="call_status_enum",
            create_constraint=False,
        )
        task_status_type = sa.Enum(
            "pending",
            "in_progress",
            "completed",
            "cancelled",
            name="task_status_enum",
            create_constraint=False,
        )
        task_priority_type = sa.Enum(
            "1", "2", "3", "4", name="task_priority_enum", create_constraint=False
        )
        now_default = sa.text("now()")
    else:
        # SQLite: Use String for UUID, JSON for costs, String for enums
        id_type = sa.String(36)
        costs_type = sa.JSON()
        language_type = sa.String(10)
        customer_type_type = sa.String(20)
        call_status_type = sa.String(30)
        task_status_type = sa.String(20)
        task_priority_type = sa.String(10)
        now_default = sa.func.current_timestamp()

    # Create calls table
    op.create_table(
        "calls",
        sa.Column("id", id_type, nullable=False),
        sa.Column("from_number", sa.String(length=20), nullable=False),
        sa.Column("language", language_type, nullable=True),
        sa.Column("customer_type", customer_type_type, nullable=True),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column("status", call_status_type, nullable=False, server_default="init"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("costs", costs_type, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes on calls table
    op.create_index("ix_calls_from_number", "calls", ["from_number"], unique=False)
    op.create_index("ix_calls_status", "calls", ["status"], unique=False)
    op.create_index("ix_calls_created_at", "calls", ["created_at"], unique=False)
    op.create_index(
        "ix_calls_from_number_created_at", "calls", ["from_number", "created_at"], unique=False
    )
    op.create_index("ix_calls_status_created_at", "calls", ["status", "created_at"], unique=False)

    # Create callback_tasks table
    op.create_table(
        "callback_tasks",
        sa.Column("id", id_type, nullable=False),
        sa.Column("call_id", id_type, nullable=False),
        sa.Column("priority", task_priority_type, nullable=False, server_default="2"),
        sa.Column("assignee", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("callback_number", sa.String(length=20), nullable=False),
        sa.Column("best_time_window", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", task_status_type, nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["call_id"],
            ["calls.id"],
            name="fk_callback_tasks_call_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("call_id", name="uq_callback_tasks_call_id"),
    )

    # Create indexes on callback_tasks table
    op.create_index("ix_callback_tasks_status", "callback_tasks", ["status"], unique=False)
    op.create_index(
        "ix_callback_tasks_status_priority",
        "callback_tasks",
        ["status", "priority"],
        unique=False,
    )
    op.create_index(
        "ix_callback_tasks_assignee_status",
        "callback_tasks",
        ["assignee", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop calls and callback_tasks tables."""
    # Drop callback_tasks table and indexes
    op.drop_index("ix_callback_tasks_assignee_status", table_name="callback_tasks")
    op.drop_index("ix_callback_tasks_status_priority", table_name="callback_tasks")
    op.drop_index("ix_callback_tasks_status", table_name="callback_tasks")
    op.drop_table("callback_tasks")

    # Drop calls table and indexes
    op.drop_index("ix_calls_status_created_at", table_name="calls")
    op.drop_index("ix_calls_from_number_created_at", table_name="calls")
    op.drop_index("ix_calls_created_at", table_name="calls")
    op.drop_index("ix_calls_status", table_name="calls")
    op.drop_index("ix_calls_from_number", table_name="calls")
    op.drop_table("calls")

    # Drop enum types (only for PostgreSQL)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS task_priority_enum")
        op.execute("DROP TYPE IF EXISTS task_status_enum")
        op.execute("DROP TYPE IF EXISTS call_status_enum")
        op.execute("DROP TYPE IF EXISTS customer_type_enum")
        op.execute("DROP TYPE IF EXISTS language_enum")
