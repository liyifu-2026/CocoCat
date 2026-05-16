"""Channel factory — maps channel_type strings to Channel classes."""
from __future__ import annotations

_CHANNEL_MAP: dict[str, type] = {}


def register_channel(channel_type: str, channel_cls: type):
    """Register a Channel class for a given channel_type string."""
    _CHANNEL_MAP[channel_type] = channel_cls


def create_channel(channel_type: str, **kwargs):
    """Create a Channel instance by channel_type string."""
    cls = _CHANNEL_MAP.get(channel_type)
    if cls is None:
        raise ValueError(f"Unknown channel type: {channel_type!r}. Available: {list(_CHANNEL_MAP.keys())}")
    return cls(**kwargs)
