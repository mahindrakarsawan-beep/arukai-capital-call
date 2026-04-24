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


def test_clean_filename_length_cap_preserves_full_extension():
    """255-char cap must leave the full ext intact (root truncates, not ext)."""
    out = clean_filename("a" * 500 + ".pdf")
    assert out == "a" * 251 + ".pdf"
    assert len(out) == 255


def test_clean_filename_overlong_extension_falls_back():
    """An extension longer than 8 chars is rejected → .pdf fallback."""
    assert clean_filename("doc.verylongextension").endswith(".pdf")


def test_clean_filename_path_separators_always_stripped():
    """Belt-and-braces: no platform-dependent basename behavior for separators."""
    assert clean_filename("a/b/c.pdf") == "c.pdf"
    assert clean_filename("a\\b\\c.pdf") == "c.pdf"
    out = clean_filename("foo/../bar.pdf")
    assert out.endswith(".pdf")
    assert "/" not in out and ".." not in out


def test_clean_filename_preserves_ampersand():
    """`&` is NOT in the forbidden set — legit filenames keep it."""
    assert clean_filename("R&D report.pdf") == "R&D_report.pdf"
    assert clean_filename("Smith & Co.pdf") == "Smith_&_Co.pdf"


@pytest.mark.parametrize("raw,expected", [
    ("foo.PDF", "foo.PDF"),
    ("foo.EML", "foo.EML"),
    ("foo.PnG", "foo.PnG"),
])
def test_clean_filename_preserves_extension_case(raw, expected):
    """Extension case is preserved (regex is [A-Za-z0-9], not [a-z0-9])."""
    assert clean_filename(raw) == expected
