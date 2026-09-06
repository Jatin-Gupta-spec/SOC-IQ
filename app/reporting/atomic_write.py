"""
Atomic write helper for SOC-IQ report exporters.

MAX-21B-3 Part 2: closes MAX-21A finding F3 ("Report exports are not
atomic"). Every exporter (`json_exporter.py`, `markdown_exporter.py`,
`html_exporter.py`, `pdf_exporter.py`) previously wrote straight to its
final destination -- a crash, disk-full condition, permission failure,
or interrupted write partway through that write could leave a
truncated/corrupt file, or destroy a previously-valid export that was
about to be overwritten.

This module provides one reusable helper, `atomic_write`, following
the exact pattern `app/settings/repository.py::SettingsRepository.save`
already established for settings persistence: write the complete new
content to a temporary file in the *same directory* as the final
destination, then atomically move it into place with `os.replace`
(atomic on both POSIX and Windows). The destination is therefore
always either the old complete file or the new complete file, never a
partially-written one -- and if anything fails before the replace, the
existing destination (if any) is left completely untouched.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable

#: A callable that receives the path of a freshly created, empty
#: temporary file (already in the destination's directory) and is
#: expected to fully populate it. Any exception it raises aborts the
#: write: the temporary file is removed and the destination is left
#: untouched.
WriteFn = Callable[[Path], None]


def atomic_write(output_path: Path, write_fn: WriteFn) -> None:
    """
    Write to `output_path` atomically.

    `write_fn` is called with the path of a new, empty temporary file
    created in `output_path`'s parent directory. `write_fn` must write
    the complete contents to that temporary path (and is responsible
    for flushing/closing anything it opens). Once `write_fn` returns
    successfully, the temporary file is atomically moved onto
    `output_path` via `os.replace`.

    If `write_fn` raises, or if the final replace itself fails, the
    temporary file is removed (best-effort) and the exception
    propagates -- `output_path` is never touched in that case, so any
    previously-existing valid file at that path survives unchanged.

    The parent directory is created first (mirroring every exporter's
    previous `output_path.parent.mkdir(parents=True, exist_ok=True)`
    behavior) since `tempfile.mkstemp` requires it to already exist.
    """

    directory = output_path.parent

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    fd, tmp_name = tempfile.mkstemp(
        dir=directory,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
    )

    # `write_fn` implementations open the temp path themselves (via
    # `Path.open`, `Path.write_text`, or a third-party API that takes
    # a filename, e.g. reportlab's `Canvas`), so the raw fd from
    # `mkstemp` is only needed to guarantee the file exists atomically
    # before anyone else does anything with the name; close it
    # immediately rather than leaving it open and unused.
    os.close(fd)

    tmp_path = Path(tmp_name)

    try:
        write_fn(tmp_path)
        os.replace(tmp_name, output_path)

    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise
