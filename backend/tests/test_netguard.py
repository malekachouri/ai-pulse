"""Collectors refuse internal destinations (SSRF defence): spelling, resolution, redirects, admin API."""

import httpx
import pytest

from app.ingestion import netguard
from app.ingestion.http import FetchError, HttpClient
from app.ingestion.netguard import internal_host
from tests.conftest import PASSWORD, make_admin, register_and_login
from tests.ingestion_helpers import MockHttp


@pytest.mark.parametrize(
    "host",
    ["169.254.169.254", "127.0.0.1", "10.0.0.1", "192.168.1.10", "[::1]", "fd00::1", "localhost",
     "api.localhost", "metadata.google.internal", "postgres", "redis", "printer.local", "0.0.0.0"],  # noqa: S104 - test data
)  # fmt: skip
def test_internal_hosts_are_recognised(host):
    assert internal_host(host)


@pytest.mark.parametrize("host", ["services.nvd.nist.gov", "8.8.8.8", "api.github.com", "2606:4700::1111"])
def test_public_hosts_pass(host):
    assert internal_host(host) is None


async def test_blocked_before_any_request_is_sent():
    mock = MockHttp({"http://169.254.169.254/": httpx.Response(200, text="iam-credentials")})
    with pytest.raises(FetchError, match="blocked destination"):
        await mock.client(block_private=True).get("http://169.254.169.254/latest/meta-data/")
    assert mock.requests == []  # the metadata service was never contacted


async def test_redirect_to_an_internal_address_is_blocked():
    seen = []

    def handler(request):
        seen.append(request.url.host)
        if request.url.host == "feeds.example.com":
            return httpx.Response(302, headers={"Location": "http://10.0.0.5/admin"})
        return httpx.Response(200, text="internal")

    # Same redirect policy as the production client.
    inner = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    with pytest.raises(FetchError, match="10.0.0.5 is not a public address"):
        await HttpClient(inner, block_private=True).get("https://feeds.example.com/rss")
    assert seen == ["feeds.example.com"]  # the internal hop was never requested


async def test_names_resolving_to_private_addresses_are_blocked(monkeypatch):
    monkeypatch.setattr(netguard, "_proxied", lambda url: False)
    monkeypatch.setattr(netguard.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("10.1.2.3", 443))])
    assert "resolves to 10.1.2.3" in (
        await netguard.blocked_reason("https://evil.example.com/", "evil.example.com", 443)
    )
    monkeypatch.setattr(
        netguard.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.216.34", 443))]
    )
    assert await netguard.blocked_reason("https://ok.example.com/", "ok.example.com", 443) is None


async def test_guard_off_by_default_for_injected_clients():
    mock = MockHttp({"http://10.0.0.5/": httpx.Response(200, json={})})
    assert (await mock.client().get("http://10.0.0.5/x")).status_code == 200


async def test_admin_api_refuses_internal_source_urls(client, session_factory):
    await register_and_login(client, "guard@example.com")
    await make_admin(session_factory, "guard@example.com")
    r = await client.post("/api/v1/auth/login", json={"email": "guard@example.com", "password": PASSWORD})
    admin_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    base = {"name": "Feed", "connector": "rss", "source_type": "rss", "default_item_type": "news"}
    for url in ["http://169.254.169.254/latest/meta-data", "http://postgres:5432/", "http://localhost/x"]:
        r = await client.post(
            "/api/v1/admin/sources", headers=admin_headers, json={**base, "slug": "s1", "url": url}
        )
        assert r.status_code == 400 and "Source URL refused" in r.json()["error"]["message"], url
    r = await client.post("/api/v1/admin/sources", headers=admin_headers,
                          json={**base, "slug": "s2", "url": "https://feeds.example.com/rss"})  # fmt: skip
    assert r.status_code == 201
    r = await client.patch(f"/api/v1/admin/sources/{r.json()['id']}", headers=admin_headers,
                           json={"url": "http://10.0.0.1/feed"})  # fmt: skip
    assert r.status_code == 400
