"""
MongoDB connection and User repository for authentication.

This module provides a drop-in replacement for the SQLAlchemy-based
UserRepository, connecting to MongoDB Atlas for user persistence.
All other database operations (jobs, extraction data, etc.) continue
to use the existing SQLite/PostgreSQL layer in database.py.

Collections created:
  - users  (unique index on email, index on provider_user_id)
"""
from __future__ import annotations

import os
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger("converter.auth.mongo")

# ---------------------------------------------------------------------------
# Document-level helpers
# ---------------------------------------------------------------------------

class MongoUser:
    """
    A plain Python object that mirrors the SQLAlchemy UserModel interface
    so that router.py needs zero changes.

    Fields match UserModel exactly:
        id, email, name, hashed_password, auth_provider,
        provider_user_id, profile_image, is_active, is_verified,
        created_at, updated_at
    """
    __slots__ = (
        "id", "email", "name", "hashed_password",
        "auth_provider", "provider_user_id", "profile_image",
        "is_active", "is_verified", "created_at", "updated_at",
    )

    def __init__(
        self,
        *,
        id: Optional[str] = None,
        email: str,
        name: str,
        hashed_password: Optional[str] = None,
        auth_provider: str = "LOCAL",
        provider_user_id: Optional[str] = None,
        profile_image: Optional[str] = None,
        is_active: bool = True,
        is_verified: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id or str(uuid4())
        self.email = email
        self.name = name
        self.hashed_password = hashed_password
        self.auth_provider = auth_provider
        self.provider_user_id = provider_user_id
        self.profile_image = profile_image
        self.is_active = is_active
        self.is_verified = is_verified
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def to_doc(self) -> dict:
        """Convert to a MongoDB document dict."""
        return {
            "_id": self.id,
            "email": self.email,
            "name": self.name,
            "hashed_password": self.hashed_password,
            "auth_provider": self.auth_provider,
            "provider_user_id": self.provider_user_id,
            "profile_image": self.profile_image,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> "MongoUser":
        """Construct a MongoUser from a MongoDB document."""
        return cls(
            id=str(doc["_id"]),
            email=doc["email"],
            name=doc.get("name", ""),
            hashed_password=doc.get("hashed_password"),
            auth_provider=doc.get("auth_provider", "LOCAL"),
            provider_user_id=doc.get("provider_user_id"),
            profile_image=doc.get("profile_image"),
            is_active=doc.get("is_active", True),
            is_verified=doc.get("is_verified", False),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def get_mongo_db() -> AsyncIOMotorDatabase:
    """Return (and lazily create) the Motor database instance."""
    global _client, _db
    if _db is not None:
        return _db

    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DATABASE", "access2java")

    if not uri:
        raise RuntimeError(
            "MONGODB_URI environment variable is not set. "
            "Add it to converter/.env"
        )

    logger.info("Connecting to MongoDB…")
    _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=10_000)

    # Verify connectivity
    await _client.admin.command("ping")
    logger.info("MongoDB connection established.")

    _db = _client[db_name]

    # Ensure indexes (idempotent)
    await _ensure_indexes(_db)

    return _db


async def close_mongo() -> None:
    """Close the MongoDB connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed.")


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create required indexes on first connect (idempotent)."""
    from pymongo import ASCENDING, IndexModel

    users = db["users"]
    await users.create_indexes([
        IndexModel([("email", ASCENDING)], unique=True, name="ix_users_email"),
        IndexModel([("provider_user_id", ASCENDING)], sparse=True, name="ix_users_provider_id"),
        IndexModel([("auth_provider", ASCENDING)], name="ix_users_auth_provider"),
    ])
    logger.debug("MongoDB indexes ensured on 'users' collection.")


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class MongoUserRepository:
    """
    Drop-in replacement for UserRepository (SQLAlchemy) that stores users
    in MongoDB.

    The calling API surface matches UserRepository exactly so auth/router.py
    can use this without modification.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db["users"]

    # ── create ──────────────────────────────────────────────────────────────

    async def create(self, user: MongoUser) -> MongoUser:
        doc = user.to_doc()
        await self._col.insert_one(doc)
        logger.debug("Created MongoDB user: %s", user.email)
        return user

    # ── read ────────────────────────────────────────────────────────────────

    async def get(self, user_id: str) -> Optional[MongoUser]:
        doc = await self._col.find_one({"_id": user_id})
        return MongoUser.from_doc(doc) if doc else None

    async def get_by_email(self, email: str) -> Optional[MongoUser]:
        doc = await self._col.find_one({"email": email})
        return MongoUser.from_doc(doc) if doc else None

    async def get_by_provider(self, provider: str, provider_user_id: str) -> Optional[MongoUser]:
        doc = await self._col.find_one({
            "auth_provider": provider,
            "provider_user_id": provider_user_id,
        })
        return MongoUser.from_doc(doc) if doc else None

    # ── update ──────────────────────────────────────────────────────────────

    async def update(self, user: MongoUser) -> MongoUser:
        user.updated_at = datetime.utcnow()
        await self._col.replace_one({"_id": user.id}, user.to_doc())
        logger.debug("Updated MongoDB user: %s", user.email)
        return user

    # ── delete ──────────────────────────────────────────────────────────────

    async def delete(self, user_id: str) -> bool:
        result = await self._col.delete_one({"_id": user_id})
        return result.deleted_count > 0


# ---------------------------------------------------------------------------
# FastAPI dependency (mirrors get_db_session pattern for the auth router)
# ---------------------------------------------------------------------------

async def get_mongo_user_repo() -> MongoUserRepository:
    """
    FastAPI dependency that yields a MongoUserRepository.
    Usage: repo = await get_mongo_user_repo()
    """
    db = await get_mongo_db()
    return MongoUserRepository(db)
