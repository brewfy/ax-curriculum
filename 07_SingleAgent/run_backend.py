"""로컬 개발용 백엔드 실행 스크립트."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).parent.parent
cmd = [
    sys.executable, "-m", "uvicorn",
    "backend.main:app",
    "--reload",
    "--host", "0.0.0.0",
    "--port", "8000",
]
subprocess.run(cmd, cwd=Path(__file__).parent)
