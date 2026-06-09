import pytest

from keysight_scope.errors import IDNParseError
from keysight_scope.idn import detect_series, parse_idn


def test_parse_keysight_idn():
    idn = parse_idn("KEYSIGHT TECHNOLOGIES,DSOX4024A,MY12345678,02.50\n")

    assert idn.vendor == "KEYSIGHT TECHNOLOGIES"
    assert idn.model == "DSOX4024A"
    assert idn.serial == "MY12345678"
    assert idn.firmware == "02.50"
    assert idn.series == "4000X"


@pytest.mark.parametrize(
    ("model", "series"),
    [
        ("DSOX2004A", "2000X"),
        ("DSOX3024A", "3000X"),
        ("DSOX4024A", "4000X"),
        ("DSOX4034A", "4000X"),
        ("MSOX3024A", "3000X"),
    ],
)
def test_detect_series(model, series):
    assert detect_series(model) == series


def test_detect_series_returns_none_for_unknown_model():
    assert detect_series("DSO-X-UNKNOWN") is None


def test_parse_idn_rejects_incomplete_response():
    with pytest.raises(IDNParseError):
        parse_idn("KEYSIGHT,DSOX4024A")
