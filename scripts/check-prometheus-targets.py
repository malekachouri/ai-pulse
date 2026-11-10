#!/usr/bin/env python3
"""Exit 0 when every given Prometheus scrape job has at least one target and all of them are up.

scripts/check-prometheus-targets.py [--url http://localhost:9090] [--wait 150] ai-pulse-api postgres redis
"""

import argparse
import json
import sys
import time
import urllib.request


def health(url: str) -> dict[str, list[str]]:
    with urllib.request.urlopen(f"{url}/api/v1/targets?state=active", timeout=5) as r:  # noqa: S310 - operator-given URL
        targets = json.load(r)["data"]["activeTargets"]
    jobs: dict[str, list[str]] = {}
    for t in targets:
        jobs.setdefault(t["labels"].get("job", "?"), []).append(t["health"])
    return jobs


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:9090")
    p.add_argument("--wait", type=int, default=150, help="seconds to wait for the targets to come up")
    p.add_argument("jobs", nargs="+")
    a = p.parse_args()
    deadline = time.monotonic() + a.wait
    last: dict[str, list[str]] = {}
    while True:
        try:
            last = health(a.url)
            if all(last.get(j) and all(h == "up" for h in last[j]) for j in a.jobs):
                print("all targets up:", {j: last[j] for j in a.jobs})
                return 0
        except OSError as exc:
            print("prometheus not reachable yet:", exc)
        if time.monotonic() > deadline:
            print("targets not up:", {j: last.get(j, []) for j in a.jobs}, file=sys.stderr)
            return 1
        time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
