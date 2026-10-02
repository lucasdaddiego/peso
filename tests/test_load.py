"""Parsing the raw snapshots into monthly dicts: month keys, vintage truncation, null skipping,
end-of-period collapse, and the Bluelytics 'Blue'-only filter. Offline."""

from __future__ import annotations

from pipeline import config, load
from tests.conftest import bluelytics_csv, series_json


def test_month_key():
    assert load.month_key("2007-03-15") == "2007-03"
    assert load.month_key("1999-12-01") == "1999-12"


def test_monthly_from_rows_truncates_skips_null_and_takes_eop():
    rows = [
        ["1992-12-01", 5.0],  # before SERIES_START -> dropped
        ["2000-05-03", 10.0],  # kept
        ["2000-05-28", 11.0],  # same month, later day -> overwrites (end of period)
        ["2000-06-01", None],  # null -> skipped
        ["2099-01-01", 99.0],  # after the vintage -> dropped
    ]
    out = load.monthly_from_rows(rows)
    assert out == {"2000-05": 11.0}


def test_load_series_file(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(series_json({"2010-01": 1.5, "2010-02": 1.6}), encoding="utf-8")
    assert load.load_series_file(p) == {"2010-01": 1.5, "2010-02": 1.6}


def test_bluelytics_from_rows_keeps_blue_only_and_truncates():
    import csv
    import io

    text = bluelytics_csv(blue={"2012-01": 7.0, "1990-01": 4.0}, oficial={"2012-01": 5.0})
    rows = list(csv.DictReader(io.StringIO(text)))
    out = load.bluelytics_from_rows(rows)
    assert out == {"2012-01": 7.0}  # Oficial rows ignored; 1990-01 before vintage start dropped


def test_bluelytics_from_rows_takes_month_end_from_a_newest_first_file():
    """The live evolution.csv lists the newest day first. Aug-2019 opened at 45 and closed at 62
    after the PASO devaluation; reading the file in its own order kept the 1st (45), a blue below
    the end-of-month official rate and a negative brecha."""
    import csv
    import io

    text = "day,type,value_buy,value_sell\n2019-08-30,Blue,58.00,62.00\n2019-08-30,Oficial,57.00,60.00\n2019-08-01,Blue,44.00,45.00\n"
    rows = list(csv.DictReader(io.StringIO(text)))
    assert load.bluelytics_from_rows(rows) == {"2019-08": 62.0}
    assert load.bluelytics_from_rows(list(reversed(rows))) == {"2019-08": 62.0}


def test_load_bluelytics_file(tmp_path):
    p = tmp_path / "b.csv"
    p.write_text(bluelytics_csv(blue={"2015-06": 13.0}), encoding="utf-8")
    assert load.load_bluelytics_file(p) == {"2015-06": 13.0}


def test_truncate_window_uses_config_bounds():
    # Sanity: the real bounds frame the kept range.
    assert config.SERIES_START <= "2000-05" <= config.DATA_VINTAGE
