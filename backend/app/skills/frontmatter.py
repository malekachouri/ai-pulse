"""The YAML front matter of a SKILL.md: only the flat `key: value` fields the radar reads (name, description,
license), including quoted values and block scalars (`|`, `|-`, `>`, `>-`). No YAML library needed."""

import re

_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")


def parse(text: str) -> dict[str, str]:
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}
    out: dict[str, str] = {}
    i = 1
    while i < end:
        m = _KEY_RE.match(lines[i])
        i += 1
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value[:1] in ("|", ">"):
            block: list[str] = []
            while i < end and (not lines[i].strip() or lines[i][:1] in (" ", "\t")):
                block.append(lines[i].strip())
                i += 1
            joiner = "\n" if value.startswith("|") else " "
            out[key] = joiner.join(block).strip()
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            inner = value[1:-1]
            out[key] = inner.replace('\\"', '"') if value[0] == '"' else inner.replace("''", "'")
        else:
            out[key] = value
    return out
