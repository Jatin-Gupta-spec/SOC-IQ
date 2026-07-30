"""
SOC-IQ Dashboard Component

Raycast Quick Command Launcher Widget

Fast keyboard and mouse action palette enabling instant navigation across modules.
"""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.buttons.animated_button import AnimatedButton
from app.gui.components.cards.modern_card import ModernCard
from app.gui.design.tokens import Radius, Spacing


class CommandLauncherWidget(ModernCard):
    """
    Raycast-style action launcher card.
    """

    action_selected = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._title = QLabel("Analyst Command Palette")
        self._subtitle = QLabel("Quick launch shortcuts and workflow actions.")

        self._actions = [
            ("⚡ Analyze New Malware Report", 1, "Ctrl+N"),
            ("🔍 Search Investigation History", 5, "Ctrl+H"),
            ("🌐 Threat Intelligence Lookup", 3, "Ctrl+T"),
            ("⚙️ Configure System Settings", 6, "Ctrl+S"),
        ]

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Construct Command Launcher layout.
        """
        palette = self.theme.palette
        fonts = self.theme.fonts

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )
        main_layout.setSpacing(Spacing.MD)

        self._title.setFont(fonts.title())
        self._title.setStyleSheet(f"color: {palette.text_primary}; font-weight: 700;")

        self._subtitle.setFont(fonts.body())
        self._subtitle.setStyleSheet(f"color: {palette.text_secondary};")

        main_layout.addWidget(self._title)
        main_layout.addWidget(self._subtitle)

        # Action Buttons Grid
        for label, page_idx, shortcut in self._actions:
            btn = AnimatedButton(label)
            btn.clicked.connect(lambda checked=False, p=page_idx: self.action_selected.emit(p))

            row = QHBoxLayout()
            row.setSpacing(Spacing.SM)

            badge_shortcut = QLabel(shortcut)
            badge_shortcut.setFont(fonts.caption())
            badge_shortcut.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {palette.surface_secondary};
                    color: {palette.text_muted};
                    border: 1px solid {palette.border_subtle};
                    border-radius: {Radius.BADGE}px;
                    padding: 2px 8px;
                    font-weight: 600;
                }}
                """
            )

            row.addWidget(btn, 3)
            row.addWidget(badge_shortcut, 1)

            main_layout.addLayout(row)

        self.add_layout(main_layout)
