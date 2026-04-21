"""Unit coverage for app.sanitizers.clean_filename — POR-158 #8."""
import pytest
from app.sanitizers import clean_filename


@pytest.mark.parametrize("raw,expected_no", [
    ("../../../etc/passwd.pdf", [".."]),
    ("/etc/passwd.pdf", ["/"]),
    ("C:\\windows\\evil.pdf", ["\\", "C:"]),
    ("$(rm -rf /).pdf", ["$(", "rm", "-rf"]),
    ("file; DROP TABLE x.pdf", [";"]),
    ("<script>alert(1)</script>.pdf", ["<", ">"]),
    ("file\x00null.pdf", ["\x00"]),
    ("file\r\nheader.pdf", ["\r", "\n"]),
])
def test_clean_filename_strips(raw, expected_no):
    out = clean_filename(raw)
    for tok in expected_no:
        assert tok not in out, f"{tok!r} survived in {out!r}"


def test_clean_filename_preserves_benign():
    assert clean_filename("Q2-2026-Capital-Call.pdf") == "Q2-2026-Capital-Call.pdf"


def test_clean_filename_empty_falls_back():
    assert clean_filename("") == "upload.pdf"
    assert clean_filename(None) == "upload.pdf"


def test_clean_filename_extension_fallback():
    # A filename with no surviving extension gets the .pdf fallback
    assert clean_filename("no_extension").endswith(".pdf")


def test_clean_filename_preserves_known_extensions():
    assert clean_filename("foo.eml") == "foo.eml"
    assert clean_filename("foo.PDF") == "foo.PDF"


def test_clean_filename_length_cap():
    long = "a" * 500 + ".pdf"
    out = clean_filename(long)
    assert len(out) <= 255
    assert out.endswith(".pdf")
