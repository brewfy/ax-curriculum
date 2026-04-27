"""로컬 개발용 백엔드 실행 헬퍼."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent  # 워크스페이스 루트

subprocess.run(
    [
        sys.executable, "-m", "uvicorn",
        "backend.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000",
    ],
    cwd=Path(__file__).parent,
    env={
        **__import__("os").environ,
        "PYTHONPATH": str(ROOT),
    },
)
