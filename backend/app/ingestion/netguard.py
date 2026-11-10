"""Destination guard for collectors (SSRF defence in depth).

Sources are configured by admins, and whatever a collector fetches is published as items. A source URL
pointing inside the deployment - cloud metadata (169.254.169.254), localhost, private networks, Docker
service names such as `postgres` - would turn the worker into a proxy to internal services. Every
request (redirects included) is therefore checked:

* the host must not be an internal name (`localhost`, `*.internal`, `*.local`, single-label names) or a
  literal non-public IP;
* without an outbound HTTP proxy, every address it resolves to must be public. Behind a proxy the
  proxy resolves names (and enforces egress policy), so only the first check applies.

`INGESTION_ALLOW_PRIVATE_HOSTS=true` disables the guard for intranet-only deployments.
"""

import asyncio
import ipaddress
import socket
import urllib.request

INTERNAL_SUFFIXES = (".localhost", ".internal", ".local", ".lan", ".home.arpa", ".svc", ".cluster.local")


def _ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None


def internal_host(host: str) -> str | None:
    """Why `host` is internal from its spelling alone, or None."""
    h = host.strip().rstrip(".").lower()
    if not h:
        return "empty host"
    ip = _ip(h)
    if ip is not None:
        return None if ip.is_global else f"{ip} is not a public address"
    if h == "localhost" or h.endswith(INTERNAL_SUFFIXES):
        return f"{h} is an internal name"
    if "." not in h:
        return f"{h} is a single-label (internal) name"
    return None


def _proxied(url: str) -> bool:
    proxies = urllib.request.getproxies()
    scheme = url.split(":", 1)[0].lower()
    if not proxies.get(scheme):
        return False
    host = url.split("://", 1)[-1].split("/", 1)[0].rsplit("@", 1)[-1]
    return not urllib.request.proxy_bypass(host.split(":", 1)[0])


async def blocked_reason(url: str, host: str, port: int | None) -> str | None:
    """None when the destination may be fetched; otherwise why not."""
    if reason := internal_host(host):
        return reason
    if _ip(host) is not None or _proxied(url):
        return None
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, port or 443, type=socket.SOCK_STREAM)
    except OSError:
        return None  # resolution failure: the request itself will fail with a clear transport error
    for info in infos:
        ip = _ip(str(info[4][0]))
        if ip is not None and not ip.is_global:
            return f"{host} resolves to {ip}, which is not a public address"
    return None
