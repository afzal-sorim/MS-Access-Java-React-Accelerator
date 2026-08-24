"""Tests for FastAPI backend."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from pathlib import Path
import tempfile
import shutil


@pytest_asyncio.fixture
async def client():
    """Create test client."""
    from converter.app.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_cleanup():
    """Clean up database after tests."""
    yield
    # Cleanup code here if needed


class TestRootEndpoint:
    """Test root endpoint."""

    @pytest.mark.asyncio
    async def test_root(self, client):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "MS Access Converter API"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"


class TestJobEndpoints:
    """Test job management endpoints."""

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, client):
        response = await client.get("/api/jobs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, client):
        response = await client.get("/api/jobs/nonexistent")
        assert response.status_code == 404


class TestVersionEndpoint:
    """Test versions endpoint."""

    @pytest.mark.asyncio
    async def test_get_versions(self, client):
        response = await client.get("/api/versions")
        assert response.status_code == 200
        data = response.json()
        assert "backend" in data
        assert "frontend" in data
        assert "database" in data


class TestLLMEndpoints:
    """Test LLM orchestration endpoints."""

    @pytest.mark.asyncio
    async def test_llm_cache_stats(self, client):
        response = await client.get("/api/llm/cache")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total_tokens" in data
        assert "total_accesses" in data


class TestHealthCheck:
    """Health check tests."""

    @pytest.mark.asyncio
    async def test_health(self, client):
        response = await client.get("/")
        assert response.status_code == 200


class TestJobCreation:
    """Test job creation endpoints."""

    @pytest.mark.asyncio
    async def test_create_job_invalid_file_type(self, client):
        """Test that non-Access files are rejected."""
        files = {"file": ("test.txt", b"not an access file", "text/plain")}
        response = await client.post("/api/jobs", files=files)
        assert response.status_code == 400
        assert "must be .accdb or .mdb" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_job_no_file(self, client):
        """Test that missing file is rejected."""
        response = await client.post("/api/jobs")
        assert response.status_code == 400 or response.status_code == 422


class TestWebSocket:
    """Test WebSocket endpoint."""

    @pytest.mark.asyncio
    async def test_websocket_invalid_job(self, client):
        """Test WebSocket with non-existent job."""
        # Note: WebSocket testing requires special handling, skipping for now
        pass