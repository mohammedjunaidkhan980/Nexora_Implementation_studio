import os
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

MEMORY_MESSAGE_LIMIT = 10
MEMORY_CONTENT_LIMIT = 16000
_client: MongoClient[Any] | None = None
_client_lock = Lock()
_index_ready = False


def _memory_collection() -> Collection[dict[str, Any]]:
    global _client, _index_ready

    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI environment variable must be set")

    with _client_lock:
        if _client is None:
            _client = MongoClient(uri)
        database_name = os.getenv("MONGODB_DATABASE", "ai_implementation_studio")
        collection = _client[database_name]["chat_memory"]
        if not _index_ready:
            try:
                collection.create_index(
                    [("organization_id", ASCENDING), ("user_id", ASCENDING)],
                    unique=True,
                    name="uq_chat_memory_org_user",
                )
            except PyMongoError:
                _client.close()
                _client = None
                raise
            _index_ready = True
        return collection


def _memory_filter(organization_id: int, user_id: int) -> dict[str, int]:
    return {"organization_id": organization_id, "user_id": user_id}


def get_recent_messages(organization_id: int, user_id: int) -> list[dict[str, str]]:
    document = _memory_collection().find_one(
        _memory_filter(organization_id, user_id),
        {"messages": {"$slice": -MEMORY_MESSAGE_LIMIT}},
    )
    if not document:
        return []
    return [
        {"role": item["role"], "content": item["content"]}
        for item in document.get("messages", [])
        if item.get("role") in {"user", "assistant"}
        and isinstance(item.get("content"), str)
    ]


def append_message(
    organization_id: int,
    user_id: int,
    role: str,
    content: str,
) -> None:
    if role not in {"user", "assistant"}:
        raise ValueError("Chat memory role must be user or assistant")
    if len(content) > MEMORY_CONTENT_LIMIT:
        content = content[:MEMORY_CONTENT_LIMIT]
    message = {
        "role": role,
        "content": content,
        "created_at": datetime.now(timezone.utc),
    }
    _memory_collection().update_one(
        _memory_filter(organization_id, user_id),
        {
            "$push": {
                "messages": {
                    "$each": [message],
                    "$slice": -MEMORY_MESSAGE_LIMIT,
                }
            },
            "$setOnInsert": {
                "organization_id": organization_id,
                "user_id": user_id,
            },
        },
        upsert=True,
    )


def close_chat_memory_client() -> None:
    global _client, _index_ready
    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None
            _index_ready = False
