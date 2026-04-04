from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from backend.models.transaction import Transaction


class BaseParser(ABC):
    """Interface comum para parsers de documentos financeiros."""

    @abstractmethod
    def parse(self, filepath: Path) -> list[Transaction]:
        raise NotImplementedError
