"""
SOC-IQ Dashboard Component

MITRE ATT&CK Matrix & Detection Coverage Widget

Displays organizational MITRE ATT&CK framework tactical coverage, SIEM detection rules,
and framework alignment status.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.cards.modern_card import ModernCard
from app.gui.design.tokens import Spacing


class MitreCoverageWidget(ModernCard):
    """
    MITRE ATT&CK Tactics & Detection Coverage Panel.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._title = QLabel("MITRE ATT&CK Framework & Detection Matrix")
        self._subtitle = QLabel("Active SIEM detection rules mapped to ATT&CK tactics.")

        self._tactics = [
            ("Initial Access (TA0001)", 84),
            ("Execution (TA0002)", 92),
            ("Persistence (TA0003)", 78),
            ("Defense Evasion (TA0005)", 88),
            ("Exfiltration (TA0010)", 95),
        ]

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Construct MITRE matrix UI.
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

        # Tactics Progress Bars
        for name, pct in self._tactics:
            row_layout = QVBoxLayout()
            row_layout.setSpacing(Spacing.XS)

            lbl_row = QHBoxLayout()
            lbl_name = QLabel(name)
            lbl_name.setFont(fonts.caption())
            lbl_name.setStyleSheet(f"color: {palette.text_primary}; font-weight: 600;")

            lbl_pct = QLabel(f"{pct}% Coverage")
            lbl_pct.setFont(fonts.caption())
            lbl_pct.setStyleSheet(f"color: {palette.accent}; font-weight: 700;")

            lbl_row.addWidget(lbl_name)
            lbl_row.addStretch()
            lbl_row.addWidget(lbl_pct)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(pct)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setStyleSheet(
                f"""
                QProgressBar {{
                    background-color: {palette.surface_secondary};
                    border: none;
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background-color: {palette.accent};
                    border-radius: 3px;
                }}
                """
            )

            row_layout.addLayout(lbl_row)
            row_layout.addWidget(bar)

            main_layout.addLayout(row_layout)

        self.add_layout(main_layout)
