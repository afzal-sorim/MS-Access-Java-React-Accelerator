#!/usr/bin/env python3
"""
Development script to run both the FastAPI backend and React frontend for the wizard.
"""
import subprocess
import sys
import os
import signal
import time
from pathlib import Path


def load_env(env_path: Path, target_env: dict):
    """Load env variables from a .env file into a target dictionary."""
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key:
                        target_env[key] = val
        except Exception as e:
            print(f"Warning: failed to load .env file {env_path}: {e}")


def run_wizard():
    """Run both backend and frontend servers."""
    project_root = Path(__file__).parent
    backend_dir = project_root / "converter"
    frontend_dir = project_root / "ui"

    # Check if directories exist
    if not backend_dir.exists():
        print(f"Backend directory not found: {backend_dir}")
        return 1

    if not frontend_dir.exists():
        print(f"Frontend directory not found: {frontend_dir}")
        return 1

    # Load environment variables from respective .env files
    backend_env = {**os.environ, "PYTHONPATH": str(project_root)}
    load_env(backend_dir / ".env", backend_env)

    frontend_env = {**os.environ}
    load_env(frontend_dir / ".env", frontend_env)

    backend_host = backend_env.get("BACKEND_HOST", "0.0.0.0")
    backend_port = backend_env.get("BACKEND_PORT", "8000")
    frontend_port = frontend_env.get("PORT", "3000")

    print("=" * 60)
    print("Starting MS Access Converter Wizard")
    print("=" * 60)
    print(f"Backend:  {backend_dir}")
    print(f"Frontend: {frontend_dir}")
    print("-" * 60)

    processes = []

    try:
        # Start FastAPI backend
        print(f"\n🚀 Starting FastAPI backend on http://localhost:{backend_port}")
        backend_cmd = [
            sys.executable, "-m", "uvicorn",
            "app.api.main:app",
            "--host", backend_host,
            "--port", backend_port,
            "--reload",
        ]
        backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=backend_dir,
            env=backend_env,
        )
        processes.append(("Backend", backend_proc))
        time.sleep(2)  # Give backend time to start

        # Start React frontend
        print(f"\n⚛️  Starting React frontend on http://localhost:{frontend_port}")
        frontend_cmd = ["npm", "run", "dev"]
        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir,
            shell=True,  # Needed for npm on Windows
            env=frontend_env,
        )
        processes.append(("Frontend", frontend_proc))

        print("\n" + "=" * 60)
        print("✅ Both servers running!")
        print(f"   Backend:  http://localhost:{backend_port}")
        print(f"   Frontend: http://localhost:{frontend_port}")
        print(f"   API Docs: http://localhost:{backend_port}/docs")
        print("=" * 60)
        print("\nPress Ctrl+C to stop both servers\n")

        # Wait for processes
        for name, proc in processes:
            proc.wait()

    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down servers...")
        for name, proc in processes:
            print(f"   Stopping {name}...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("✅ Done")


if __name__ == "__main__":
    sys.exit(run_wizard())