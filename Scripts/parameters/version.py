
from pathlib import Path
import subprocess

VALMA_VERSION = "v1.0.0"

def git_provenance() -> str:
    """Return the Git description, if available."""
    repository_path = Path(__file__).resolve().parent.parent
    try:
        description = subprocess.check_output(
            ["git", "describe", "--tags"],
            cwd=repository_path,
            stderr=subprocess.STDOUT,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"
    return f"{description}"
