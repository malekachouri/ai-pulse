import enum

import sqlalchemy as sa


class StrEnum(enum.StrEnum):
    pass


def enum_column(enum_cls: type[enum.Enum], name: str) -> sa.Enum:
    """Store enums as VARCHAR + CHECK constraint (portable, migration-friendly)."""
    return sa.Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class RoleName(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    USER = "user"


class SourceType(StrEnum):
    RSS = "rss"
    API = "api"
    GITHUB = "github"
    STATUS_PAGE = "status_page"
    SCRAPE = "scrape"


class ItemType(StrEnum):
    NEWS = "news"
    MODEL_RELEASE = "model_release"
    TOOL = "tool"
    RESEARCH = "research"
    GITHUB_REPO = "github_repo"
    GITHUB_ISSUE = "github_issue"
    BUG = "bug"
    VULNERABILITY = "vulnerability"
    INCIDENT = "incident"
    DEVOPS = "devops"


class VerificationStatus(StrEnum):
    """How trustworthy the record is - shown next to every item in the UI."""

    OFFICIAL = "official"  # collected directly from the vendor's / authority's own channel
    VERIFIED = "verified"  # cross-checked against an official source
    UNVERIFIED = "unverified"  # third-party report, not yet confirmed
    DISPUTED = "disputed"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"


class IncidentStatus(StrEnum):
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class IssueState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class BugKind(StrEnum):
    BUG = "bug"
    REGRESSION = "regression"
    PERFORMANCE = "performance"
    COMPATIBILITY = "compatibility"
    SECURITY = "security"
    OTHER = "other"


class BugResolution(StrEnum):
    """Why a bug is closed, as reported by the source (GitHub `state_reason`)."""

    FIXED = "fixed"  # closed AND a merged pull request / closing commit is linked
    COMPLETED = "completed"  # closed as completed by maintainers, no linked fix found
    NOT_PLANNED = "not_planned"
    DUPLICATE = "duplicate"
    UNKNOWN = "unknown"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


class NotificationKind(StrEnum):
    CRITICAL_ALERT = "critical_alert"
    MODEL_RELEASE = "model_release"
    VULNERABILITY = "vulnerability"
    BUG = "bug"
    INCIDENT = "incident"
    BRIEFING = "briefing"
    SYSTEM = "system"


class AnalysisKind(StrEnum):
    SUMMARY = "summary"
    CLASSIFICATION = "classification"
    IMPACT = "impact"
    IMPORTANCE = "importance"
    ENTITIES = "entities"


class BriefingFrequency(StrEnum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKLY = "weekly"
    OFF = "off"
