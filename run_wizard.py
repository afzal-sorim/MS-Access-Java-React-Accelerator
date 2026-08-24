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

    print("=" * 60)
    print("Starting MS Access Converter Wizard")
    print("=" * 60)
    print(f"Backend:  {backend_dir}")
    print(f"Frontend: {frontend_dir}")
    print("-" * 60)

    processes = []

    try:
        # Start FastAPI backend
        print("\n🚀 Starting FastAPI backend on http://localhost:8000")
        backend_cmd = [
            sys.executable, "-m", "uvicorn",
            "app.api.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload",
        ]
        backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=backend_dir,
            env={**os.environ, "PYTHONPATH": str(project_root)},
        )
        processes.append(("Backend", backend_proc))
        time.sleep(2)  # Give backend time to start

        # Start React frontend
        print("\n⚛️  Starting React frontend on http://localhost:3000")
        frontend_cmd = ["npm", "run", "dev"]
        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir,
            shell=True,  # Needed for npm on Windows
        )
        processes.append(("Frontend", frontend_proc))

        print("\n" + "=" * 60)
        print("✅ Both servers running!")
        print("   Backend:  http://localhost:8000")
        print("   Frontend: http://localhost:3000")
        print("   API Docs: http://localhost:8000/docs")
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