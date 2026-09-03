"""
MongoDB Repositories for MS Access Converter Application.

Provides MongoDB persistent storage for:
- migration_jobs
- extraction_data
- ir_data
- dependency_graphs
- supportability_results
- build_logs
- llm_cache
- external_dependencies
- users
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel

from .jobs.models import JobState

logger = logging.getLogger("converter.mongo_repos")


# ---------------------------------------------------------------------------
# MongoDB Document Wrapper Objects (Interface Parity with SQLAlchemy Models)
# ---------------------------------------------------------------------------

class MongoJob:
    """Document wrapper for migration_jobs collection."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id") or str(kwargs.get("_id") or uuid4())
        self.user_id = kwargs.get("user_id")
        self.state = kwargs.get("state", JobState.CREATED.value)
        self.created_at = kwargs.get("created_at") or datetime.utcnow()
        self.updated_at = kwargs.get("updated_at") or datetime.utcnow()

        self.source_file = kwargs.get("source_file")
        self.source_file_size = kwargs.get("source_file_size")
        self.source_mode = kwargs.get("source_mode", "UPLOAD")
        self.source_origin = kwargs.get("source_origin")

        self.project_name = kwargs.get("project_name", "ConvertedApplication")
        self.base_package = kwargs.get("base_package", "com.generated.app")
        self.java_version = kwargs.get("java_version", 25)
        self.spring_boot_version = kwargs.get("spring_boot_version", "4.1.0")
        self.react_version = kwargs.get("react_version", "19.2.8")
        self.node_version = kwargs.get("node_version", 24)
        self.postgres_version = kwargs.get("postgres_version", "18")

        self.progress = kwargs.get("progress") or {
            "current_step": "",
            "total_steps": 25,
            "completed_steps": 0,
            "percentage": 0.0,
            "started_at": None,
            "estimated_remaining_seconds": None,
        }

        self.extraction_path = kwargs.get("extraction_path")
        self.ir_path = kwargs.get("ir_path")
        self.output_path = kwargs.get("output_path")

        self.result = kwargs.get("result")
        self.error = kwargs.get("error")
        self.build_validation = kwargs.get("build_validation")

        self.tables_count = kwargs.get("tables_count", 0)
        self.queries_count = kwargs.get("queries_count", 0)
        self.forms_count = kwargs.get("forms_count", 0)
        self.reports_count = kwargs.get("reports_count", 0)
        self.macros_count = kwargs.get("macros_count", 0)
        self.vba_modules_count = kwargs.get("vba_modules_count", 0)

        # Related documents populated when needed
        self.extraction_data = kwargs.get("extraction_data")
        self.ir_data = kwargs.get("ir_data")
        self.dependency_graph = kwargs.get("dependency_graph")
        self.supportability_results = kwargs.get("supportability_results", [])
        self.build_logs = kwargs.get("build_logs", [])
        self.llm_cache_entries = kwargs.get("llm_cache_entries", [])
        self.user = kwargs.get("user")

    def transition_to(self, new_state: JobState) -> None:
        """Transition to a new state, updating progress metadata."""
        self.state = new_state.value
        self.updated_at = datetime.utcnow()
        progress = dict(self.progress or {})
        progress["completed_steps"] = progress.get("completed_steps", 0) + 1
        progress["current_step"] = new_state.value
        total_steps = progress.get("total_steps", 25) or 25
        progress["percentage"] = round((progress["completed_steps"] / total_steps) * 100, 1)
        self.progress = progress

    def to_doc(self) -> dict:
        return {
            "_id": self.id,
            "user_id": self.user_id,
            "state": self.state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_file": self.source_file,
            "source_file_size": self.source_file_size,
            "source_mode": self.source_mode,
            "source_origin": self.source_origin,
            "project_name": self.project_name,
            "base_package": self.base_package,
            "java_version": self.java_version,
            "spring_boot_version": self.spring_boot_version,
            "react_version": self.react_version,
            "node_version": self.node_version,
            "postgres_version": self.postgres_version,
            "progress": self.progress,
            "extraction_path": self.extraction_path,
            "ir_path": self.ir_path,
            "output_path": self.output_path,
            "result": self.result,
            "error": self.error,
            "build_validation": self.build_validation,
            "tables_count": self.tables_count,
            "queries_count": self.queries_count,
            "forms_count": self.forms_count,
            "reports_count": self.reports_count,
            "macros_count": self.macros_count,
            "vba_modules_count": self.vba_modules_count,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> MongoJob:
        return cls(**doc)


class MongoExtractionData:
    def __init__(self, job_id: str, data: dict, id: Optional[str] = None, created_at: Optional[datetime] = None):
        self.id = id or str(uuid4())
        self.job_id = job_id
        self.data = data
        self.created_at = created_at or datetime.utcnow()

    def to_doc(self) -> dict:
        return {
            "_id": self.id,
            "job_id": self.job_id,
            "data": self.data,
            "created_at": self.created_at,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> MongoExtractionData:
        return cls(job_id=doc["job_id"], data=doc.get("data", {}), id=str(doc["_id"]), created_at=doc.get("created_at"))


class MongoIRData:
    def __init__(self, job_id: str, data: dict, application_name: Optional[str] = None, id: Optional[str] = None, created_at: Optional[datetime] = None):
        self.id = id or str(uuid4())
        self.job_id = job_id
        self.data = data
        self.application_name = application_name
        self.created_at = created_at or datetime.utcnow()

    def to_doc(self) -> dict:
        return {
            "_id": self.id,
            "job_id": self.job_id,
            "data": self.data,
            "application_name": self.application_name,
            "created_at": self.created_at,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> MongoIRData:
        return cls(job_id=doc["job_id"], data=doc.get("data", {}), application_name=doc.get("application_name"), id=str(doc["_id"]), created_at=doc.get("created_at"))


class MongoDependencyGraph:
    def __init__(self, job_id: str, nodes: list, edges: list, cycles: list, orphans: list, id: Optional[str] = None, created_at: Optional[datetime] = None):
        self.id = id or str(uuid4())
        self.job_id = job_id
        self.nodes = nodes
        self.edges = edges
        self.cycles = cycles
        self.orphans = orphans
        self.created_at = created_at or datetime.utcnow()

    def to_doc(self) -> dict:
        return {
            "_id": self.id,
            "job_id": self.job_id,
            "nodes": self.nodes,
            "edges": self.edges,
            "cycles": self.cycles,
            "orphans": self.orphans,
            "created_at": self.created_at,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> MongoDependencyGraph:
        return cls(
            job_id=doc["job_id"],
            nodes=doc.get("nodes", []),
            edges=doc.get("edges", []),
            cycles=doc.get("cycles", []),
            orphans=doc.get("orphans", []),
            id=str(doc["_id"]),
            created_at=doc.get("created_at"),
        )


class MongoSupportabilityResult:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id") or str(kwargs.get("_id") or uuid4())
        self.job_id = kwargs.get("job_id")
        self.object_name = kwargs.get("object_name")
        self.category = kwargs.get("category")
        self.status = kwargs.get("status")
        self.complexity = kwargs.get("complexity")
        self.risk = kwargs.get("risk")
        self.conversion = kwargs.get("conversion")
        self.confidence = kwargs.get("confidence")
        self.reason = kwargs.get("reason")
        self.created_at = kwargs.get("created_at") or datetime.utcnow()

    def to_doc(self) -> dict:
        return {
            "_id": self.id,
            "job_id": self.job_id,
            "object_name": self.object_name,
            "category": self.category,
            "status": self.status,
            "complexity": self.complexity,
            "risk": self.risk,
            "conversion": self.conversion,
            "confidence": self.confidence,
            "reason": self.reason,
            "created_at": self.created_at,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> MongoSupportabilityResult:
        return cls(**doc)


class MongoBuildLog:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id") or str(kwargs.get("_id") or uuid4())
        self.job_id = kwargs.get("job_id")
        self.phase = kwargs.get("phase")
        self.step = kwargs.get("step")
        self.status = kwargs.get("status")
        self.output = kwargs.get("output")
        self.error = kwargs.get("error")
        self.started_at = kwargs.get("started_at") or datetime.utcnow()
        self.completed_at = kwargs.get("completed_at")

    def to_doc(self) -> dict:
        return {
            "_id": self.id,
            "job_id": self.job_id,
            "phase": self.phase,
            "step": self.step,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> MongoBuildLog:
        return cls(**doc)


class MongoLLMCacheEntry:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id") or str(kwargs.get("_id") or uuid4())
        self.job_id = kwargs.get("job_id")
        self.cache_key = kwargs.get("cache_key")
        self.prompt_hash = kwargs.get("prompt_hash")
        self.system_prompt_hash = kwargs.get("system_prompt_hash")
        self.response = kwargs.get("response", {})
        self.model = kwargs.get("model")
        self.tokens_used = kwargs.get("tokens_used")
        self.provider_type = kwargs.get("provider_type")
        self.created_at = kwargs.get("created_at") or datetime.utcnow()
        self.access_count = kwargs.get("access_count", 1)
        self.last_accessed = kwargs.get("last_accessed") or datetime.utcnow()

    def to_doc(self) -> dict:
        return {
            "_id": self.id,
            "job_id": self.job_id,
            "cache_key": self.cache_key,
            "prompt_hash": self.prompt_hash,
            "system_prompt_hash": self.system_prompt_hash,
            "response": self.response,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "provider_type": self.provider_type,
            "created_at": self.created_at,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> MongoLLMCacheEntry:
        return cls(**doc)


class MongoExternalDependency:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id") or str(kwargs.get("_id") or uuid4())
        self.job_id = kwargs.get("job_id")
        self.dependency_type = kwargs.get("dependency_type")
        self.connection_info = kwargs.get("connection_info", {})
        self.location = kwargs.get("location")
        self.source_table = kwargs.get("source_table")
        self.target_table = kwargs.get("target_table")
        self.migration_strategy = kwargs.get("migration_strategy")
        self.support_status = kwargs.get("support_status")
        self.risk_level = kwargs.get("risk_level")
        self.has_credentials = kwargs.get("has_credentials", False)
        self.details = kwargs.get("details")
        self.created_at = kwargs.get("created_at") or datetime.utcnow()

    def to_doc(self) -> dict:
        return {
            "_id": self.id,
            "job_id": self.job_id,
            "dependency_type": self.dependency_type,
            "connection_info": self.connection_info,
            "location": self.location,
            "source_table": self.source_table,
            "target_table": self.target_table,
            "migration_strategy": self.migration_strategy,
            "support_status": self.support_status,
            "risk_level": self.risk_level,
            "has_credentials": self.has_credentials,
            "details": self.details,
            "created_at": self.created_at,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> MongoExternalDependency:
        return cls(**doc)


# ---------------------------------------------------------------------------
# Mongo Repositories Implementation
# ---------------------------------------------------------------------------

class MongoJobRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._col = db["migration_jobs"]

    async def create(self, job: MongoJob) -> MongoJob:
        await self._col.insert_one(job.to_doc())
        return job

    async def get(self, job_id: str) -> Optional[MongoJob]:
        doc = await self._col.find_one({"_id": job_id})
        if not doc:
            return None
        job = MongoJob.from_doc(doc)
        # Populate relationships
        ext_doc = await self.db["extraction_data"].find_one({"job_id": job_id})
        if ext_doc:
            job.extraction_data = MongoExtractionData.from_doc(ext_doc)
        ir_doc = await self.db["ir_data"].find_one({"job_id": job_id})
        if ir_doc:
            job.ir_data = MongoIRData.from_doc(ir_doc)
        dep_doc = await self.db["dependency_graphs"].find_one({"job_id": job_id})
        if dep_doc:
            job.dependency_graph = MongoDependencyGraph.from_doc(dep_doc)
        sup_cursor = self.db["supportability_results"].find({"job_id": job_id})
        job.supportability_results = [MongoSupportabilityResult.from_doc(d) async for d in sup_cursor]
        log_cursor = self.db["build_logs"].find({"job_id": job_id}).sort("started_at", ASCENDING)
        job.build_logs = [MongoBuildLog.from_doc(d) async for d in log_cursor]
        cache_cursor = self.db["llm_cache"].find({"job_id": job_id})
        job.llm_cache_entries = [MongoLLMCacheEntry.from_doc(d) async for d in cache_cursor]
        return job

    async def get_simple(self, job_id: str) -> Optional[MongoJob]:
        doc = await self._col.find_one({"_id": job_id})
        return MongoJob.from_doc(doc) if doc else None

    async def update(self, job: MongoJob) -> MongoJob:
        job.updated_at = datetime.utcnow()
        await self._col.replace_one({"_id": job.id}, job.to_doc())
        return job

    async def delete(self, job_id: str) -> bool:
        res = await self._col.delete_one({"_id": job_id})
        await self.db["extraction_data"].delete_many({"job_id": job_id})
        await self.db["ir_data"].delete_many({"job_id": job_id})
        await self.db["dependency_graphs"].delete_many({"job_id": job_id})
        await self.db["supportability_results"].delete_many({"job_id": job_id})
        await self.db["build_logs"].delete_many({"job_id": job_id})
        await self.db["llm_cache"].delete_many({"job_id": job_id})
        await self.db["external_dependencies"].delete_many({"job_id": job_id})
        return res.deleted_count > 0

    async def list_all(self, limit: int = 50, offset: int = 0) -> List[MongoJob]:
        cursor = self._col.find().sort("created_at", DESCENDING).skip(offset).limit(limit)
        return [MongoJob.from_doc(doc) async for doc in cursor]

    async def list_by_state(self, state: JobState, limit: int = 100) -> List[MongoJob]:
        cursor = self._col.find({"state": state.value}).sort("created_at", DESCENDING).limit(limit)
        return [MongoJob.from_doc(doc) async for doc in cursor]

    async def list_by_user(self, user_id: str, limit: int = 50, offset: int = 0) -> List[MongoJob]:
        cursor = self._col.find({"user_id": user_id}).sort("created_at", DESCENDING).skip(offset).limit(limit)
        return [MongoJob.from_doc(doc) async for doc in cursor]


class MongoExtractionRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._col = db["extraction_data"]

    async def create(self, job_id: str, data: dict) -> MongoExtractionData:
        model = MongoExtractionData(job_id=job_id, data=data)
        await self._col.insert_one(model.to_doc())
        return model

    async def get(self, job_id: str) -> Optional[MongoExtractionData]:
        doc = await self._col.find_one({"job_id": job_id})
        return MongoExtractionData.from_doc(doc) if doc else None

    async def update(self, job_id: str, data: dict) -> MongoExtractionData:
        doc = await self._col.find_one({"job_id": job_id})
        if doc:
            model = MongoExtractionData.from_doc(doc)
            model.data = data
            await self._col.replace_one({"_id": model.id}, model.to_doc())
            return model
        return await self.create(job_id, data)


class MongoIRRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._col = db["ir_data"]

    async def create(self, job_id: str, data: dict, application_name: str) -> MongoIRData:
        model = MongoIRData(job_id=job_id, data=data, application_name=application_name)
        await self._col.insert_one(model.to_doc())
        return model

    async def get(self, job_id: str) -> Optional[MongoIRData]:
        doc = await self._col.find_one({"job_id": job_id})
        return MongoIRData.from_doc(doc) if doc else None


class MongoDependencyGraphRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._col = db["dependency_graphs"]

    async def create(self, job_id: str, nodes: list, edges: list, cycles: list, orphans: list) -> MongoDependencyGraph:
        model = MongoDependencyGraph(job_id=job_id, nodes=nodes, edges=edges, cycles=cycles, orphans=orphans)
        await self._col.insert_one(model.to_doc())
        return model

    async def get(self, job_id: str) -> Optional[MongoDependencyGraph]:
        doc = await self._col.find_one({"job_id": job_id})
        return MongoDependencyGraph.from_doc(doc) if doc else None


class MongoSupportabilityRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._col = db["supportability_results"]

    async def create_batch(self, results: List[Any]) -> None:
        if not results:
            return
        docs = [
            r.to_doc() if hasattr(r, "to_doc") else MongoSupportabilityResult(
                job_id=r.job_id,
                object_name=r.object_name,
                category=r.category,
                status=r.status,
                complexity=r.complexity,
                risk=r.risk,
                conversion=r.conversion,
                confidence=r.confidence,
                reason=r.reason,
            ).to_doc()
            for r in results
        ]
        await self._col.insert_many(docs)

    async def list_by_job(self, job_id: str) -> List[MongoSupportabilityResult]:
        cursor = self._col.find({"job_id": job_id})
        return [MongoSupportabilityResult.from_doc(doc) async for doc in cursor]

    async def delete_by_job(self, job_id: str) -> None:
        await self._col.delete_many({"job_id": job_id})


class MongoBuildLogRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._col = db["build_logs"]

    async def create(self, job_id: str, phase: str, step: str, status: str, output: Optional[str] = None, error: Optional[str] = None) -> MongoBuildLog:
        model = MongoBuildLog(job_id=job_id, phase=phase, step=step, status=status, output=output, error=error)
        await self._col.insert_one(model.to_doc())
        return model

    async def update_status(self, log_id: str, status: str, output: Optional[str] = None, error: Optional[str] = None) -> Optional[MongoBuildLog]:
        doc = await self._col.find_one({"_id": log_id})
        if not doc:
            return None
        model = MongoBuildLog.from_doc(doc)
        model.status = status
        if output is not None:
            model.output = output
        if error is not None:
            model.error = error
        if status in ("completed", "failed"):
            model.completed_at = datetime.utcnow()
        await self._col.replace_one({"_id": log_id}, model.to_doc())
        return model

    async def list_by_job(self, job_id: str) -> List[MongoBuildLog]:
        cursor = self._col.find({"job_id": job_id}).sort("started_at", ASCENDING)
        return [MongoBuildLog.from_doc(doc) async for doc in cursor]


class MongoLLMCacheRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._col = db["llm_cache"]

    async def get_by_key(self, cache_key: str) -> Optional[MongoLLMCacheEntry]:
        doc = await self._col.find_one({"cache_key": cache_key})
        if not doc:
            return None
        model = MongoLLMCacheEntry.from_doc(doc)
        model.access_count += 1
        model.last_accessed = datetime.utcnow()
        await self._col.update_one(
            {"_id": model.id},
            {"$set": {"access_count": model.access_count, "last_accessed": model.last_accessed}},
        )
        return model

    async def put(self, cache_key: str, prompt_hash: str, system_prompt_hash: str, response: dict, model: str, tokens_used: int, provider_type: str, job_id: Optional[str] = None) -> MongoLLMCacheEntry:
        existing = await self._col.find_one({"cache_key": cache_key})
        if existing:
            entry = MongoLLMCacheEntry.from_doc(existing)
            entry.response = response
            entry.tokens_used = tokens_used
            entry.last_accessed = datetime.utcnow()
            await self._col.replace_one({"_id": entry.id}, entry.to_doc())
            return entry

        entry = MongoLLMCacheEntry(
            job_id=job_id,
            cache_key=cache_key,
            prompt_hash=prompt_hash,
            system_prompt_hash=system_prompt_hash,
            response=response,
            model=model,
            tokens_used=tokens_used,
            provider_type=provider_type,
        )
        await self._col.insert_one(entry.to_doc())
        return entry

    async def get_stats(self) -> dict:
        total_entries = await self._col.count_documents({})
        pipeline = [{"$group": {"_id": None, "total_tokens": {"$sum": "$tokens_used"}}}]
        agg = await self._col.aggregate(pipeline).to_list(1)
        total_tokens = agg[0]["total_tokens"] if agg else 0
        return {
            "total_entries": total_entries,
            "total_tokens_saved": total_tokens or 0,
        }

    async def clear(self) -> int:
        res = await self._col.delete_many({})
        return res.deleted_count


class MongoExternalDependencyRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._col = db["external_dependencies"]

    async def create_batch(self, dependencies: List[Any]) -> None:
        if not dependencies:
            return
        docs = [
            d.to_doc() if hasattr(d, "to_doc") else MongoExternalDependency(
                job_id=d.job_id,
                dependency_type=d.dependency_type,
                connection_info=d.connection_info,
                location=d.location,
                source_table=d.source_table,
                target_table=d.target_table,
                migration_strategy=d.migration_strategy,
                support_status=d.support_status,
                risk_level=d.risk_level,
                has_credentials=d.has_credentials,
                details=d.details,
            ).to_doc()
            for d in dependencies
        ]
        await self._col.insert_many(docs)

    async def list_by_job(self, job_id: str) -> List[MongoExternalDependency]:
        cursor = self._col.find({"job_id": job_id})
        return [MongoExternalDependency.from_doc(doc) async for doc in cursor]

    async def delete_by_job(self, job_id: str) -> None:
        await self._col.delete_many({"job_id": job_id})


async def ensure_mongo_app_indexes(db: AsyncIOMotorDatabase) -> None:
    """Ensure indexes across all MongoDB application collections."""
    await db["migration_jobs"].create_indexes([
        IndexModel([("state", ASCENDING)], name="ix_job_state"),
        IndexModel([("created_at", DESCENDING)], name="ix_job_created_at"),
        IndexModel([("user_id", ASCENDING)], sparse=True, name="ix_job_user_id"),
    ])
    await db["extraction_data"].create_index([("job_id", ASCENDING)], unique=True, name="ix_ext_job_id")
    await db["ir_data"].create_index([("job_id", ASCENDING)], unique=True, name="ix_ir_job_id")
    await db["dependency_graphs"].create_index([("job_id", ASCENDING)], unique=True, name="ix_dep_job_id")
    await db["supportability_results"].create_indexes([
        IndexModel([("job_id", ASCENDING), ("object_name", ASCENDING)], name="ix_sup_job_object"),
        IndexModel([("status", ASCENDING)], name="ix_sup_status"),
    ])
    await db["build_logs"].create_index([("job_id", ASCENDING), ("phase", ASCENDING)], name="ix_build_logs_job_phase")
    await db["llm_cache"].create_indexes([
        IndexModel([("cache_key", ASCENDING)], unique=True, name="ix_llm_cache_key"),
        IndexModel([("prompt_hash", ASCENDING)], name="ix_llm_cache_prompt_hash"),
    ])
    await db["external_dependencies"].create_index([("job_id", ASCENDING), ("dependency_type", ASCENDING)], name="ix_ext_dep_job_type")
    logger.info("Ensured indexes for all MongoDB application collections.")
