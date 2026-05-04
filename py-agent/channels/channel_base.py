"""ReconnectingChannel mixin for auto-reconnect with exponential backoff."""
import time
import logging

logger = logging.getLogger("cococat.channel")


class ReconnectingChannel:
    """Mixin that adds exponential backoff reconnection to Channel classes."""

    MAX_RETRIES = 5
    BASE_DELAY = 2
    MAX_DELAY = 60

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._retry_count = 0
        self._should_stop = False

    def _get_delay(self) -> int:
        delay = min(self.BASE_DELAY * (2 ** self._retry_count), self.MAX_DELAY)
        return delay

    def _run_with_reconnect(self, target_fn, *args, **kwargs):
        while self._retry_count < self.MAX_RETRIES and not self._should_stop:
            try:
                self._connected = True
                target_fn(*args, **kwargs)
            except Exception as e:
                self._connected = False
                self._retry_count += 1
                delay = self._get_delay()
                logger.warning(f"Channel disconnected (attempt {self._retry_count}/{self.MAX_RETRIES}), reconnecting in {delay}s: {e}")
                time.sleep(delay)
        if self._retry_count >= self.MAX_RETRIES:
            logger.error("Channel stopped: max retries reached")
            self._connected = False

    def stop(self):
        self._should_stop = True
        self._connected = False
