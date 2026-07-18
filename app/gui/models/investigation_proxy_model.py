"""
Proxy model for filtering and sorting investigations.
"""

from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt


class InvestigationProxyModel(QSortFilterProxyModel):
    """
    Proxy model that enables filtering and sorting
    of investigation data.
    """

    def __init__(self) -> None:
        super().__init__()

        self.setFilterCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )

        self.setFilterKeyColumn(-1)

        self.setDynamicSortFilter(True)