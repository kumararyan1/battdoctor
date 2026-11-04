from __future__ import annotations

import time

import pytest
import typer

from battdoctor.cli import parse_since


@pytest.mark.parametrize("value", ["nanh", "infh", "-infh", "0h", "", "notatime"])
def test_parse_since_rejects_invalid_values(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        parse_since(value)


def test_parse_since_accepts_hours() -> None:
    since = parse_since("24h")
    assert since < time.time()
    assert time.time() - since >= 23 * 3600
