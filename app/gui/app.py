"""
GUI application entry point for SOC-IQ.
"""

from __future__ import annotations

from app.gui.widgets.application_shell import ApplicationShell


def main() -> int:
    """
    Create and start the GUI application.

    All QApplication/MainWindow lifecycle concerns — construction,
    global chrome (metadata, stylesheet), the process-wide exception
    hook, existing-QApplication reuse, and shutdown cleanup — are
    owned by `ApplicationShell`. This function previously duplicated
    that entire bootstrap sequence independently (a second,
    hand-written QApplication-construction and exception-hook
    implementation living side by side with ApplicationShell's),
    which meant the two could silently drift out of sync, and it
    left ApplicationShell's own shutdown-hook registration completely
    unused. Delegating here keeps a single implementation of each of
    those concerns.
    """

    shell = ApplicationShell()

    window = shell.ensure_main_window()

    # Backstop for MainWindow.closeEvent()'s page cleanup (VirusTotal
    # HTTP session, event_bus subscriptions). closeEvent only fires
    # when the window itself is closed (e.g. the title-bar X); if the
    # application is ever quit a different way -- app.quit() /
    # QCoreApplication.exit() without closing the window first --
    # that cleanup would otherwise never run. Both page cleanup()
    # methods are explicitly documented as safe to call more than
    # once, so this is a harmless no-op on the normal close path.
    # Routed through ApplicationShell's shutdown-hook mechanism
    # (rather than a raw `app.aboutToQuit.connect(...)`) so a
    # failure in one page's cleanup is logged and isolated instead
    # of silently preventing the other page's cleanup from running.
    shell.register_shutdown_hook(window.threat_page.cleanup)
    shell.register_shutdown_hook(window.ioc_page.cleanup)

    return shell.application.exec()


if __name__ == "__main__":
    raise SystemExit(main())