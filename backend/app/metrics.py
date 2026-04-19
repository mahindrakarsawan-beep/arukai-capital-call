"""Lightweight metrics — Prometheus-compatible text format, no dependencies."""
import time
from collections import defaultdict
from typing import Optional

_start_time = time.time()
_request_count: dict[str, int] = defaultdict(int)
_request_latency_sum: dict[str, float] = defaultdict(float)
_error_count: int = 0
_classification_count: dict[str, int] = defaultdict(int)
_last_classification_time: Optional[float] = None


def record_request(method: str, path: str, status: int, duration: float):
    key = f'{method} {path} {status}'
    _request_count[key] += 1
    _request_latency_sum[key] += duration
    global _error_count
    if status >= 500:
        _error_count += 1


def record_classification(provider: str, doc_type: str, duration_s: float):
    _classification_count[f"{provider}:{doc_type}"] += 1
    global _last_classification_time
    _last_classification_time = time.time()


def get_metrics_text() -> str:
    lines = []
    lines.append("# HELP request_total Total HTTP requests")
    lines.append("# TYPE request_total counter")
    for key, count in _request_count.items():
        method, path, status = key.rsplit(" ", 2)
        lines.append(f'request_total{{method="{method}",path="{path}",status="{status}"}} {count}')

    lines.append("# HELP request_latency_seconds_sum Total request latency")
    lines.append("# TYPE request_latency_seconds_sum counter")
    for key, total in _request_latency_sum.items():
        method, path, status = key.rsplit(" ", 2)
        lines.append(f'request_latency_seconds_sum{{method="{method}",path="{path}",status="{status}"}} {total:.4f}')

    lines.append("# HELP classification_total Total classifications")
    lines.append("# TYPE classification_total counter")
    for key, count in _classification_count.items():
        provider, doc_type = key.split(":", 1)
        lines.append(f'classification_total{{provider="{provider}",doc_type="{doc_type}"}} {count}')

    lines.append(f"# HELP uptime_seconds Seconds since startup")
    lines.append(f"uptime_seconds {time.time() - _start_time:.0f}")
    return "\n".join(lines) + "\n"


def get_detailed_health() -> dict:
    total_requests = sum(_request_count.values())
    total_latency = sum(_request_latency_sum.values())
    return {
        "uptime_seconds": round(time.time() - _start_time),
        "total_requests": total_requests,
        "avg_latency_ms": round((total_latency / total_requests * 1000) if total_requests else 0, 1),
        "error_count": _error_count,
        "error_rate": round(_error_count / total_requests, 4) if total_requests else 0,
        "last_classification": _last_classification_time,
        "classifications": dict(_classification_count),
    }
