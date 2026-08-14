"""
Application theme for the SOC-IQ desktop GUI.

This module provides the global Qt stylesheet used by the application.
"""

from __future__ import annotations

from app.gui.design.theme.stylesheet import DEFAULT_STYLESHEET


def get_stylesheet() -> str:
    """
    Return the application's global stylesheet.

    Delegates to the token-driven stylesheet infrastructure
    (`app.gui.design.theme.stylesheet.Stylesheet`) so the
    Colors/Spacing/Typography/Radius design tokens are the single
    source of truth for the application's global QSS, rather than
    the hardcoded hex values this module used to return directly.

    Kept as a thin wrapper — rather than updating ApplicationShell
    to import `Stylesheet`/`DEFAULT_STYLESHEET` directly — so the
    existing `app.gui.styles.theme.get_stylesheet` import path used
    by `ApplicationShell.bootstrap()` does not need to change. This
    was the smaller of the two options the design-token system
    already made available.
    """

    return DEFAULT_STYLESHEET.build()