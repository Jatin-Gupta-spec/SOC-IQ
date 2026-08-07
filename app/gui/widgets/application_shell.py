"""
Application shell for the SOC-IQ desktop application.

Owns application-lifetime concerns that don't belong inside any
single page, widget, or controller: constructing the
QApplication, applying global chrome (metadata, stylesheet),
installing a process-wide exception hook, owning the
MainWindow instance, and coordinating graceful shutdown of any
resources that need explicit cleanup (HTTP sessions, database
connections, etc.) when the application quits.

This class contains no business logic and does not replace any
existing controller or service — it is intentionally a thin
composition root.
"""

from __future__ import annotations

import logging
import sys
from typing import Callable

from PySide6.QtWidgets import QApplication, QMessageBox

from app.gui.main_window import MainWindow
from app.gui.styles.theme import get_stylesheet

logger = logging.getLogger(__name__)


class ApplicationShell:
    """
    Composition root for the SOC-IQ desktop application.
    """

    def __init__(
        self,
        argv: list[str] | None = None,
    ) -> None:
        """
        Initialize the shell. Does not construct QApplication
        or MainWindow yet — call `run()` (or `bootstrap()`) to
        do that.
        """

        self._argv = argv if argv is not None else sys.argv

        self._app: QApplication | None = None
        self._main_window: MainWindow | None = None

        self._shutdown_hooks: list[Callable[[], None]] = []

        # Guards against installing sys.excepthook twice (e.g. if
        # bootstrap() is ever invoked a second time from a test
        # harness) — see `_install_global_exception_hook`.
        self._exception_hook_installed = False

        # Tracks whether `run()` itself has already been invoked, so
        # the "called again" warning in `run()` reflects a genuine
        # repeat call to `run()` rather than firing just because
        # `ensure_main_window()` was called separately beforehand
        # (e.g. by a caller that needs the window before starting
        # the event loop).
        self._run_invoked = False

    # --------------------------------------------------
    # Lifecycle
    # --------------------------------------------------

    def bootstrap(self) -> QApplication:
        """
        Construct the QApplication and apply global chrome.

        Idempotent and safe to call from a context that has
        already constructed a QApplication (e.g. a test
        harness): Qt only permits a single QApplication per
        process, so an existing instance is reused rather than
        triggering a crash from a second construction attempt.
        """

        if self._app is not None:
            return self._app

        existing = QApplication.instance()

        if isinstance(existing, QApplication):

            self._app = existing

            return self._app

        self._install_global_exception_hook()

        app = QApplication(self._argv)

        app.setApplicationName("SOC-IQ")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("SOC-IQ")

        app.setStyleSheet(get_stylesheet())

        app.aboutToQuit.connect(self._run_shutdown_hooks)

        self._app = app

        return app

    def ensure_main_window(self) -> MainWindow:
        """
        Construct (if not already constructed) and show the
        main window, bootstrapping the QApplication first if
        needed.

        This does not start the Qt event loop — call this when
        a caller needs a `MainWindow` reference (e.g. to wire up
        shutdown hooks or signal connections) before handing
        control to `run()` or calling `application.exec()`
        directly. `run()` itself calls this internally.

        Idempotent: calling this again after the window already
        exists simply re-shows and raises the existing window
        instead of constructing a second one — doing so would
        leave two independent windows, and worse, two
        independent sets of controllers, timers, and signal
        connections, alive at once.
        """

        self.bootstrap()

        if self._main_window is not None:

            self._main_window.show()
            self._main_window.raise_()
            self._main_window.activateWindow()

            return self._main_window

        self._main_window = MainWindow()
        self._main_window.show()

        return self._main_window

    def run(self) -> int:
        """
        Bootstrap (if not already done), construct and show
        the main window, and run the Qt event loop until the
        application exits.

        Calling this more than once will not construct a
        second `MainWindow`: doing so would leave two
        independent windows — and, worse, two independent sets
        of controllers, timers, and signal connections — alive
        at once. The existing window is simply re-shown and
        raised instead.
        """

        app = self.bootstrap()

        if self._run_invoked:

            logger.warning(
                "ApplicationShell.run() called again after the "
                "application was already started; reusing the "
                "existing MainWindow instead of creating another."
            )

        self._run_invoked = True

        self.ensure_main_window()

        return app.exec()

    @property
    def main_window(self) -> MainWindow | None:
        """
        Return the active MainWindow instance, or None if the
        shell has not been run yet.
        """

        return self._main_window

    @property
    def application(self) -> QApplication | None:
        """
        Return the active QApplication instance, or None if
        the shell has not been bootstrapped yet.
        """

        return self._app

    # --------------------------------------------------
    # Shutdown
    # --------------------------------------------------

    def register_shutdown_hook(
        self,
        hook: Callable[[], None],
    ) -> None:
        """
        Register a callable to run when the application is
        about to quit.

        Intended for releasing resources the shell itself has
        no visibility into — HTTP client sessions, open
        database connections, and similar — so that pages and
        services which own such resources can register their
        own cleanup here instead of the shell needing to know
        about them ahead of time.

        Hooks run in registration order. A failing hook is
        logged and does not prevent the remaining hooks from
        running. Registering the exact same callable twice
        (e.g. a page's `cleanup` method registered again after
        a re-navigation) is a no-op rather than a duplicate
        entry — otherwise shutdown would run cleanup on an
        already-cleaned-up resource, or run it twice.
        """

        if hook in self._shutdown_hooks:

            logger.debug(
                "Shutdown hook '%s' is already registered; "
                "skipping duplicate registration.",
                getattr(hook, "__qualname__", repr(hook)),
            )

            return

        self._shutdown_hooks.append(hook)

    def _run_shutdown_hooks(self) -> None:
        """
        Execute all registered shutdown hooks, isolating
        failures so that one hook's exception cannot prevent
        the others from running.

        The hook list is swapped out for an empty one before
        running so hooks are cleared even if one of them
        raises, and so nothing can cause the same hooks to run
        twice.
        """

        hooks, self._shutdown_hooks = self._shutdown_hooks, []

        for hook in hooks:

            try:

                hook()

            except Exception:

                logger.exception(
                    "Shutdown hook '%s' failed.",
                    getattr(
                        hook,
                        "__qualname__",
                        repr(hook),
                    ),
                )

    # --------------------------------------------------
    # Error handling
    # --------------------------------------------------

    def _install_global_exception_hook(self) -> None:
        """
        Install a process-wide exception hook so an unhandled
        exception raised inside a Qt slot or event-loop
        callback is logged, with a full traceback, and
        surfaced to the user via a non-crashing dialog instead
        of being lost or aborting the process outright.

        Guarded to install only once per process: a repeated
        install is harmless today (the second one simply wins),
        but guarding now protects against a silent
        double-install if this method is ever extended to chain
        onto a previously-installed hook — without the guard,
        a second install would wrap itself and double-report
        every crash.
        """

        if self._exception_hook_installed:
            return

        def handle_exception(exc_type, exc_value, exc_traceback):

            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return

            logger.critical(
                "Unhandled exception.",
                exc_info=(exc_type, exc_value, exc_traceback),
            )

            QMessageBox.critical(
                None,
                "SOC-IQ — Unexpected Error",
                "An unexpected error occurred and has been logged.\n\n"
                f"{exc_value}",
            )

        sys.excepthook = handle_exception

        self._exception_hook_installed = True