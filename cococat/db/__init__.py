"""Database package."""
from cococat.db.database import Database, new_uuid
from cococat.db.scene_store import SceneStore
from cococat.db.message_store import MessageStore

__all__ = [
    "Database", "new_uuid",
    "SceneStore", "MessageStore",
]
