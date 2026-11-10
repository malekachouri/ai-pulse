#!/usr/bin/env python3
"""Regenerates the endpoint reference in docs/API.md from the application's OpenAPI schema.

Run from the repository root with the backend dependencies available:
    cd backend && python ../scripts/build-api-docs.py
Only the block between the BEGIN/END markers is rewritten; CI fails if it is stale.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

BEGIN, END = "<!-- BEGIN GENERATED ENDPOINTS -->", "<!-- END GENERATED ENDPOINTS -->"
ORDER = ["health", "auth", "dashboard", "news", "search", "models", "tools", "research", "github", "bugs",
         "security", "incidents", "radar", "briefings", "notifications", "preferences", "bookmarks",
         "catalog", "admin"]  # fmt: skip


def _calls(dependant) -> set:  # type: ignore[no-untyped-def]
    out = set()
    for d in dependant.dependencies:
        out.add(d.call)
        out |= _calls(d)
    return out


def access_map(app) -> dict[tuple[str, str], str]:  # type: ignore[no-untyped-def]
    """(METHOD, path) -> who may call it, from the route dependency trees."""
    from app.api.deps import get_current_user, get_optional_user

    result: dict[tuple[str, str], str] = {}

    def visit(routes) -> None:  # type: ignore[no-untyped-def]
        for r in routes:
            contexts = getattr(r, "effective_route_contexts", None)
            items = contexts() if callable(contexts) else ([r] if hasattr(r, "dependant") else [])
            for ctx in items:
                calls = _calls(ctx.dependant)
                roles = next((c.roles for c in calls if hasattr(c, "roles")), None)
                if roles:
                    label = " / ".join(sorted(str(x) for x in roles))
                elif get_current_user in calls:
                    label = "signed in"
                elif get_optional_user in calls:
                    label = "public (personalised when signed in)"
                else:
                    label = "public"
                for m in ctx.methods or []:
                    result[(m.upper(), getattr(ctx, "path_format", ctx.path))] = label

    visit(app.routes)
    return result


def main() -> None:
    app = create_app(Settings(log_level="ERROR", log_json=False))
    schema = app.openapi()
    who = access_map(app)
    groups: dict[str, list[tuple[str, str, str, str]]] = {}
    for path, ops in schema["paths"].items():
        for method, op in ops.items():
            tag = (op.get("tags") or ["other"])[0]
            summary = (op.get("summary") or "").replace("|", "\\|")
            groups.setdefault(tag, []).append(
                (path, method.upper(), summary, who.get((method.upper(), path), "?"))
            )
    lines = [
        BEGIN,
        "",
        f"{sum(len(v) for v in groups.values())} operations, generated from the OpenAPI schema.",
        "",
    ]
    for tag in sorted(groups, key=lambda t: (ORDER.index(t) if t in ORDER else 99, t)):
        lines += [f"### {tag}", "", "| Method | Path | Summary | Access |", "|---|---|---|---|"]
        for path, method, summary, acc in sorted(groups[tag]):
            lines.append(f"| `{method}` | `{path}` | {summary} | {acc} |")
        lines.append("")
    lines.append(END)
    doc = ROOT / "docs" / "API.md"
    text = doc.read_text()
    start, end = text.index(BEGIN), text.index(END) + len(END)
    doc.write_text(text[:start] + "\n".join(lines) + text[end:])
    print(f"updated {doc}")


if __name__ == "__main__":
    main()
