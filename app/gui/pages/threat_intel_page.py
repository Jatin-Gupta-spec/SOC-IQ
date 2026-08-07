"""
Threat Intelligence Page for the SOC-IQ desktop application.

Provides indicator reputation lookups, VirusTotal enrichment searches,
and threat actor intelligence tracking.
"""

from __future__ import annotations

import logging
import re

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.buttons.animated_button import AnimatedButton
from app.gui.components.cards.glass_card import GlassCard
from app.gui.components.cards.metric_card import MetricCard
from app.gui.components.cards.modern_card import ModernCard
from app.gui.components.layout.component_section import ComponentSection
from app.gui.design.tokens import Spacing
from app.gui.events.application_events import events
from app.gui.widgets.page_container import PageContainer
from app.threat_intel.virustotal import VirusTotalClient

logger = logging.getLogger(__name__)

# Matches the same shape VirusTotalClient itself validates
# against. Duplicated locally (rather than importing the
# module-private `_SHA256_PATTERN`) because reaching into
# another module's underscore-prefixed implementation detail
# is itself a maintainability smell.
_SHA256_PATTERN = re.compile(r"^[A-Fa-f0-9]{64}$")


class _VirusTotalLookupWorker(QObject):
    """
    Executes a single VirusTotal SHA256 lookup on a
    background thread so a network call never blocks the
    GUI event loop.
    """

    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, client: VirusTotalClient, sha256: str) -> None:
        super().__init__()

        self._client = client
        self._sha256 = sha256

    def run(self) -> None:

        try:

            result = self._client.lookup_sha256(self._sha256)

        except Exception as error:

            logger.exception(
                "VirusTotal lookup failed for '%s'.",
                self._sha256,
            )

            self.failed.emit(str(error))

            return

        self.finished.emit(result)


class ThreatIntelPage(QWidget):
    """
    Threat Intelligence Page.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._vt_client: VirusTotalClient | None = None
        self._init_vt_client()

        self._thread: QThread | None = None
        self._worker: _VirusTotalLookupWorker | None = None

        # A client that was swapped out by `_on_settings_changed`
        # while a lookup was still in flight on it. Closed once that
        # lookup finishes rather than immediately -- see
        # `_on_settings_changed` for why.
        self._pending_client_close: VirusTotalClient | None = None

        # Set once this page is torn down, so any callback that was
        # already queued from a background thread (lookup finished/
        # failed, thread cleanup) becomes a safe no-op instead of
        # touching widgets that may no longer exist.
        self._is_destroyed = False

        self._container = PageContainer(
            title="Threat Intelligence Center",
            description=(
                "Query global threat intelligence networks, VirusTotal reputation "
                "databases, and indicator threat classifications."
            ),
        )

        self._search_input = QLineEdit()
        self._search_btn = AnimatedButton("Query Indicator")

        self._result_card = ModernCard()
        self._quota_card = GlassCard()

        self._metric_queries = MetricCard(
            title="Queries Today",
            value="14",
            subtitle="VirusTotal API",
            footer="Free Tier Quota",
        )
        self._metric_malicious = MetricCard(
            title="Malicious Hits",
            value="8",
            subtitle="Flagged IOCs",
            footer="High Confidence",
        )
        self._metric_quota = MetricCard(
            title="Rate Limit",
            value="4 / min",
            subtitle="API Threshold",
            footer="Operational",
        )

        self._build_ui()
        self._connect_signals()

    def _init_vt_client(self) -> None:
        """
        (Re)build the VirusTotal client from current settings.
        """

        try:

            self._vt_client = VirusTotalClient()

        except Exception:

            logger.warning(
                "VirusTotal client unavailable — no valid "
                "API key is configured."
            )

            self._vt_client = None

    def _build_ui(self) -> None:
        """
        Build the Threat Intel page user interface.
        """
        layout = self._container.content_layout()

        # Metrics Row
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(Spacing.LG)
        metrics_layout.addWidget(self._metric_queries)
        metrics_layout.addWidget(self._metric_malicious)
        metrics_layout.addWidget(self._metric_quota)
        layout.addLayout(metrics_layout)

        # Search Bar Section
        search_section = ComponentSection(
            title="Indicator Reputation Lookup",
            description="Enter a file hash (SHA256) to query live VirusTotal reputation.",
        )

        search_box = QHBoxLayout()
        search_box.setSpacing(Spacing.MD)

        self._search_input.setPlaceholderText("e.g. a SHA256 file hash...")
        search_box.addWidget(self._search_input, 4)
        search_box.addWidget(self._search_btn, 1)

        search_section.add_layout(search_box)
        layout.addWidget(search_section)

        # Result View
        self._build_result_card()
        layout.addWidget(self._result_card)

        layout.addStretch()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._container)

    def _build_result_card(self) -> None:
        """
        Construct initial result container.
        """
        res_layout = QVBoxLayout()
        res_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        res_layout.setSpacing(Spacing.MD)

        palette = self._result_card.theme.palette
        fonts = self._result_card.theme.fonts

        self._res_title = QLabel("Query Results")
        self._res_title.setFont(fonts.title())
        self._res_title.setStyleSheet(f"color: {palette.text_primary}; font-weight: 600;")

        self._res_detail = QLabel("Enter a SHA256 hash above and click 'Query Indicator' to retrieve live VirusTotal threat telemetry.")
        self._res_detail.setFont(fonts.body())
        self._res_detail.setStyleSheet(f"color: {palette.text_secondary};")
        self._res_detail.setWordWrap(True)

        res_layout.addWidget(self._res_title)
        res_layout.addWidget(self._res_detail)

        self._result_card.add_layout(res_layout)

    def _connect_signals(self) -> None:
        """
        Connect search signals.
        """
        self._search_btn.clicked.connect(self._run_query)
        self._search_input.returnPressed.connect(self._run_query)

        # Without this, a client built with a missing/old
        # key at page-construction time would keep failing
        # (or keep using a stale key) for the rest of the
        # session, even after the analyst fixes it on the
        # Settings page.
        events.settings_changed.connect(self._on_settings_changed)

    def cleanup(self) -> None:
        """
        Release everything this page owns that outlives normal
        widget teardown: the `events.settings_changed` subscription
        and the VirusTotal client's HTTP session.

        Previously the client built in `_init_vt_client` at
        construction time was never closed unless a settings change
        happened to replace it first -- a plain resource leak on
        normal page/app teardown. Safe to call more than once; the
        container/window that owns this page (or the app shutdown
        hook) should call it when the page is removed or the app is
        shutting down.
        """

        self._is_destroyed = True

        try:
            events.settings_changed.disconnect(self._on_settings_changed)
        except (RuntimeError, TypeError):
            # Already disconnected, or the signal/slot is gone.
            pass

        if self._vt_client is not None:
            self._vt_client.close()
            self._vt_client = None

        if self._pending_client_close is not None:
            self._pending_client_close.close()
            self._pending_client_close = None

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Ensure cleanup runs if this page is ever used as (or
        inside) a top-level window that receives a close event.
        """

        self.cleanup()
        super().closeEvent(event)

    def _on_settings_changed(self, changed: dict) -> None:
        """
        React to credential changes made on the Settings page.
        """

        if "virustotal_api_key" not in changed:
            return

        old_client = self._vt_client
        self._init_vt_client()

        if old_client is None:
            return

        if self._thread is not None:
            # A lookup on `old_client` may currently be running on
            # the background worker thread. Closing its HTTP session
            # out from under that in-flight request could raise
            # mid-call on another thread. Defer the close until that
            # worker finishes -- `_cleanup_thread` closes it then.
            self._pending_client_close = old_client
        else:
            old_client.close()

    def _run_query(self) -> None:
        """
        Execute indicator lookup.
        """

        if self._thread is not None:
            # A lookup is already in flight. The search controls are
            # disabled while one runs, but guard here too in case a
            # re-entrant trigger (e.g. Enter and click firing in the
            # same event-loop tick) slips through.
            return

        query = self._search_input.text().strip()

        if not query:
            return

        if self._vt_client is None:
            self._res_title.setText("VirusTotal Not Configured")
            self._res_detail.setText(
                "No VirusTotal API key is configured. Add one on "
                "the Settings page to enable live reputation lookups."
            )
            return

        if not _SHA256_PATTERN.fullmatch(query):
            # Previously ANY input — including garbage — produced
            # a hardcoded, fabricated "42 / 70 vendors flagged
            # malicious" result. Showing invented threat
            # intelligence in a SOC tool is actively dangerous:
            # an analyst could act on it. Only SHA256 lookups are
            # wired to a real backend today (VirusTotalClient
            # only exposes `lookup_sha256`), so anything else is
            # now reported honestly as unsupported instead of faked.
            self._res_title.setText("Unsupported Indicator Type")
            self._res_detail.setText(
                "Live lookups currently support SHA256 file hashes "
                "only. IP address, domain, and URL reputation "
                "lookups are not yet implemented."
            )
            return

        self._search_btn.setEnabled(False)
        self._search_input.setEnabled(False)

        self._res_title.setText(f"Threat Intelligence Report: {query}")
        self._res_detail.setText("Querying VirusTotal...")

        # Deliberately not parented to `self`: if this page is torn
        # down while a lookup is still running, Qt would otherwise
        # try to destroy a live QThread as part of destroying its
        # parent, which is unsafe/warns loudly. Leaving it unparented
        # lets the thread finish and clean itself up via `deleteLater`
        # in `_cleanup_thread` independent of this page's lifetime;
        # the `_is_destroyed` guard keeps its completion callbacks
        # from touching widgets that may already be gone.
        self._thread = QThread()
        self._worker = _VirusTotalLookupWorker(self._vt_client, query)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_lookup_finished)
        self._worker.failed.connect(self._on_lookup_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)

        self._thread.start()

    def _cleanup_thread(self) -> None:
        """
        Release the worker/thread, close any client whose closure
        was deferred during this lookup, and restore the search UI.
        """

        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

        if self._pending_client_close is not None:
            self._pending_client_close.close()
            self._pending_client_close = None

        if self._is_destroyed:
            # Page was torn down while this lookup was running --
            # nothing left to re-enable.
            return

        self._search_btn.setEnabled(True)
        self._search_input.setEnabled(True)

    def _on_lookup_finished(self, result: dict) -> None:
        """
        Render a successful VirusTotal lookup.
        """

        if self._is_destroyed:
            return

        if not result.get("found", False):
            self._res_detail.setText(
                f"Indicator: {result['sha256']}\n"
                "Status: Not found in VirusTotal."
            )
            return

        self._res_detail.setText(
            f"Indicator: {result['sha256']}\n"
            f"Malicious: {result['malicious']}\n"
            f"Suspicious: {result['suspicious']}\n"
            f"Harmless: {result['harmless']}\n"
            f"Undetected: {result['undetected']}\n"
            f"Reputation: {result['reputation']}\n"
            f"Last Analysis: {result['last_analysis_date']}\n"
            f"Permalink: {result['permalink']}"
        )

    def _on_lookup_failed(self, message: str) -> None:
        """
        Render a failed VirusTotal lookup.
        """

        if self._is_destroyed:
            return

        self._res_title.setText("Query Failed")
        self._res_detail.setText(message)