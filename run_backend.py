import uvicorn
import sys
import os
from pathlib import Path

if __name__ == "__main__":
    # Add the current directory to sys.path to ensure 'converter' is found
    root_dir = Path(__file__).parent.resolve()
    sys.path.insert(0, str(root_dir))

    print(f"Starting server from root: {root_dir}")
    uvicorn.run("converter.app.api.main:app", host="0.0.0.0", port=8000, reload=True)
