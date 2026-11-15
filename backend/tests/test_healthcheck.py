"""Container health check for Beat: reads the heartbeat with the standard library only."""

import importlib.util
import socket
import threading
import time
from pathlib import Path

import pytest

from app.core.metrics import BEAT_HEARTBEAT_KEY

_spec = importlib.util.spec_from_file_location(
    "healthcheck", Path(__file__).parents[1] / "docker" / "healthcheck.py"
)
assert _spec and _spec.loader
hc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hc)


class FakeRedis:
    """Just enough RESP for AUTH, SELECT and GET, recording the commands it receives."""

    def __init__(self, data: dict[str, bytes], password: str | None = None) -> None:
        self.data, self.password, self.commands = data, password, []
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:  # closed at the end of the test
                return
            with conn, conn.makefile("rb") as f:
                authed = self.password is None
                while line := f.readline():
                    args = []
                    for _ in range(int(line[1:])):
                        n = int(f.readline()[1:])
                        args.append(f.read(n + 2)[:-2].decode())
                    self.commands.append(args)
                    cmd = args[0].upper()
                    if cmd == "AUTH":
                        authed = args[-1] == self.password
                        conn.sendall(b"+OK\r\n" if authed else b"-WRONGPASS invalid password\r\n")
                    elif not authed:
                        conn.sendall(b"-NOAUTH Authentication required.\r\n")
                    elif cmd == "SELECT":
                        conn.sendall(b"+OK\r\n")
                    elif cmd == "GET":
                        v = self.data.get(args[1])
                        conn.sendall(b"$-1\r\n" if v is None else b"$%d\r\n%s\r\n" % (len(v), v))

    def close(self) -> None:
        self.server.close()


@pytest.fixture
def redis_server():  # type: ignore[no-untyped-def]
    servers: list[FakeRedis] = []

    def make(data: dict[str, bytes], password: str | None = None) -> FakeRedis:
        servers.append(FakeRedis(data, password))
        return servers[-1]

    yield make
    for s in servers:
        s.close()


def test_beat_healthcheck_reads_the_heartbeat(redis_server, monkeypatch):  # type: ignore[no-untyped-def]
    assert hc.BEAT_HEARTBEAT_KEY == BEAT_HEARTBEAT_KEY  # the check imports nothing from the app
    fresh = redis_server({BEAT_HEARTBEAT_KEY: str(time.time() - 5).encode()}, password="p@ss word")
    monkeypatch.setenv("REDIS_URL", f"redis://:p%40ss%20word@127.0.0.1:{fresh.port}/2")
    assert hc.beat() is True
    assert fresh.commands == [["AUTH", "p@ss word"], ["SELECT", "2"], ["GET", BEAT_HEARTBEAT_KEY]]

    stale = redis_server({BEAT_HEARTBEAT_KEY: str(time.time() - 600).encode()})
    monkeypatch.setenv("REDIS_URL", f"redis://127.0.0.1:{stale.port}/0")
    assert hc.beat() is False
    assert stale.commands == [["GET", BEAT_HEARTBEAT_KEY]]  # no AUTH without a password, no SELECT for db 0

    missing = redis_server({})
    monkeypatch.setenv("REDIS_URL", f"redis://127.0.0.1:{missing.port}")
    assert hc.beat() is False


def test_beat_healthcheck_errors_and_url_sources(redis_server, monkeypatch, tmp_path):  # type: ignore[no-untyped-def]
    locked = redis_server({BEAT_HEARTBEAT_KEY: b"1"}, password="right")
    with pytest.raises(RuntimeError, match="WRONGPASS"):
        hc._redis_get(f"redis://:wrong@127.0.0.1:{locked.port}/0", BEAT_HEARTBEAT_KEY)
    with pytest.raises(ValueError, match="scheme"):
        hc._redis_get("http://127.0.0.1:1/0", BEAT_HEARTBEAT_KEY)

    # Same order as the app's settings: environment, then the Docker secret file, then the default.
    (tmp_path / "redis_url").write_text("redis://from-secret:6379/0\n")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    monkeypatch.setenv("REDIS_URL", "redis://from-env:6379/0")
    assert hc._redis_url() == "redis://from-env:6379/0"
    monkeypatch.delenv("REDIS_URL")
    assert hc._redis_url() == "redis://from-secret:6379/0"
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path / "none"))
    assert hc._redis_url() == "redis://localhost:6379/0"


def test_tls_redis_requires_tls_1_2(monkeypatch):  # type: ignore[no-untyped-def]
    import ssl

    seen = {}

    def wrap(self, sock, server_hostname=None):  # type: ignore[no-untyped-def]
        seen["min"], seen["host"], seen["verify"] = self.minimum_version, server_hostname, self.verify_mode
        raise ConnectionAbortedError("stop before the handshake")

    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: socket.socket())
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap)
    with pytest.raises(ConnectionAbortedError):
        hc._redis_get("rediss://redis.example.test:6380/0", BEAT_HEARTBEAT_KEY)
    assert seen == {"min": ssl.TLSVersion.TLSv1_2, "host": "redis.example.test", "verify": ssl.CERT_REQUIRED}
