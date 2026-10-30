from __future__ import annotations

import statistics
from collections.abc import Sequence

MAD_SCALE = 1.4826


def robust_zscore(values: Sequence[float]) -> list[float]:
    data = [float(value) for value in values]
    if not data:
        return []
    center = statistics.median(data)
    mad = statistics.median([abs(value - center) for value in data])
    scale = MAD_SCALE * mad
    if scale == 0:
        try:
            scale = statistics.stdev(data)
        except statistics.StatisticsError:
            scale = 0.0
    if scale == 0:
        return [0.0 for _ in data]
    return [(value - center) / scale for value in data]


def find_spikes(values: Sequence[float], threshold: float = 3.5) -> list[int]:
    return [
        index
        for index, score in enumerate(robust_zscore(values))
        if abs(score) > threshold
    ]


def ewma(values: Sequence[float], alpha: float = 0.3) -> list[float]:
    data = [float(value) for value in values]
    if not data:
        return []
    smoothed = [data[0]]
    for value in data[1:]:
        smoothed.append(alpha * value + (1 - alpha) * smoothed[-1])
    return smoothed


def level_shift(values: Sequence[float]) -> dict:
    data = [float(value) for value in values]
    if len(data) < 4:
        return {"pct_change": 0.0, "direction": "flat"}
    split = len(data) // 2
    first_mean = statistics.fmean(data[:split])
    second_mean = statistics.fmean(data[split:])
    if first_mean == 0:
        pct_change = 0.0
    else:
        pct_change = (second_mean - first_mean) / abs(first_mean) * 100
    if second_mean > first_mean:
        direction = "up"
    elif second_mean < first_mean:
        direction = "down"
    else:
        direction = "flat"
    return {"pct_change": round(pct_change, 2), "direction": direction}
