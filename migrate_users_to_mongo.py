#!/usr/bin/env python3
"""
migrate_users_to_mongo.py
--------------------------
One-time migration script: copies existing users from SQLite → MongoDB.

Usage:
    python migrate_users_to_mongo.py

Run from the project root (MS-Access-Java-React-Accelerator-base-working/)
so that the .env at converter/.env is found automatically.

The SQLite database is NOT deleted. You can keep running it until
the MongoDB integration is verified, then safely remove the 'users'
table rows if desired.
"""
import asyncio
import os
import sys
from pathlib import Path

# ── Load .env ────────────────────────────────────────────────────────────────
env_path = Path(__file__).parent / "converter" / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip("'\""))

# ── Add converter to path ─────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

async def migrate():
    from motor.motor_asyncio import AsyncIOMotorClient
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select

    # ---------- Source: SQLite ----------
    sqlite_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./converter/converter_jobs_v2.db")
    print(f"[SOURCE] SQLite: {sqlite_url}")

    engine = create_async_engine(sqlite_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Import the SQLAlchemy UserModel (original)
    from converter.app.database import UserModel

    async with session_factory() as session:
        result = await session.execute(select(UserModel))
        sqlite_users = result.scalars().all()

    print(f"[SOURCE] Found {len(sqlite_users)} user(s) in SQLite.")

    if not sqlite_users:
        print("[INFO] No users to migrate. Exiting.")
        await engine.dispose()
        return

    # ---------- Destination: MongoDB ----------
    mongo_uri = os.environ.get("MONGODB_URI")
    mongo_db_name = os.environ.get("MONGODB_DATABASE", "access2java")

    if not mongo_uri:
        print("[ERROR] MONGODB_URI is not set in environment. Aborting.")
        sys.exit(1)

    print(f"[DEST] MongoDB: {mongo_db_name}")
    client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=10_000)

    # Verify connection
    await client.admin.command("ping")
    print("[DEST] MongoDB connection OK.")

    db = client[mongo_db_name]
    users_col = db["users"]

    # Ensure indexes
    from pymongo import ASCENDING, IndexModel
    await users_col.create_indexes([
        IndexModel([("email", ASCENDING)], unique=True, name="ix_users_email"),
        IndexModel([("provider_user_id", ASCENDING)], sparse=True, name="ix_users_provider_id"),
    ])

    # ---------- Migrate ----------
    migrated, skipped, failed = 0, 0, 0
    for u in sqlite_users:
        doc = {
            "_id": str(u.id),
            "email": u.email,
            "name": u.name,
            "hashed_password": u.hashed_password,
            "auth_provider": u.auth_provider,
            "provider_user_id": u.provider_user_id,
            "profile_image": u.profile_image,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "created_at": u.created_at,
            "updated_at": u.updated_at,
        }
        try:
            await users_col.insert_one(doc)
            print(f"  [OK] Migrated: {u.email}")
            migrated += 1
        except Exception as e:
            if "duplicate" in str(e).lower() or "E11000" in str(e):
                print(f"  [SKIP] Skipped (already exists): {u.email}")
                skipped += 1
            else:
                print(f"  [ERROR] Failed: {u.email} - {e}")
                failed += 1

    client.close()
    await engine.dispose()

    print(f"\n[DONE] Migrated: {migrated}  Skipped: {skipped}  Failed: {failed}")
    if failed:
        print("[WARNING] Some users failed to migrate. Check errors above.")
    else:
        print("[SUCCESS] All users successfully migrated to MongoDB.")

if __name__ == "__main__":
    asyncio.run(migrate())
