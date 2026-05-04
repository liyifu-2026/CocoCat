from abc import ABC, abstractmethod


class SearchBackend(ABC):
    name: str = ""
    order: int = 100

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> str:
        ...
