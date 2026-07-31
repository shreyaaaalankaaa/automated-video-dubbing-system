from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from .errors import DependencyError, MediaError
from .utils import ensure_directory


def require_binary(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise DependencyError(
            f"'{name}' was not found. Install FFmpeg and ensure both ffmpeg and ffprobe "
            "are available on PATH."
        )
    return executable


def run_command(command: Sequence[str], *, description: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "Unknown media error").strip()
        raise MediaError(f"{description} failed:\n{detail[-3000:]}") from exc


def probe(path: Path) -> dict:
    ffprobe = require_binary("ffprobe")
    result = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        description=f"Probing {path.name}",
    )
    return json.loads(result.stdout)


def duration_seconds(path: Path) -> float:
    data = probe(path)
    try:
        return float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MediaError(f"Could not read media duration for {path}.") from exc


def extract_audio(video_path: Path, audio_path: Path) -> Path:
    ffmpeg = require_binary("ffmpeg")
    ensure_directory(audio_path.parent)
    run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(audio_path),
        ],
        description="Extracting transcription audio",
    )
    return audio_path


def extract_full_audio(video_path: Path, audio_path: Path) -> Path:
    ffmpeg = require_binary("ffmpeg")
    ensure_directory(audio_path.parent)
    run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            str(audio_path),
        ],
        description="Extracting full-quality source audio",
    )
    return audio_path


def create_silence(output_path: Path, duration: float, *, sample_rate: int = 48000) -> Path:
    ffmpeg = require_binary("ffmpeg")
    ensure_directory(output_path.parent)
    run_command(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={sample_rate}:cl=mono",
            "-t",
            f"{max(0.02, duration):.6f}",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        description="Creating timeline silence",
    )
    return output_path


def mux_video(video_path: Path, audio_path: Path, output_path: Path) -> Path:
    ffmpeg = require_binary("ffmpeg")
    ensure_directory(output_path.parent)
    run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ],
        description="Muxing dubbed audio with original video",
    )
    return output_path


def mix_background(
    speech_path: Path,
    background_path: Path,
    output_path: Path,
    *,
    background_volume: float = 0.28,
) -> Path:
    ffmpeg = require_binary("ffmpeg")
    run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(speech_path),
            "-i",
            str(background_path),
            "-filter_complex",
            (
                f"[1:a]volume={background_volume}[bg];"
                "[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0,"
                "loudnorm=I=-16:LRA=11:TP=-1.5[out]"
            ),
            "-map",
            "[out]",
            "-ar",
            "48000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        description="Mixing preserved background audio",
    )
    return output_path
