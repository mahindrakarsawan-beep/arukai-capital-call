"""Input sanitizers for POR-158 #8 — defensive scrubbing of user-supplied
strings at the API boundary. Keep this module small, dependency-free, and
string-in/string-out.

The single public function is `clean_filename(raw)`. It:
  - strips path components (POSIX + Windows) so only the basename remains
  - removes null bytes and ASCII control chars (including CR/LF — header
    smuggling surface on Content-Disposition)
  - removes shell/SQL/HTML metacharacters that have no place in a PDF name
  - collapses whitespace, trims, truncates to 255 chars
  - preserves the canonical extension if present (.pdf, .eml, .png — anything
    matching a short ASCII extension); falls back to '.pdf' if the cleaned
    name has no dot

Does NOT HTML-escape: rendering-layer concern. Storage stays truthful.
"""
from __future__ import annotations

import os
import re

# Characters that have no legitimate place in an uploaded filename. We drop
# rather than escape because we do not want to reconstruct the original
# intent — a hostile input is thrown away, a benign one is unaffected.
_FORBIDDEN = re.compile(r"[\x00-\x1f<>:\"|?*$`;()&{}\[\]\\]")

_MAX_LEN = 255
_DEFAULT_EXT = ".pdf"


def clean_filename(raw: str | None) -> str:
    """Return a safe, storable filename derived from `raw`.

    Guarantees on the output:
      - non-empty string (caller never has to guard)
      - contains no path separators, control chars, or shell/HTML metachars
      - does not contain '..' (traversal segments collapsed)
      - length <= 255 chars
      - ends with a dot-extension (falls back to '.pdf' if the input had none)
    """
    if not raw:
        return "upload" + _DEFAULT_EXT

    # Strip path components — basename handles POSIX, ntpath handles backslash
    import ntpath
    name = ntpath.basename(os.path.basename(raw))

    # Remove forbidden bytes
    name = _FORBIDDEN.sub("", name)

    # Kill traversal fragments that survived basename (e.g. "...")
    name = name.replace("..", "")

    # Collapse whitespace to underscores — prevents two-word injection
    # sequences like "DROP TABLE" from surviving after the separator char
    # (";") was stripped. Benign filenames rarely contain spaces; if they
    # do, an underscore substitution is still readable and storable.
    name = re.sub(r"\s+", "_", name).strip("_")

    if not name:
        return "upload" + _DEFAULT_EXT

    # Ensure an extension survives
    root, ext = os.path.splitext(name)
    if not ext or not re.fullmatch(r"\.[A-Za-z0-9]{1,8}", ext):
        name = (root or "upload") + _DEFAULT_EXT

    # Enforce length cap last so the extension stays intact
    if len(name) > _MAX_LEN:
        root, ext = os.path.splitext(name)
        keep = _MAX_LEN - len(ext)
        name = root[:keep] + ext

    return name
