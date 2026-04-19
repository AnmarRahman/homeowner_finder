from __future__ import annotations

from abc import ABC, abstractmethod

from scraper.models import PropertyRecord


class PropertySource(ABC):
    key: str
    label: str

    @abstractmethod
    def fetch(self, limit: int, city: str | None = None) -> list[PropertyRecord]:
        raise NotImplementedError
