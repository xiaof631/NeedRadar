"""轻量级 Prometheus 指标实现，兼容常用接口。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


class CollectorRegistry:
    """存储并管理所有注册的指标。"""

    def __init__(self) -> None:
        self._metrics: list[BaseMetric] = []

    def register(self, metric: BaseMetric) -> None:
        self._metrics.append(metric)

    def collect(self) -> Iterable[BaseMetric]:
        return tuple(self._metrics)

    def get_sample_value(self, name: str, labels: dict[str, Any] | None = None) -> float | None:
        for metric in self._metrics:
            if metric.name == name:
                return metric.get_sample_value(labels or {})
        return None


class BaseMetric:
    name: str
    documentation: str
    type_name: str

    def render(self) -> list[str]:  # pragma: no cover - 抽象方法
        raise NotImplementedError

    def get_sample_value(self, labels: dict[str, Any]) -> float | None:  # pragma: no cover
        return None


class Counter(BaseMetric):
    type_name = "counter"

    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: tuple[str, ...] = (),
        registry: CollectorRegistry | None = None,
    ) -> None:
        self.name = name
        self.documentation = documentation
        self.labelnames = tuple(labelnames)
        self._values: dict[tuple[Any, ...], float] = {}
        if registry is not None:
            registry.register(self)

    def labels(self, *label_values: Any, **label_dict: Any) -> _CounterChild:
        values = _resolve_labels(self.labelnames, label_values, label_dict)
        return _CounterChild(self, values)

    def inc(self, amount: float = 1.0) -> None:
        self.labels().inc(amount)

    def _increment(self, key: tuple[Any, ...], amount: float) -> None:
        self._values[key] = self._values.get(key, 0.0) + amount

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.documentation}", f"# TYPE {self.name} {self.type_name}"]
        if not self._values:
            lines.append(f"{self.name} 0")
            return lines
        for key, value in sorted(self._values.items()):
            labels = _format_labels(zip(self.labelnames, key))
            lines.append(f"{self.name}{labels} {value}")
        return lines

    def get_sample_value(self, labels: dict[str, Any]) -> float | None:
        key = tuple(labels.get(name) for name in self.labelnames)
        if not self.labelnames:
            key = ()
        return self._values.get(key)


class Histogram(BaseMetric):
    type_name = "histogram"

    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: tuple[str, ...],
        registry: CollectorRegistry | None = None,
        buckets: tuple[float, ...] = (),
    ) -> None:
        self.name = name
        self.documentation = documentation
        self.labelnames = tuple(labelnames)
        self.buckets = tuple(sorted(buckets)) or (0.1, 1.0, 5.0)
        self._samples: dict[tuple[Any, ...], _HistogramBucket] = {}
        if registry is not None:
            registry.register(self)

    def labels(self, *label_values: Any, **label_dict: Any) -> _HistogramChild:
        values = _resolve_labels(self.labelnames, label_values, label_dict)
        return _HistogramChild(self, values)

    def observe(self, value: float) -> None:
        self.labels().observe(value)

    def _record(self, key: tuple[Any, ...], value: float) -> None:
        bucket = self._samples.setdefault(key, _HistogramBucket(self.buckets))
        bucket.observe(value)

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.documentation}", f"# TYPE {self.name} {self.type_name}"]
        for key, bucket in sorted(self._samples.items()):
            base_pairs = list(zip(self.labelnames, key))
            for le, count in bucket.render_buckets():
                labels = _format_labels(base_pairs + [("le", le)])
                lines.append(f"{self.name}_bucket{labels} {count}")
            base_label = _format_labels(base_pairs)
            lines.append(f"{self.name}_sum{base_label} {bucket.sum}")
            lines.append(f"{self.name}_count{base_label} {bucket.count}")
        return lines

    def get_sample_value(self, labels: dict[str, Any]) -> float | None:
        key = tuple(labels.get(name) for name in self.labelnames)
        bucket = self._samples.get(key)
        if bucket is None:
            return None
        return float(bucket.count)


@dataclass
class _HistogramBucket:
    boundaries: tuple[float, ...]

    def __post_init__(self) -> None:
        self.count = 0
        self.sum = 0.0
        self.bucket_counts = {boundary: 0 for boundary in self.boundaries}
        self.bucket_counts[float("inf")] = 0

    def observe(self, value: float) -> None:
        self.count += 1
        self.sum += value
        for boundary in self.boundaries:
            if value <= boundary:
                self.bucket_counts[boundary] += 1
        self.bucket_counts[float("inf")] += 1

    def render_buckets(self) -> list[tuple[str, int]]:
        cumulative = 0
        lines: list[tuple[str, int]] = []
        for boundary in self.boundaries:
            cumulative = self.bucket_counts.get(boundary, cumulative)
            lines.append((str(boundary), cumulative))
        lines.append(("+Inf", self.bucket_counts.get(float("inf"), self.count)))
        return lines


class _CounterChild:
    def __init__(self, counter: Counter, key: tuple[Any, ...]) -> None:
        self._counter = counter
        self._key = key

    def inc(self, amount: float = 1.0) -> None:
        self._counter._increment(self._key, amount)


class _HistogramChild:
    def __init__(self, histogram: Histogram, key: tuple[Any, ...]) -> None:
        self._histogram = histogram
        self._key = key

    def observe(self, value: float) -> None:
        self._histogram._record(self._key, value)


def _resolve_labels(
    labelnames: tuple[str, ...],
    label_values: tuple[Any, ...],
    label_dict: dict[str, Any],
) -> tuple[Any, ...]:
    if label_dict:
        values = tuple(label_dict[name] for name in labelnames)
    else:
        values = label_values
    if len(values) != len(labelnames):
        if labelnames:
            raise ValueError("Label count mismatch")
        return ()
    return values


def _format_labels(pairs: Iterable[tuple[str, Any]]) -> str:
    data = [(name, value) for name, value in pairs]
    if not data:
        return ""
    payload = ",".join(f'{name}="{value}"' for name, value in data)
    return "{" + payload + "}"


def generate_latest(registry: CollectorRegistry) -> bytes:
    lines: list[str] = []
    for metric in registry.collect():
        lines.extend(metric.render())
    payload = "\n".join(lines) + "\n"
    return payload.encode("utf-8")


__all__ = [
    "CollectorRegistry",
    "Counter",
    "Histogram",
    "generate_latest",
    "CONTENT_TYPE_LATEST",
]
