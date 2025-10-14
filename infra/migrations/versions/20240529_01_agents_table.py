"""Create agents table with pgvector support."""

from __future__ import annotations

from alembic import op


revision = "20240529_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute(
        """
        CREATE TABLE agents (
            id UUID NOT NULL,
            seed TEXT NOT NULL,
            username_hint TEXT NOT NULL,
            payload JSONB NOT NULL,
            embedding VECTOR,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        ) PARTITION BY RANGE (created_at);
        """
    )
    op.execute(
        """
        CREATE TABLE agents_default
        PARTITION OF agents
        DEFAULT;
        """
    )
    op.execute("CREATE UNIQUE INDEX ux_agents_default_id ON agents_default (id);")
    op.execute(
        "CREATE UNIQUE INDEX ux_agents_default_username ON agents_default (username_hint);",
    )
    op.execute(
        "CREATE INDEX ix_agents_default_created_at ON agents_default (created_at);",
    )
    op.execute(
        """
        CREATE INDEX ix_agents_default_embedding
        ON agents_default
        USING ivfflat (embedding vector_l2_ops)
        WITH (lists = 100);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agents CASCADE;")
