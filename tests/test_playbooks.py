from __future__ import annotations

from datetime import UTC

from battdoctor.analyze.playbooks import _parse_install_date


def test_parse_install_date_accepts_iso_zulu() -> None:
    parsed = _parse_install_date("2026-04-05T19:05:42Z")
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 4
    assert parsed.astimezone(UTC).day == 5
    assert parsed.tzinfo is not None
