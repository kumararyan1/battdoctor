from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader
from plotly.offline import get_plotlyjs

from battdoctor.analyze.attribution import analyze_window, format_duration
from battdoctor.store import Store

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
MAX_BACKGROUND_SEGMENTS = 500


def _dt(ts: float | int | None) -> datetime:
    return datetime.fromtimestamp(float(ts or 0))


def _format_ts(ts: float | None) -> str:
    if ts is None:
        return "unknown"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _format_watts(value: float | None) -> str:
    return f"{value:.1f} W" if value is not None else "unknown"


def _format_pct(value: float | None) -> str:
    return f"{value:.0f}%" if value is not None else "unknown"


def _layout(title: str, *, height: int = 320, **overrides: Any) -> dict[str, Any]:
    layout: dict[str, Any] = {
        "template": "plotly_dark",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {
            "color": "#c9d1d9",
            "family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            "size": 12,
        },
        "margin": {"l": 52, "r": 20, "t": 46, "b": 40},
        "height": height,
        "title": {
            "text": title,
            "x": 0.01,
            "xanchor": "left",
            "font": {"size": 14, "color": "#e6edf3"},
        },
        "hovermode": "x unified",
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "font": {"size": 10},
        },
    }
    layout.update(overrides)
    return layout


def _style_axes(
    fig: go.Figure,
    *,
    x_title: str | None = None,
    y_title: str | None = None,
) -> None:
    fig.update_xaxes(
        gridcolor="rgba(240,246,252,0.06)",
        zerolinecolor="rgba(240,246,252,0.10)",
        title_text=x_title,
    )
    fig.update_yaxes(
        gridcolor="rgba(240,246,252,0.06)",
        zerolinecolor="rgba(240,246,252,0.10)",
        title_text=y_title,
    )


def _empty_figure(title: str, message: str = "No data in this window") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**_layout(title))
    fig.add_annotation(
        text=message,
        showarrow=False,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        font={"size": 13, "color": "#8b949e"},
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _ac_segments(samples: list[dict[str, Any]]) -> list[tuple[datetime, datetime, int]]:
    segments: list[tuple[datetime, datetime, int]] = []
    for current, following in zip(samples, samples[1:], strict=False):
        state = current.get("ac_connected")
        start = current.get("ts")
        end = following.get("ts")
        if state is None or start is None or end is None:
            continue
        state = int(state)
        if segments and segments[-1][2] == state:
            segments[-1] = (segments[-1][0], _dt(end), state)
        else:
            segments.append((_dt(start), _dt(end), state))
    return segments


def _battery_figure(samples: list[dict[str, Any]]) -> go.Figure:
    times = [_dt(row.get("ts")) for row in samples]
    percentages = [row.get("battery_pct") for row in samples]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=times,
            y=percentages,
            mode="lines",
            name="Battery %",
            line={"color": "#3fb950", "width": 2},
            connectgaps=True,
            hovertemplate="%{x}<br>%{y:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(**_layout("Battery % over time"))
    _style_axes(fig, y_title="Battery %")
    fig.update_yaxes(range=[0, 100])
    segments = _ac_segments(samples)
    if len(segments) <= MAX_BACKGROUND_SEGMENTS:
        for start, end, state in segments:
            color = "rgba(88,166,255,0.10)" if state == 1 else "rgba(63,185,80,0.055)"
            fig.add_shape(
                type="rect",
                x0=start,
                x1=end,
                y0=0,
                y1=100,
                fillcolor=color,
                line={"width": 0},
                layer="below",
            )
    return fig


def _power_figure(samples: list[dict[str, Any]]) -> go.Figure:
    times: list[datetime] = []
    values: list[float] = []
    for row in samples:
        if row.get("ac_connected") == 0:
            raw = row.get("battery_power_w")
            value = abs(raw) if raw is not None else None
        else:
            value = row.get("system_power_w")
        if value is None:
            continue
        times.append(_dt(row.get("ts")))
        values.append(float(value))
    if not values:
        return _empty_figure("Power draw over time", "No power readings in this window")
    average = sum(values) / len(values)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=times,
            y=values,
            mode="lines",
            name="Power draw",
            line={"color": "#f0883e", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(240,136,62,0.10)",
            hovertemplate="%{x}<br>%{y:.1f} W<extra></extra>",
        )
    )
    fig.add_hline(
        y=average,
        line={"color": "#8b949e", "width": 1, "dash": "dash"},
        annotation_text=f"avg {average:.1f} W",
        annotation_position="top right",
        annotation_font={"color": "#8b949e", "size": 10},
    )
    fig.update_layout(**_layout("Power draw over time"))
    _style_axes(fig, y_title="Watts")
    return fig


def _memory_figure(samples: list[dict[str, Any]]) -> go.Figure:
    times = [_dt(row.get("ts")) for row in samples]
    series = [
        ("Swap used (MB)", "swap_used_mb", "#58a6ff"),
        ("Swap total (MB)", "swap_total_mb", "#8b949e"),
        ("Compressor (MB)", "compressor_mb", "#d2a8ff"),
    ]
    if not any(row.get(key) is not None for row in samples for _, key, _ in series):
        return _empty_figure("Memory pressure over time", "No memory readings in this window")
    fig = go.Figure()
    for name, key, color in series:
        fig.add_trace(
            go.Scatter(
                x=times,
                y=[row.get(key) for row in samples],
                mode="lines",
                name=name,
                line={"color": color, "width": 2},
                connectgaps=True,
                hovertemplate=f"%{{x}}<br>{name}: %{{y:.0f}} MB<extra></extra>",
            )
        )
    fig.update_layout(**_layout("Memory pressure over time"))
    _style_axes(fig, y_title="Megabytes")
    return fig


def _apps_figure(processes: list[dict[str, Any]]) -> go.Figure:
    if not processes:
        return _empty_figure("Top apps by CPU", "No process data in this window")
    per_timestamp: dict[float, dict[str, float]] = {}
    totals: dict[str, float] = {}
    for row in processes:
        timestamp = row.get("ts")
        if timestamp is None:
            continue
        name = row.get("name") or "unknown"
        if name.startswith("Brave"):
            name = "Brave"
        cpu = float(row.get("cpu_pct") or 0.0)
        bucket = per_timestamp.setdefault(float(timestamp), {})
        bucket[name] = bucket.get(name, 0.0) + cpu
        totals[name] = totals.get(name, 0.0) + cpu
    if not totals:
        return _empty_figure("Top apps by CPU", "No process CPU data in this window")
    top_names = [
        name for name, _ in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:8]
    ]
    timestamps = sorted(per_timestamp)
    fig = go.Figure()
    for name in top_names:
        fig.add_trace(
            go.Scatter(
                x=[_dt(timestamp) for timestamp in timestamps],
                y=[per_timestamp[timestamp].get(name, 0.0) for timestamp in timestamps],
                mode="lines",
                name=name,
                stackgroup="apps",
                line={"width": 0.5},
                connectgaps=True,
                hovertemplate=f"{name}: %{{y:.1f}}%<extra></extra>",
            )
        )
    fig.update_layout(**_layout("Top apps by CPU (stacked)"))
    _style_axes(fig, y_title="CPU %")
    return fig


def _cpu_figure(samples: list[dict[str, Any]]) -> go.Figure:
    if not any(
        row.get("load1") is not None or row.get("top_cpu_pct") is not None for row in samples
    ):
        return _empty_figure("CPU load", "No CPU readings in this window")
    times = [_dt(row.get("ts")) for row in samples]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=times,
            y=[row.get("load1") for row in samples],
            mode="lines",
            name="Load average (1m)",
            line={"color": "#58a6ff", "width": 2},
            connectgaps=True,
            hovertemplate="%{x}<br>load1: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=[row.get("top_cpu_pct") for row in samples],
            mode="lines",
            name="Top process CPU %",
            line={"color": "#ffa657", "width": 2},
            connectgaps=True,
            hovertemplate="%{x}<br>top CPU: %{y:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(**_layout("CPU load"))
    _style_axes(fig, y_title="Load / CPU %")
    return fig


def _assertions_figure(assertions: list[dict[str, Any]]) -> go.Figure:
    if not assertions:
        return _empty_figure("Sleep / display assertions", "No assertions in this window")
    counts: dict[tuple[str, str], int] = {}
    for row in assertions:
        process = row.get("process") or "unknown"
        assertion_type = row.get("type") or "unknown"
        key = (process, assertion_type)
        counts[key] = counts.get(key, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: item[1])
    labels = [f"{process} · {assertion_type}" for (process, assertion_type), _ in ordered]
    values = [count for _, count in ordered]
    height = max(280, 28 * len(labels) + 100)
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker={"color": "#58a6ff"},
            hovertemplate="%{y}<br>%{x} assertion(s)<extra></extra>",
        )
    )
    fig.update_layout(**_layout("Sleep / display assertions", height=height))
    _style_axes(fig, x_title="Count")
    return fig


def _events_figure(events: list[dict[str, Any]]) -> go.Figure | None:
    if not events:
        return None
    kinds = sorted({row.get("kind") or "unknown" for row in events})
    fig = go.Figure(
        go.Scatter(
            x=[_dt(row.get("ts")) for row in events],
            y=[row.get("kind") or "unknown" for row in events],
            mode="markers",
            name="Events",
            marker={"size": 10, "color": "#d2a8ff", "line": {"width": 1, "color": "#0d1117"}},
            text=[row.get("detail") or "" for row in events],
            hovertemplate="%{x}<br><b>%{y}</b><br>%{text}<extra></extra>",
        )
    )
    fig.update_layout(**_layout("Events timeline"))
    fig.update_yaxes(type="category", categoryorder="array", categoryarray=kinds)
    _style_axes(fig)
    return fig


def _figure_html(fig: go.Figure, div_id: str) -> str:
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id=div_id,
        config={"responsive": True, "displaylogo": False},
    )


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _window_pressure(samples: list[dict[str, Any]]) -> str:
    pressures = [row.get("memory_pressure") for row in samples if row.get("memory_pressure")]
    if "critical" in pressures:
        return "critical"
    if "warning" in pressures:
        return "warning"
    if pressures:
        return str(pressures[-1])
    return "unknown"


def render_report(
    store: Store,
    since: float,
    out_path: Path,
    title: str = "battdoctor report",
    until: float | None = None,
) -> Path:
    samples = [dict(row) for row in store.query_samples(since, until)]
    processes = [dict(row) for row in store.query_processes(since, until)]
    assertions = [dict(row) for row in store.query_assertions(since, until)]
    events = [dict(row) for row in store.query_events(since, until)]
    analysis = analyze_window(store, since, until)

    has_samples = bool(samples)
    charts: dict[str, str] = {}
    if has_samples:
        charts["battery"] = _figure_html(_battery_figure(samples), "chart-battery")
        charts["power"] = _figure_html(_power_figure(samples), "chart-power")
        charts["memory"] = _figure_html(_memory_figure(samples), "chart-memory")
        charts["apps"] = _figure_html(_apps_figure(processes), "chart-apps")
        charts["cpu"] = _figure_html(_cpu_figure(samples), "chart-cpu")
        charts["assertions"] = _figure_html(_assertions_figure(assertions), "chart-assertions")
        events_figure = _events_figure(events)
        if events_figure is not None:
            charts["events"] = _figure_html(events_figure, "chart-events")

    window_start = analysis.window_start if analysis.window_start is not None else since
    window_end = analysis.window_end if analysis.window_end is not None else (until or time.time())

    template = _environment().get_template("report.html.j2")
    html = template.render(
        title=title,
        analysis=analysis,
        charts=charts,
        has_samples=has_samples,
        include_events="events" in charts,
        memory_pressure=_window_pressure(samples),
        expected_runtime=format_duration(analysis.expected_runtime_min),
        current_power=_format_watts(analysis.current_power_w),
        battery_health=_format_pct(analysis.battery_health_pct),
        window_start=_format_ts(window_start),
        window_end=_format_ts(window_end),
        generated_at=_format_ts(analysis.generated_at),
        plotlyjs=get_plotlyjs() if charts else "",
    )

    target = Path(out_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    target.chmod(0o600)
    return target
