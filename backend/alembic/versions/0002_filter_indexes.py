"""filter indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-09 11:15:40.173821
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_ai_model_releases_released_at", "ai_model_releases", ["released_at"], unique=False)
    op.create_index("ix_collection_jobs_status", "collection_jobs", ["status"], unique=False)
    op.create_index("ix_github_issues_state_opened", "github_issues", ["state", "opened_at"], unique=False)
    op.create_index("ix_github_repositories_stars", "github_repositories", ["stars"], unique=False)
    op.create_index("ix_incidents_started_at", "incidents", ["started_at"], unique=False)
    op.create_index("ix_incidents_status_verified", "incidents", ["status", "last_verified_at"], unique=False)
    op.create_index("ix_research_papers_published_at", "research_papers", ["published_at"], unique=False)
    op.create_index(
        "ix_security_vulnerabilities_cvss", "security_vulnerabilities", ["cvss_score"], unique=False
    )
    op.create_index(
        "ix_security_vulnerabilities_modified", "security_vulnerabilities", ["last_modified_at"], unique=False
    )
    op.create_index(
        "ix_security_vulnerabilities_severity", "security_vulnerabilities", ["severity"], unique=False
    )
    op.create_index(
        "ix_software_bugs_severity_created", "software_bugs", ["severity", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_software_bugs_severity_created", table_name="software_bugs")
    op.drop_index("ix_security_vulnerabilities_severity", table_name="security_vulnerabilities")
    op.drop_index("ix_security_vulnerabilities_modified", table_name="security_vulnerabilities")
    op.drop_index("ix_security_vulnerabilities_cvss", table_name="security_vulnerabilities")
    op.drop_index("ix_research_papers_published_at", table_name="research_papers")
    op.drop_index("ix_incidents_status_verified", table_name="incidents")
    op.drop_index("ix_incidents_started_at", table_name="incidents")
    op.drop_index("ix_github_repositories_stars", table_name="github_repositories")
    op.drop_index("ix_github_issues_state_opened", table_name="github_issues")
    op.drop_index("ix_collection_jobs_status", table_name="collection_jobs")
    op.drop_index("ix_ai_model_releases_released_at", table_name="ai_model_releases")
