"""Sandbox data class."""
from __future__ import annotations


class Sandbox:
    """Represents a sandbox instance."""

    def __init__(self, id: str, template: str, permissions: dict):
        self.id = id
        self.template = template
        self.permissions = permissions
        self.created_at = None
