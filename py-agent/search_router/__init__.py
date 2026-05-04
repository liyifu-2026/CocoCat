"""Search Router — multi-backend with auto-fallback, no heartbeat."""
import time
from .base import SearchBackend

_DEGRADE_THRESHOLD = 3
_RETRY_INTERVAL = 300


class SearchRouter:
    def __init__(self, backends: list[SearchBackend] | None = None):
        self._backends = backends or _default_backends()
        self._failures: dict[str, int] = {}
        self._degraded_until: dict[str, float] = {}

    def search(self, query: str, max_results: int = 5) -> str:
        now = time.time()
        for name in list(self._degraded_until.keys()):
            if now >= self._degraded_until[name]:
                del self._degraded_until[name]
                self._failures[name] = 0

        sorted_backends = sorted(
            self._backends,
            key=lambda b: (self._failures.get(b.name, 0), b.order),
        )

        last_error = ""
        for backend in sorted_backends:
            if backend.name in self._degraded_until:
                continue
            try:
                result = backend.search(query, max_results)
                self._failures[backend.name] = 0
                return result
            except Exception as e:
                last_error = f"{backend.name}: {e}"
                count = self._failures.get(backend.name, 0) + 1
                self._failures[backend.name] = count
                if count >= _DEGRADE_THRESHOLD:
                    self._degraded_until[backend.name] = time.time() + _RETRY_INTERVAL
                continue

        return f"Search failed: all backends unavailable ({last_error})"


def _default_backends() -> list[SearchBackend]:
    from .backends.baidu import BaiduSearch
    from .backends.bing import BingSearch
    from .backends.duckduckgo import DuckDuckGoSearch
    return [
        BaiduSearch(),
        BingSearch(),
        DuckDuckGoSearch(),
    ]


_default_router = None


def get_router() -> SearchRouter:
    global _default_router
    if _default_router is None:
        _default_router = SearchRouter()
    return _default_router
