from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .errors import DependencyError, MediaError
from .utils import ensure_directory


def separate_background(original_audio: Path, output_dir: Path) -> Path:
    """Return a music/effects stem using Demucs' two-stem vocal separation."""
    try:
        import demucs  # noqa: F401
    except ImportError as exc:
        raise DependencyError(
            "Background preservation requires Demucs. Install with: "
            "pip install -e '.[background]'"
        ) from exc

    ensure_directory(output_dir)
    command = [
        sys.executable,
        "-m",
        "demucs",
        "--two-stems",
        "vocals",
        "-n",
        "htdemucs",
        "--out",
        str(output_dir),
        str(original_audio),
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise MediaError(f"Demucs separation failed:\n{result.stderr[-3000:]}")

    matches = list(output_dir.rglob("no_vocals.wav"))
    if not matches:
        raise MediaError("Demucs completed but no_vocals.wav was not found.")
    stem = matches[0]
    stable_path = output_dir / "background_no_vocals.wav"
    shutil.copy2(stem, stable_path)
    return stable_path
