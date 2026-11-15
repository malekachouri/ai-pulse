"""Install instructions assembled from a listing's own fields.

Each instruction is {"label", "command", "notes"}: `command` is copy-pasteable, `notes` say what the user
still has to fill in (secrets, URL variables); placeholders look like <NAME>. Nothing is added that the
listing does not state: a package type without a known runner gets a note pointing to the listing.
"""

import re
import shlex
from typing import Any

# How each package registry is run, per the MCP Registry server.json schema (`registryType`).
_RUNNERS: dict[str, tuple[str, ...]] = {"npm": ("npx", "-y"), "pypi": ("uvx",), "nuget": ("dnx",)}
_VAR_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def short_name(name: str) -> str:
    """`io.github.acme/postgres-mcp` -> `postgres-mcp`: the local name given to `claude mcp add`."""
    base = name.rsplit("/", 1)[-1].lower()
    return re.sub(r"[^a-z0-9-]+", "-", base).strip("-")[:60] or "server"


def _q(value: str) -> str:
    return shlex.quote(value) if value else "''"


def _args(items: list[dict[str, Any]] | None) -> list[str]:
    """Positional and named arguments with a value or a placeholder, in listing order."""
    out: list[str] = []
    for a in items or []:
        value = a.get("value") or a.get("default")
        if a.get("type") == "named" and a.get("name"):
            out.append(a["name"])
            if value is not None or a.get("isRequired"):
                out.append(str(value) if value is not None else f"<{a['name'].lstrip('-').upper()}>")
        elif value is not None:
            out.append(str(value))
        elif a.get("isRequired") and a.get("valueHint"):
            out.append(f"<{a['valueHint']}>")
    return out


def _env_notes(envs: list[dict[str, Any]] | None) -> tuple[list[str], list[str]]:
    """(names of the required variables, notes)."""
    required: list[str] = []
    notes: list[str] = []
    for e in envs or []:
        name = e.get("name")
        if not name:
            continue
        if e.get("isRequired"):
            required.append(name)
            kind = "secret" if e.get("isSecret") else "value"
            notes.append(f"Set {name} ({kind}): {(e.get('description') or '').strip()[:200]}".rstrip(": "))
    optional = [e["name"] for e in envs or [] if e.get("name") and not e.get("isRequired")]
    if optional:
        notes.append("Optional settings: " + ", ".join(optional[:10]))
    return required, notes


def _url_notes(url: str) -> list[str]:
    names = _VAR_RE.findall(url)
    return [f"Replace {{{n}}} in the URL" for n in dict.fromkeys(names)]


def mcp_server(name: str, server: dict[str, Any]) -> list[dict[str, Any]]:
    """Instructions for Claude Code (`claude mcp add`) from an MCP Registry server.json."""
    local = short_name(name)
    out: list[dict[str, Any]] = []
    for r in server.get("remotes") or []:
        url = r.get("url")
        if not url or r.get("type") not in ("streamable-http", "sse"):
            continue
        transport = "http" if r["type"] == "streamable-http" else "sse"
        cmd = ["claude", "mcp", "add", "--transport", transport, local, url]
        notes = _url_notes(url)
        for h in r.get("headers") or []:
            if h.get("isRequired") and h.get("name"):
                cmd += ["--header", f"{h['name']}: <{h['name'].upper().replace('-', '_')}>"]
                notes.append(f"Header {h['name']}: {(h.get('description') or '').strip()[:200]}".rstrip(": "))
        out.append(
            {"label": f"Connect to the hosted server ({r['type']})", "command": _join(cmd), "notes": notes}
        )

    for p in server.get("packages") or []:
        kind, ident = p.get("registryType"), p.get("identifier")
        if not kind or not ident:
            continue
        transport = (p.get("transport") or {}).get("type", "stdio")
        required, notes = _env_notes(p.get("environmentVariables"))
        version = p.get("version")
        if kind == "oci":
            env = [x for n in required for x in ("-e", n)]  # docker passes these from the environment
            run = ["docker", "run", "-i", "--rm", *env, *_args(p.get("runtimeArguments")), ident,
                   *_args(p.get("packageArguments"))]  # fmt: skip
        elif kind in _RUNNERS:
            hint = p.get("runtimeHint")
            runner = (hint,) if hint and hint not in _RUNNERS[kind] else _RUNNERS[kind]
            pinned = (
                f"{ident}=={version}"
                if kind == "pypi" and version
                else f"{ident}@{version}"
                if version
                else ident
            )
            run = [*runner, *_args(p.get("runtimeArguments")), pinned, *_args(p.get("packageArguments"))]
        elif kind == "mcpb":
            note = "Open the bundle with an app that supports MCP bundles (e.g. Claude Desktop)."
            out.append({"label": "Download the MCP bundle (.mcpb)", "command": ident, "notes": [note]})
            continue
        else:
            note = f"No standard runner for '{kind}' packages: follow the listing."
            out.append({"label": f"{kind} package {ident}", "command": None, "notes": [note]})
            continue
        if transport == "stdio":
            env = [x for n in required for x in ("-e", f"{n}=<{n}>")]
            cmd = ["claude", "mcp", "add", local, *env, "--", *run]
            out.append({"label": f"Run locally from {kind}", "command": _join(cmd), "notes": notes})
        else:
            url = (p.get("transport") or {}).get("url")
            steps = [_join(run)]
            if url:
                steps.append(_join(["claude", "mcp", "add", "--transport", "http", local, url]))
            label = f"Run locally from {kind}, then connect ({transport})"
            notes += _url_notes(url) if url else []
            out.append({"label": label, "command": "\n".join(steps), "notes": notes})
    return out


def plugin(name: str, marketplace: str, marketplace_repo: str) -> list[dict[str, Any]]:
    """Instructions for a Claude Code plugin listed by a marketplace."""
    add = f"/plugin marketplace add {marketplace_repo}"
    return [
        {"label": "Add the marketplace (once)", "command": add, "notes": []},
        {"label": "Install the plugin", "command": f"/plugin install {name}@{marketplace}", "notes": []},
    ]


def skill(plugin_name: str, marketplace: str, marketplace_repo: str) -> list[dict[str, Any]]:
    """An Agent Skill installs with the plugin that bundles it."""
    steps = plugin(plugin_name, marketplace, marketplace_repo)
    steps[1]["notes"] = [f"This skill is part of the plugin '{plugin_name}'."]
    return steps


def _join(parts: list[str]) -> str:
    return " ".join(_q(p) for p in parts)
