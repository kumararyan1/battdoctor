from __future__ import annotations

import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import battdoctor
from battdoctor.analyze.attribution import (
    Analysis,
    analyze_snapshot,
    format_duration,
    measured_power_w,
)
from battdoctor.analyze.playbooks import PLAYBOOKS, run_playbook
from battdoctor.collectors.power_events import collect_power_events
from battdoctor.collectors.powermetrics import is_available
from battdoctor.collectors.snapshot import collect_snapshot
from battdoctor.collectors.system import collect_static
from battdoctor.models import ProcessInfo, Snapshot
from battdoctor.store import DISPLAY_ASSERTION_TYPES, SLEEP_ASSERTION_TYPES, Store

DEFAULT_DB = Path.home() / ".battdoctor" / "battdoctor.db"
SINCE_UNITS = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0, "w": 604800.0}
POWERMETRICS_HINT = "sudo scripts/install_helper.sh"

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Local macOS battery and performance diagnostics.",
)
console = Console()


def parse_since(value: str) -> float:
    text = value.strip()
    if not text:
        raise typer.BadParameter(
            "provide a duration like 30s, 15m, 24h, 7d, 2w, or an ISO datetime"
        )
    lowered = text.lower()
    unit = lowered[-1]
    if unit in SINCE_UNITS:
        try:
            amount = float(lowered[:-1])
        except ValueError as exc:
            raise typer.BadParameter(f"invalid duration: {value}") from exc
        if not math.isfinite(amount) or amount <= 0:
            raise typer.BadParameter("duration must be a finite value greater than zero")
        return time.time() - amount * SINCE_UNITS[unit]
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError as exc:
        raise typer.BadParameter(f"invalid duration or datetime: {value}") from exc


def _fmt(value: float | None, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}{suffix}"


def _fmt_int(value: int | None, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value}{suffix}"


def _shorten(text: str, limit: int = 140) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "..."


def _top_processes(snapshot: Snapshot, limit: int = 10) -> list[ProcessInfo]:
    return sorted(
        snapshot.processes,
        key=lambda process: (process.energy_impact or 0.0, process.cpu_pct),
        reverse=True,
    )[:limit]


def _print_header(snapshot: Snapshot) -> None:
    system = snapshot.system
    console.print()
    console.print(
        f"[bold cyan]battdoctor[/bold cyan] [dim]·[/dim] "
        f"[bold]{system.model or 'Mac'}[/bold] [dim]·[/dim] "
        f"{system.chip or 'unknown chip'} [dim]·[/dim] "
        f"macOS {system.os_version or 'unknown'} ({system.os_build or 'unknown build'})"
    )


def _print_summary(analysis: Analysis) -> None:
    snapshot = analysis.snapshot
    lines = [analysis.summary]
    if snapshot is not None:
        battery = snapshot.battery
        memory = snapshot.memory
        status = []
        if battery.external_connected is not None:
            status.append("AC connected" if battery.external_connected else "on battery")
        if battery.charging:
            status.append("charging")
        if battery.fully_charged:
            status.append("fully charged")
        battery_line = (
            f"Battery {_fmt(battery.percent, 1, '%')} · "
            f"power {_fmt(measured_power_w(snapshot), 2, ' W')}"
        )
        if status:
            battery_line += f" · {', '.join(status)}"
        lines.append(battery_line)
        lines.append(
            f"Runtime {format_duration(analysis.expected_runtime_min)} · "
            f"health {_fmt(analysis.battery_health_pct, 1, '%')} · "
            f"usable {_fmt(analysis.usable_wh, 1, ' Wh')}"
        )
        lines.append(
            f"Swap {_fmt(memory.swap_used_mb, 0, ' MB')} / {_fmt(memory.swap_total_mb, 0, ' MB')}"
            f" · compressor {_fmt(memory.compressor_mb, 0, ' MB')}"
            f" · pressure {memory.pressure or 'unknown'}"
        )
        if battery.cycle_count is not None:
            lines.append(f"Charge cycles {battery.cycle_count}")
    if analysis.warnings:
        lines.append("[yellow]Warnings: " + "; ".join(analysis.warnings) + "[/yellow]")
    console.print(Panel("\n".join(lines), title="Summary", border_style="cyan"))


def _print_causes(analysis: Analysis) -> None:
    if not analysis.causes:
        console.print("[dim]No ranked causes found.[/dim]")
        return
    table = Table(title="Ranked causes")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Cause", style="bold")
    table.add_column("Est. W", justify="right")
    table.add_column("Share", justify="right")
    table.add_column("Confidence")
    table.add_column("Evidence", overflow="fold")
    table.add_column("Action", overflow="fold")
    for index, cause in enumerate(analysis.causes, start=1):
        table.add_row(
            str(index),
            cause.name,
            _fmt(cause.estimated_w, 2),
            _fmt(cause.share_pct, 1, "%"),
            cause.confidence,
            "; ".join(cause.evidence),
            cause.action,
        )
    console.print(table)


def _print_processes(snapshot: Snapshot) -> None:
    processes = _top_processes(snapshot)
    if not processes:
        return
    table = Table(title="Top processes")
    table.add_column("PID", justify="right")
    table.add_column("Process")
    table.add_column("CPU %", justify="right")
    table.add_column("Mem %", justify="right")
    table.add_column("RSS MB", justify="right")
    table.add_column("Energy impact", justify="right")
    table.add_column("Wakeups", justify="right")
    for process in processes:
        table.add_row(
            str(process.pid),
            process.name,
            _fmt(process.cpu_pct, 1),
            _fmt(process.mem_pct, 1),
            _fmt(process.rss_mb, 0),
            _fmt(process.energy_impact, 1),
            _fmt_int(process.wakeups),
        )
    console.print(table)


def _print_assertions(snapshot: Snapshot, limit: int = 10) -> None:
    active = [
        assertion
        for assertion in snapshot.assertions
        if assertion.type in SLEEP_ASSERTION_TYPES | DISPLAY_ASSERTION_TYPES
    ]
    if not active:
        console.print("[dim]No sleep or display assertions.[/dim]")
        return
    active.sort(key=lambda assertion: assertion.duration_s or 0, reverse=True)
    table = Table(title="Sleep / display assertions")
    table.add_column("Process")
    table.add_column("Type")
    table.add_column("Assertion", overflow="fold")
    table.add_column("Duration", justify="right")
    for assertion in active[:limit]:
        table.add_row(
            assertion.process,
            assertion.type,
            assertion.name,
            format_duration((assertion.duration_s or 0) / 60),
        )
    console.print(table)


def _print_settings(snapshot: Snapshot) -> None:
    settings = snapshot.battery_settings()
    if not settings:
        console.print("[dim]No battery power settings reported.[/dim]")
        return
    table = Table(title="Battery power settings")
    table.add_column("Setting")
    table.add_column("Value")
    for key, value in settings.items():
        table.add_row(key, str(value))
    console.print(table)


def _print_events(snapshot: Snapshot, limit: int = 10) -> None:
    events = snapshot.events[-limit:]
    if not events:
        return
    table = Table(title="Recent power events")
    table.add_column("Time")
    table.add_column("Kind")
    table.add_column("Detail", overflow="fold")
    for event in events:
        stamp = datetime.fromtimestamp(event.ts).strftime("%Y-%m-%d %H:%M:%S")
        table.add_row(stamp, event.kind, _shorten(event.detail))
    console.print(table)


def _print_analysis(analysis: Analysis) -> None:
    if analysis.snapshot is None:
        console.print(Panel(analysis.summary, title="Summary", border_style="cyan"))
        return
    snapshot = analysis.snapshot
    _print_header(snapshot)
    _print_summary(analysis)
    _print_causes(analysis)
    _print_processes(snapshot)
    _print_assertions(snapshot)
    _print_settings(snapshot)
    _print_events(snapshot)


def _warn_powermetrics(*, err: bool = False) -> None:
    message = (
        "powermetrics is not available; sampling will run unprivileged. "
        f"Install the helper with {POWERMETRICS_HINT}."
    )
    if err:
        typer.echo(message, err=True)
    else:
        console.print(f"[yellow]{message}[/yellow]")


def _print_record_status(sample: Snapshot, count: int) -> None:
    battery = sample.battery
    memory = sample.memory
    top = max(
        sample.processes,
        key=lambda process: (process.cpu_pct, process.energy_impact or 0.0),
        default=None,
    )
    top_text = f"{top.name} {top.cpu_pct:.1f}% CPU" if top else "n/a"
    swap = (
        f"{memory.swap_used_mb:.0f}/{memory.swap_total_mb:.0f} MB"
        if memory.swap_used_mb is not None and memory.swap_total_mb is not None
        else "n/a"
    )
    console.print(
        f"[dim]{datetime.now().strftime('%H:%M:%S')}[/dim] "
        f"samples={count} battery={_fmt(battery.percent, 1, '%')} "
        f"power={_fmt(measured_power_w(sample), 2, ' W')} swap={swap} top={top_text}"
    )


@app.command()
def snapshot(
    json_output: Annotated[
        bool, typer.Option("--json", help="Print the analysis as JSON.")
    ] = False,
    save: Annotated[
        bool, typer.Option("--save", help="Save the snapshot to the database.")
    ] = False,
    db: Annotated[
        Path, typer.Option("--db", help="SQLite database path.")
    ] = DEFAULT_DB,
    powermetrics: Annotated[
        bool, typer.Option("--powermetrics", help="Include powermetrics energy data.")
    ] = False,
    lite: Annotated[
        bool,
        typer.Option("--lite", help="Skip slow collectors (for the menu bar app)."),
    ] = False,
) -> None:
    if powermetrics and not is_available():
        _warn_powermetrics(err=json_output)
    sample = collect_snapshot(with_powermetrics=powermetrics, lite=lite)
    analysis = analyze_snapshot(sample)
    if json_output:
        typer.echo(json.dumps(analysis.to_dict(include_snapshot=True), indent=2, default=str))
    else:
        _print_analysis(analysis)
    if save:
        store = Store(db)
        try:
            store.insert_snapshot(sample)
            if json_output:
                typer.echo(f"Saved snapshot to {store.path}", err=True)
            else:
                console.print(f"[green]Saved snapshot to {store.path}[/green]")
        finally:
            store.close()


@app.command()
def record(
    interval: Annotated[
        float, typer.Option("--interval", help="Seconds between samples.")
    ] = 5.0,
    db: Annotated[
        Path, typer.Option("--db", help="SQLite database path.")
    ] = DEFAULT_DB,
    duration: Annotated[
        float, typer.Option("--duration", help="Stop after N seconds (0 = until Ctrl-C).")
    ] = 0.0,
    powermetrics: Annotated[
        bool, typer.Option("--powermetrics", help="Include powermetrics energy data.")
    ] = False,
    process_every: Annotated[
        float, typer.Option("--process-every", help="Seconds between process/assertion rows.")
    ] = 30.0,
) -> None:
    if interval <= 0:
        raise typer.BadParameter("--interval must be greater than zero")
    if process_every < 0:
        raise typer.BadParameter("--process-every cannot be negative")
    if duration < 0:
        raise typer.BadParameter("--duration cannot be negative")
    if powermetrics and not is_available():
        _warn_powermetrics()

    static = collect_static()
    store = Store(db)
    count = 0
    started = time.time()
    last_process_ts = 0.0
    last_status = 0.0
    last_events_ts = 0.0
    interrupted = False
    console.print(
        f"[bold cyan]Recording[/bold cyan] to {store.path} every {interval:g}s "
        f"({'until Ctrl-C' if duration <= 0 else f'for {duration:g}s'})"
    )
    try:
        while duration <= 0 or time.time() - started < duration:
            sample = collect_snapshot(
                full=False,
                static=static,
                with_powermetrics=powermetrics,
            )
            count += 1
            should_store = last_process_ts == 0.0 or (
                sample.timestamp - last_process_ts
            ) >= process_every
            if should_store:
                last_process_ts = sample.timestamp
            store.insert_snapshot(sample, store_processes=should_store)
            if sample.timestamp - last_events_ts >= 60 or last_events_ts == 0.0:
                store.insert_events(collect_power_events())
                last_events_ts = sample.timestamp
            if sample.timestamp - last_status >= 30 or last_status == 0.0:
                _print_record_status(sample, count)
                last_status = sample.timestamp
            remaining = interval - (time.time() - sample.timestamp)
            if remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        interrupted = True
        console.print()
        console.print("[yellow]Interrupted.[/yellow]")
    finally:
        store.close()
    console.print(f"[green]Recorded {count} sample(s) to {store.path}[/green]")
    if interrupted:
        raise typer.Exit(code=130)


@app.command()
def report(
    since: Annotated[
        str, typer.Option("--since", help="Window such as 30m, 24h, 7d, or an ISO datetime.")
    ] = "24h",
    db: Annotated[
        Path, typer.Option("--db", help="SQLite database path.")
    ] = DEFAULT_DB,
    out: Annotated[
        Path, typer.Option("--out", help="Output HTML path.")
    ] = Path("battdoctor-report.html"),
    title: Annotated[
        str, typer.Option("--title", help="Report title.")
    ] = "battdoctor report",
) -> None:
    try:
        from battdoctor.report.render import render_report
    except ImportError as exc:
        typer.echo(
            "Report dependencies are not installed. "
            "Install with: pip install 'battdoctor[report]'",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    since_ts = parse_since(since)
    store = Store(db)
    try:
        path = render_report(store, since_ts, out, title=title)
    finally:
        store.close()
    console.print(f"[green]Wrote report to {path}[/green]")


@app.command()
def playbook(
    name: Annotated[str, typer.Argument(help="Playbook name.")],
    since: Annotated[
        str, typer.Option("--since", help="Window such as 30m, 24h, 7d, or an ISO datetime.")
    ] = "24h",
    db: Annotated[
        Path, typer.Option("--db", help="SQLite database path.")
    ] = DEFAULT_DB,
) -> None:
    since_ts = parse_since(since)
    store = Store(db)
    try:
        lines = run_playbook(name, store, since_ts)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    finally:
        store.close()
    for line in lines:
        console.print(line)


@app.command()
def playbooks() -> None:
    table = Table(title="Available playbooks")
    table.add_column("Name", style="cyan")
    table.add_column("Description", overflow="fold")
    for name, description in PLAYBOOKS.items():
        table.add_row(name, str(description))
    console.print(table)


@app.command()
def version() -> None:
    console.print(battdoctor.__version__)


if __name__ == "__main__":
    app()
