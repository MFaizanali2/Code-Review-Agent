import os
import shutil
from typing import List


def cleanup_temp_dir(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)


def get_python_files(directory: str) -> List[str]:
    py_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in [".git", "__pycache__", ".venv"]]
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))
    return py_files


def is_valid_github_url(url: str) -> bool:
    return url.startswith("https://github.com/") and len(url.split("/")) >= 5


def safe_read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def severity_rank(severity: str) -> int:
    return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "SAFE": 0}.get(severity, 0)
