#!/usr/bin/env python3
"""Generates the provisioned Grafana dashboards (infra/grafana/dashboards/*.json).

Dashboards are code: edit this file and re-run `python3 scripts/build-dashboards.py`, never the JSON.
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "infra" / "grafana" / "dashboards"
DS = {"type": "prometheus", "uid": "prometheus"}


class Board:
    def __init__(self) -> None:
        self.panels: list[dict] = []
        self.y = 0
        self.x = 0
        self.row_h = 0
        self.next_id = 1

    def _place(self, w: int, h: int) -> dict:
        if self.x + w > 24:
            self.x, self.y = 0, self.y + self.row_h
            self.row_h = 0
        pos = {"x": self.x, "y": self.y, "w": w, "h": h}
        self.x += w
        self.row_h = max(self.row_h, h)
        return pos

    def row(self, title: str) -> None:
        if self.x:
            self.x, self.y, self.row_h = 0, self.y + self.row_h, 0
        self.panels.append(
            {"type": "row", "title": title, "id": self._id(), "collapsed": False,
             "gridPos": {"x": 0, "y": self.y, "w": 24, "h": 1}, "panels": []}
        )
        self.y += 1

    def _id(self) -> int:
        self.next_id += 1
        return self.next_id

    def panel(self, kind: str, title: str, targets: list[tuple[str, str]], *, w: int = 12, h: int = 8,
              unit: str = "short", desc: str = "", thresholds: list[tuple[float, str]] | None = None,
              stack: bool = False, decimals: int | None = None, overrides: list | None = None,
              options: dict | None = None) -> None:
        steps = [{"color": "green", "value": None}] + [{"color": c, "value": v} for v, c in (thresholds or [])]
        defaults: dict = {"unit": unit, "thresholds": {"mode": "absolute", "steps": steps}}
        if decimals is not None:
            defaults["decimals"] = decimals
        if kind == "timeseries":
            defaults["custom"] = {"lineWidth": 2, "fillOpacity": 10, "showPoints": "never",
                                  "stacking": {"mode": "normal" if stack else "none"}}
            defaults["color"] = {"mode": "palette-classic"}
        else:
            defaults["color"] = {"mode": "thresholds"}
        p = {
            "id": self._id(), "type": kind, "title": title, "description": desc, "datasource": DS,
            "gridPos": self._place(w, h),
            "targets": [{"refId": chr(65 + i), "expr": e, "legendFormat": leg, "datasource": DS}
                        for i, (e, leg) in enumerate(targets)],
            "fieldConfig": {"defaults": defaults, "overrides": overrides or []},
            "options": options or {},
        }
        if kind == "timeseries":
            p["options"] = {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "max"]},
                            "tooltip": {"mode": "multi", "sort": "desc"}, **(options or {})}
        if kind == "stat":
            p["options"] = {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                            "graphMode": "area", **(options or {})}
        self.panels.append(p)

    def dump(self, uid: str, title: str, desc: str, tags: list[str]) -> None:
        board = {
            "uid": uid, "title": title, "description": desc, "tags": tags, "schemaVersion": 39, "version": 1,
            "editable": False, "graphTooltip": 1, "refresh": "1m", "timezone": "browser",
            "time": {"from": "now-6h", "to": "now"}, "panels": self.panels,
            "templating": {"list": []}, "annotations": {"list": []},
            "links": [{"title": "AI Pulse dashboards", "type": "dashboards", "tags": ["ai-pulse"], "asDropdown": True}],
        }
        (OUT / f"{uid}.json").write_text(json.dumps(board, indent=2) + "\n")


def service() -> None:
    b = Board()
    b.row("Availability")
    b.panel("stat", "API up", [('up{job="ai-pulse-api"}', "")], w=4, h=4, thresholds=[(0, "red"), (1, "green")],
            options={"colorMode": "background"},
            overrides=[], desc="Prometheus can scrape the API")
    b.panel("stat", "PostgreSQL reachable", [('aipulse_dependency_up{name="postgres"}', "")], w=4, h=4,
            thresholds=[(0, "red"), (1, "green")])
    b.panel("stat", "Redis reachable", [('aipulse_dependency_up{name="redis"}', "")], w=4, h=4,
            thresholds=[(0, "red"), (1, "green")])
    b.panel("stat", "Requests / s", [("sum(rate(aipulse_http_requests_total[5m]))", "")], w=4, h=4, unit="reqps",
            decimals=2)
    b.panel("stat", "5xx ratio (5m)",
            [('sum(rate(aipulse_http_requests_total{status=~"5.."}[5m])) / clamp_min(sum(rate(aipulse_http_requests_total[5m])), 0.001)', "")],
            w=4, h=4, unit="percentunit", thresholds=[(0.01, "orange"), (0.05, "red")])
    b.panel("stat", "p95 latency (5m)",
            [("histogram_quantile(0.95, sum by (le) (rate(aipulse_http_request_duration_seconds_bucket[5m])))", "")],
            w=4, h=4, unit="s", thresholds=[(0.5, "orange"), (1, "red")])
    b.row("API traffic")
    b.panel("timeseries", "Latency p50 / p95 / p99",
            [(f"histogram_quantile({q}, sum by (le) (rate(aipulse_http_request_duration_seconds_bucket[5m])))", f"p{int(q * 100)}")
             for q in (0.5, 0.95, 0.99)], unit="s")
    b.panel("timeseries", "Error rate by status class",
            [('sum by (status) (rate(aipulse_http_requests_total{status=~"[45].."}[5m]))', "{{status}}")], unit="reqps")
    b.panel("timeseries", "Slowest routes (p95)",
            [("topk(8, histogram_quantile(0.95, sum by (le, route) (rate(aipulse_http_request_duration_seconds_bucket[5m]))))", "{{route}}")],
            unit="s")
    b.panel("timeseries", "Requests by route",
            [("topk(10, sum by (route) (rate(aipulse_http_requests_total[5m])))", "{{route}}")], unit="reqps", stack=True)
    b.panel("timeseries", "Rate-limited requests",
            [("sum by (scope) (rate(aipulse_rate_limited_total[5m]))", "{{scope}}")], unit="reqps", w=24, h=6)
    b.row("Database & Redis")
    b.panel("timeseries", "PostgreSQL connections by state",
            [("aipulse_db_connections", "{{state}}"), ("aipulse_db_max_connections", "max_connections")], stack=False)
    b.panel("timeseries", "API connection pool",
            [("aipulse_db_pool_connections", "{{state}}")])
    b.panel("timeseries", "Transactions / s", [("sum(rate(pg_stat_database_xact_commit[5m]))", "commits"),
                                               ("sum(rate(pg_stat_database_xact_rollback[5m]))", "rollbacks")], unit="ops", w=8)
    b.panel("timeseries", "Database size", [('pg_database_size_bytes{datname!~"template.*|postgres"}', "{{datname}}")],
            unit="bytes", w=8)
    b.panel("timeseries", "Redis memory", [("redis_memory_used_bytes", "used"), ("redis_memory_max_bytes", "maxmemory")],
            unit="bytes", w=8)
    b.dump("ai-pulse-service", "AI Pulse — Service health",
           "API availability, latency, errors, rate limiting, PostgreSQL and Redis.", ["ai-pulse"])


def pipeline() -> None:
    b = Board()
    b.row("Queues & scheduler")
    b.panel("stat", "Ingestion queue", [('aipulse_celery_queue_length{queue="ingestion"}', "")], w=6, h=4,
            thresholds=[(50, "orange"), (200, "red")])
    b.panel("stat", "Beat heartbeat age", [("time() - aipulse_beat_heartbeat_timestamp_seconds", "")], w=6, h=4,
            unit="s", thresholds=[(120, "orange"), (300, "red")])
    b.panel("stat", "Last dispatch age", [("time() - aipulse_scheduler_last_dispatch_timestamp_seconds", "")], w=6, h=4,
            unit="s", thresholds=[(300, "orange"), (600, "red")])
    b.panel("stat", "Sources down", [("count(aipulse_source_up == 0) or vector(0)", "")], w=6, h=4,
            thresholds=[(1, "orange"), (3, "red")])
    b.panel("timeseries", "Queue length", [("aipulse_celery_queue_length", "{{queue}}")], w=12)
    b.panel("timeseries", "Background job duration p95 by task",
            [("histogram_quantile(0.95, sum by (le, task) (rate(aipulse_celery_task_duration_seconds_bucket[30m])))", "{{task}}")],
            unit="s", w=12)
    b.panel("timeseries", "Task runs / min by task",
            [("sum by (task) (rate(aipulse_celery_task_duration_seconds_count[10m])) * 60", "{{task}}")], unit="short", w=12)
    b.panel("timeseries", "Task failures & retries",
            [("sum by (task) (increase(aipulse_celery_task_failures_total[30m]))", "failed {{task}}"),
             ("sum by (task) (increase(aipulse_celery_task_retries_total[30m]))", "retried {{task}}")], w=12)
    b.row("Ingestion")
    b.panel("timeseries", "Ingestion jobs per hour by status",
            [("sum by (status) (increase(aipulse_ingestion_jobs_total[1h]))", "{{status}}")], stack=True, w=12)
    b.panel("timeseries", "Longest job in the last hour by connector",
            [("aipulse_ingestion_job_duration_seconds_max_1h", "{{connector}}")], unit="s", w=12)
    b.panel("table", "Data source availability",
            [("aipulse_source_up", ""), ("aipulse_source_consecutive_failures", ""),
             ("time() - aipulse_source_last_success_timestamp_seconds", "")],
            w=24, h=10, desc="1 = last run succeeded and not overdue. Age = seconds since the last success.",
            options={"showHeader": True, "sortBy": [{"displayName": "Value #A", "desc": False}]})
    b.panels[-1]["targets"] = [
        {"refId": r, "expr": e, "format": "table", "instant": True, "datasource": DS}
        for r, e in (("A", "aipulse_source_up"), ("B", "aipulse_source_consecutive_failures"),
                     ("C", "time() - aipulse_source_last_success_timestamp_seconds"))
    ]
    b.panels[-1]["transformations"] = [
        {"id": "merge", "options": {}},
        {"id": "organize", "options": {
            "excludeByName": {"Time": True, "__name__": True, "instance": True, "job": True, "project": True},
            "renameByName": {"Value #A": "Up", "Value #B": "Consecutive failures", "Value #C": "Seconds since success",
                             "source": "Source", "connector": "Connector"}}},
    ]
    b.row("AI providers")
    b.panel("stat", "AI error ratio (1h)",
            [('sum(increase(aipulse_ai_calls_total{outcome="error"}[1h])) / clamp_min(sum(increase(aipulse_ai_calls_total[1h])), 1)', "")],
            w=6, h=4, unit="percentunit", thresholds=[(0.05, "orange"), (0.2, "red")])
    b.panel("stat", "Tokens (24h)", [("sum(increase(aipulse_ai_tokens_total[24h]))", "")], w=6, h=4, unit="short")
    b.panel("stat", "Estimated cost (24h)", [("sum(increase(aipulse_ai_cost_usd_total[24h]))", "")], w=6, h=4,
            unit="currencyUSD", decimals=2)
    b.panel("stat", "Items awaiting analysis", [("aipulse_articles_unanalysed", "")], w=6, h=4,
            thresholds=[(500, "orange"), (2000, "red")])
    b.panel("timeseries", "AI calls by provider / outcome",
            [("sum by (provider, outcome) (increase(aipulse_ai_calls_total[15m]))", "{{provider}} {{outcome}}")], w=12)
    b.panel("timeseries", "Provider errors by purpose",
            [('sum by (provider, purpose) (increase(aipulse_ai_calls_total{outcome="error"}[15m]))', "{{provider}} {{purpose}}")], w=12)
    b.panel("timeseries", "Tokens per hour",
            [("sum by (model, direction) (increase(aipulse_ai_tokens_total[1h]))", "{{model}} {{direction}}")], stack=True, w=12)
    b.panel("timeseries", "Estimated cost per day",
            [("sum by (model) (increase(aipulse_ai_cost_usd_total[1d]))", "{{model}}")], unit="currencyUSD", w=12)
    b.dump("ai-pulse-pipeline", "AI Pulse — Pipeline, ingestion & AI",
           "Celery queues and job durations, scheduler liveness, ingestion results, source availability, AI errors, tokens and cost.",
           ["ai-pulse"])


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    service()
    pipeline()
    print("dashboards written to", OUT)
