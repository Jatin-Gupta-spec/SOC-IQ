"""
Shared dashboard domain models for SOC-IQ.

This module defines GUI-independent data types that are shared
between the backend service layer (app/services) and the GUI
presentation layer (app/gui). Keeping them here (rather than inside
a GUI widget module) lets backend services describe badge/severity
and timeline information without importing PySide6 or any other
GUI code.

GUI components import these same types so there is a single
canonical definition (identical enum members / dataclass shape)
shared by both layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class BadgeType(Enum):
    """Supported badge variants (semantic status/severity types)."""

    DEFAULT = auto()

    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()
    INFO = auto()

    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass(slots=True)
class TimelineEvent:
    """
    Timeline event model.

    Backward compatible with previous versions while
    supporting richer enterprise event metadata.
    """

    timestamp: str
    title: str
    description: str = ""

    # Enterprise Event Feed additions
    severity: str = "INFO"
    source: str = ""
    icon: str = "●"
