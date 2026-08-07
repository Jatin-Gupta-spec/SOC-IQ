"""
SOC-IQ Design System

File Dropzone Widget

Interactive drag-and-drop file upload target with visual feedback state.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.cards.modern_card import ModernCard
from app.gui.design.tokens import Radius, Spacing


class FileDropzoneWidget(ModernCard):
    """
    Drag and drop file upload surface.
    """

    file_dropped = Signal(str)
    clicked = Signal()

    # Kept as a single source of truth so the accepted
    # extensions can never drift from what the label
    # above promises the user.
    SUPPORTED_EXTENSIONS = (".txt", ".log", ".json")

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setAcceptDrops(True)

        self._icon_label = QLabel("📂")
        self._primary_label = QLabel("Drag & Drop Malware Report File Here")
        self._secondary_label = QLabel("Supports .txt, .log, .json report files or click to browse")
        self._selected_file_label = QLabel("")

        self._is_dragging = False

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Construct Dropzone UI layout.
        """
        palette = self.theme.palette
        fonts = self.theme.fonts

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(
            Spacing.XL,
            Spacing.XL,
            Spacing.XL,
            Spacing.XL,
        )
        main_layout.setSpacing(Spacing.MD)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon_label.setFont(fonts.display())
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet("font-size: 42px; background: transparent;")

        self._primary_label.setFont(fonts.title())
        self._primary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._primary_label.setStyleSheet(
            f"color: {palette.text_primary}; font-weight: 700; background: transparent;"
        )

        self._secondary_label.setFont(fonts.body())
        self._secondary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._secondary_label.setStyleSheet(
            f"color: {palette.text_secondary}; background: transparent;"
        )

        self._selected_file_label.setFont(fonts.caption())
        self._selected_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._selected_file_label.setStyleSheet(
            f"color: {palette.accent}; font-weight: 600; background: transparent;"
        )

        main_layout.addWidget(self._icon_label)
        main_layout.addWidget(self._primary_label)
        main_layout.addWidget(self._secondary_label)
        main_layout.addWidget(self._selected_file_label)

        self.add_layout(main_layout)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_file_path(self, path_str: str) -> None:
        """
        Display selected file name.
        """
        if not path_str:
            self._selected_file_label.setText("")
            self._primary_label.setText("Drag & Drop Malware Report File Here")
            return

        file_name = Path(path_str).name
        self._primary_label.setText(f"Selected: {file_name}")
        self._selected_file_label.setText(path_str)

    def _is_supported_url(self, urls) -> bool:
        """
        Determine whether the drag payload contains at
        least one local file matching a supported
        extension.
        """
        if not urls:
            return False

        local_path = urls[0].toLocalFile()

        if not local_path:
            return False

        return Path(local_path).suffix.lower() in self.SUPPORTED_EXTENSIONS

    # --------------------------------------------------
    # Drag & Drop Events
    # --------------------------------------------------

    def mousePressEvent(self, event) -> None:
        """
        Handle click trigger.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """
        Validate file drag entering boundary.
        """
        # Previously this accepted any drag containing a
        # URL, showing the "accepted" drag style for any
        # file type. That's misleading: the widget label
        # explicitly promises .txt/.log/.json support, so
        # dragging e.g. a .zip in showed a false "this will
        # work" affordance right up until the drop was
        # silently accepted anyway.
        if self._is_supported_url(event.mimeData().urls()):
            event.acceptProposedAction()
            self._is_dragging = True
            self._apply_drag_style()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """
        Handle drag leaving boundary.
        """
        self._is_dragging = False
        self._apply_default_style()
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        """
        Extract dropped file path.
        """
        self._is_dragging = False
        self._apply_default_style()

        urls = event.mimeData().urls()

        if not self._is_supported_url(urls):
            event.ignore()
            return

        file_path = urls[0].toLocalFile()
        self.set_file_path(file_path)
        self.file_dropped.emit(file_path)
        event.acceptProposedAction()

    def _apply_drag_style(self) -> None:
        palette = self.theme.palette
        self._frame.setStyleSheet(
            f"""
            QFrame#modernCard {{
                background-color: {palette.surface_secondary};
                border: 2px dashed {palette.accent};
                border-radius: {Radius.CARD}px;
            }}
            """
        )

    def _apply_default_style(self) -> None:
        palette = self.theme.palette
        self._frame.setStyleSheet(
            f"""
            QFrame#modernCard {{
                background-color: {palette.surface};
                border: 1px solid {palette.border_subtle};
                border-radius: {Radius.CARD}px;
            }}
            """
        )