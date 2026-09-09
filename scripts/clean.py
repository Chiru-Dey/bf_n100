import shutil
from pathlib import Path


def clean() -> None:
    root = Path(".")
    for path in root.rglob("__pycache__"):
        shutil.rmtree(path, ignore_errors=True)
    for path in root.rglob("*.pyc"):
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    clean()
