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
_mongo_available: Optional[bool] = None


async def get_mongo_db() -> Optional[AsyncIOMotorDatabase]:
    """Return (and lazily create) the Motor database instance, or None if unavailable."""
    global _client, _db, _mongo_available
    if _db is not None:
        return _db
    if _mongo_available is False:
        return None

    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DATABASE", "access2java")

    if not uri:
        _mongo_available = False
        return None

    try:
        logger.info("Connecting to MongoDB…")
        _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=2000)
        # Verify connectivity
        await _client.admin.command("ping")
        logger.info("MongoDB connection established.")
        _db = _client[db_name]
        await _ensure_indexes(_db)
        _mongo_available = True
        return _db
    except Exception as e:
        logger.warning(
            "MongoDB Atlas connection failed (%s). Falling back to local SQLite user store.",
            e,
        )
        _mongo_available = False
        return None


async def close_mongo() -> None:
    """Close the MongoDB connection."""
    global _client, _db, _mongo_available
    if _client:
        _client.close()
        _client = None
        _db = None
        _mongo_available = None
        logger.info("MongoDB connection closed.")


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create required indexes on first connect (idempotent)."""
    from pymongo import ASCENDING, IndexModel
    from converter.app.mongo_repos import ensure_mongo_app_indexes

    users = db["users"]
    await users.create_indexes([
        IndexModel([("email", ASCENDING)], unique=True, name="ix_users_email"),
        IndexModel([("provider_user_id", ASCENDING)], sparse=True, name="ix_users_provider_id"),
        IndexModel([("auth_provider", ASCENDING)], name="ix_users_auth_provider"),
    ])
    await ensure_mongo_app_indexes(db)
    logger.debug("MongoDB indexes ensured on 'users' and application collections.")


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------

class MongoUserRepository:
    """
    Drop-in replacement for UserRepository (SQLAlchemy) that stores users
    in MongoDB.
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


class SQLiteUserRepoAdapter:
    """
    Fallback repository for when MongoDB is unavailable (e.g. IP whitelist / network restriction).
    Uses the local SQLite database.
    """

    async def create(self, user: MongoUser) -> MongoUser:
        from converter.app.database import get_session, UserModel
        async with get_session() as session:
            db_user = UserModel(
                id=user.id,
                email=user.email,
                name=user.name,
                hashed_password=user.hashed_password,
                auth_provider=user.auth_provider,
                provider_user_id=user.provider_user_id,
                profile_image=user.profile_image,
                is_active=user.is_active,
                is_verified=user.is_verified,
            )
            session.add(db_user)
            await session.commit()
            return user

    async def get(self, user_id: str) -> Optional[MongoUser]:
        from converter.app.database import get_session, UserModel
        from sqlalchemy import select
        async with get_session() as session:
            res = await session.execute(select(UserModel).where(UserModel.id == user_id))
            u = res.scalar_one_or_none()
            if not u:
                return None
            return MongoUser(
                id=u.id,
                email=u.email,
                name=u.name,
                hashed_password=u.hashed_password,
                auth_provider=u.auth_provider,
                provider_user_id=u.provider_user_id,
                profile_image=u.profile_image,
                is_active=u.is_active,
                is_verified=u.is_verified,
                created_at=u.created_at,
                updated_at=u.updated_at,
            )

    async def get_by_email(self, email: str) -> Optional[MongoUser]:
        from converter.app.database import get_session, UserModel
        from sqlalchemy import select
        async with get_session() as session:
            res = await session.execute(select(UserModel).where(UserModel.email == email))
            u = res.scalar_one_or_none()
            if not u:
                return None
            return MongoUser(
                id=u.id,
                email=u.email,
                name=u.name,
                hashed_password=u.hashed_password,
                auth_provider=u.auth_provider,
                provider_user_id=u.provider_user_id,
                profile_image=u.profile_image,
                is_active=u.is_active,
                is_verified=u.is_verified,
                created_at=u.created_at,
                updated_at=u.updated_at,
            )

    async def get_by_provider(self, provider: str, provider_user_id: str) -> Optional[MongoUser]:
        from converter.app.database import get_session, UserModel
        from sqlalchemy import select
        async with get_session() as session:
            res = await session.execute(
                select(UserModel).where(
                    UserModel.auth_provider == provider,
                    UserModel.provider_user_id == provider_user_id,
                )
            )
            u = res.scalar_one_or_none()
            if not u:
                return None
            return MongoUser(
                id=u.id,
                email=u.email,
                name=u.name,
                hashed_password=u.hashed_password,
                auth_provider=u.auth_provider,
                provider_user_id=u.provider_user_id,
                profile_image=u.profile_image,
                is_active=u.is_active,
                is_verified=u.is_verified,
                created_at=u.created_at,
                updated_at=u.updated_at,
            )

    async def update(self, user: MongoUser) -> MongoUser:
        from converter.app.database import get_session, UserModel
        from sqlalchemy import select
        async with get_session() as session:
            res = await session.execute(select(UserModel).where(UserModel.id == user.id))
            u = res.scalar_one_or_none()
            if u:
                u.email = user.email
                u.name = user.name
                u.hashed_password = user.hashed_password
                u.auth_provider = user.auth_provider
                u.provider_user_id = user.provider_user_id
                u.profile_image = user.profile_image
                u.is_active = user.is_active
                u.is_verified = user.is_verified
                u.updated_at = datetime.utcnow()
                await session.commit()
            return user

    async def delete(self, user_id: str) -> bool:
        from converter.app.database import get_session, UserModel
        from sqlalchemy import delete
        async with get_session() as session:
            res = await session.execute(delete(UserModel).where(UserModel.id == user_id))
            await session.commit()
            return res.rowcount > 0


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_mongo_user_repo():
    """
    FastAPI dependency yielding MongoUserRepository if MongoDB is reachable,
    otherwise falling back to SQLiteUserRepoAdapter seamlessly.
    """
    db = await get_mongo_db()
    if db is not None:
        return MongoUserRepository(db)
    return SQLiteUserRepoAdapter()


async def get_mongo_app_repos():
    """Returns a dict of all MongoDB application repositories if MongoDB is reachable."""
    db = await get_mongo_db()
    if db is None:
        return None
    from converter.app.mongo_repos import (
        MongoJobRepository,
        MongoExtractionRepository,
        MongoIRRepository,
        MongoDependencyGraphRepository,
        MongoSupportabilityRepository,
        MongoBuildLogRepository,
        MongoLLMCacheRepository,
        MongoExternalDependencyRepository,
    )
    return {
        "job_repo": MongoJobRepository(db),
        "extraction_repo": MongoExtractionRepository(db),
        "ir_repo": MongoIRRepository(db),
        "dependency_graph_repo": MongoDependencyGraphRepository(db),
        "supportability_repo": MongoSupportabilityRepository(db),
        "build_log_repo": MongoBuildLogRepository(db),
        "llm_cache_repo": MongoLLMCacheRepository(db),
        "external_dep_repo": MongoExternalDependencyRepository(db),
    }

