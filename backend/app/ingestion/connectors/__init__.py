"""Connector registry: `Source.connector` → implementation."""

from app.ingestion.base import Connector
from app.ingestion.connectors.arxiv import ArxivConnector
from app.ingestion.connectors.aws_status import AwsStatusConnector
from app.ingestion.connectors.azure_status import AzureStatusConnector
from app.ingestion.connectors.cisa_kev import CisaKevConnector
from app.ingestion.connectors.gcp_status import GcpStatusConnector
from app.ingestion.connectors.github import (
    GitHubIssuesConnector,
    GitHubReleasesConnector,
    GitHubTrendingConnector,
)
from app.ingestion.connectors.huggingface import HFDailyPapersConnector, HFModelsConnector
from app.ingestion.connectors.kubernetes_cve import KubernetesCveConnector
from app.ingestion.connectors.nvd import NvdConnector
from app.ingestion.connectors.rss import RssConnector
from app.ingestion.connectors.statuspage import StatuspageConnector

REGISTRY: dict[str, type[Connector]] = {
    c.key: c
    for c in (
        RssConnector,
        ArxivConnector,
        HFDailyPapersConnector,
        HFModelsConnector,
        GitHubReleasesConnector,
        GitHubTrendingConnector,
        GitHubIssuesConnector,
        NvdConnector,
        CisaKevConnector,
        KubernetesCveConnector,
        StatuspageConnector,
        GcpStatusConnector,
        AwsStatusConnector,
        AzureStatusConnector,
    )
}


def get_connector_class(key: str) -> type[Connector]:
    try:
        return REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"Unknown connector '{key}'. Available: {', '.join(sorted(REGISTRY))}") from exc
