from __future__ import annotations

import time
from pathlib import Path

from battdoctor.report.render import render_report
from battdoctor.store import Store


def test_report_escapes_untrusted_title_and_skips_plotly_when_empty(tmp_path: Path) -> None:
    store = Store(tmp_path / "empty.db")
    out = render_report(
        store,
        since=time.time() - 3600,
        out_path=tmp_path / "report.html",
        title='<img src=x onerror=alert(1)>',
    )
    html = out.read_text(encoding="utf-8")

    assert "<img src=x onerror=alert(1)>" not in html
    assert "&lt;img" in html
    assert "Plotly.newPlot" not in html
    store.close()


def test_report_is_owner_only(tmp_path: Path) -> None:
    store = Store(tmp_path / "empty.db")
    out = render_report(store, since=time.time() - 3600, out_path=tmp_path / "report.html")
    assert out.stat().st_mode & 0o777 == 0o600
    store.close()
