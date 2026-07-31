from __future__ import annotations

from pathlib import Path
from typing import Callable

from .media import create_silence, duration_seconds, require_binary, run_command
from .models import SpeechSegment
from .utils import atempo_chain, ensure_directory, ffconcat_quote


ProgressCallback = Callable[[str], None]


def _trim_tts_silence(source_path: Path, output_path: Path) -> float:
    ffmpeg = require_binary("ffmpeg")
    run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source_path),
            "-af",
            (
                "silenceremove=start_periods=1:start_duration=0.02:start_threshold=-50dB,"
                "areverse,"
                "silenceremove=start_periods=1:start_duration=0.02:start_threshold=-50dB,"
                "areverse,aresample=48000"
            ),
            "-ar",
            "48000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        description=f"Trimming TTS silence for {source_path.stem}",
    )
    return duration_seconds(output_path)


def fit_segment_to_block(
    source_path: Path,
    output_path: Path,
    *,
    block_duration: float,
    trimmed_path: Path,
) -> tuple[float, float, float]:
    ffmpeg = require_binary("ffmpeg")
    source_duration = _trim_tts_silence(source_path, trimmed_path)
    available = max(0.12, block_duration - 0.035)
    # Keep the natural TTS pace whenever it fits; compress only when it would collide
    # with the next speaker. This avoids the unnatural stretching in the first build.
    target = max(0.12, min(source_duration, available))
    factor = source_duration / target
    filters = (
        f"{atempo_chain(factor)},"
        f"apad,atrim=0:{target:.6f},"
        f"apad,atrim=0:{block_duration:.6f},"
        "aresample=48000"
    )
    run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(trimmed_path),
            "-af",
            filters,
            "-ar",
            "48000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        description=f"Synchronizing segment {output_path.stem}",
    )
    return source_duration, target, factor


def build_dubbed_timeline(
    segments: list[SpeechSegment],
    tts_files: dict[int, Path],
    output_path: Path,
    *,
    video_duration: float,
    work_dir: Path,
    force: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> list[str]:
    ffmpeg = require_binary("ffmpeg")
    blocks_dir = ensure_directory(work_dir / "timeline_blocks")
    trimmed_dir = ensure_directory(work_dir / "trimmed_tts")
    warnings: list[str] = []
    concat_entries: list[Path] = []

    if not segments:
        create_silence(output_path, video_duration)
        return ["No speech segments were detected; output contains silence."]

    if segments[0].start > 0.02:
        pre_roll = blocks_dir / "00000_preroll.wav"
        if force or not pre_roll.exists():
            create_silence(pre_roll, segments[0].start)
        concat_entries.append(pre_roll)

    for position, segment in enumerate(segments):
        next_start = segments[position + 1].start if position + 1 < len(segments) else video_duration
        block_duration = max(0.12, next_start - segment.start)
        if segment.end > next_start + 0.03:
            warning = (
                f"Segment {segment.index} overlaps the next segment by "
                f"{segment.end - next_start:.2f}s; fitted to available timeline space."
            )
            segment.sync_warning = warning
            warnings.append(warning)

        block_path = blocks_dir / f"{position + 1:05d}_segment.wav"
        trimmed_path = trimmed_dir / f"{position + 1:05d}_trimmed.wav"
        if force or not block_path.exists() or block_path.stat().st_size == 0:
            source_duration, target_duration, factor = fit_segment_to_block(
                tts_files[segment.index],
                block_path,
                block_duration=block_duration,
                trimmed_path=trimmed_path,
            )
            segment.source_audio_duration = source_duration
            segment.target_audio_duration = target_duration
            segment.tempo_factor = factor
        else:
            segment.source_audio_duration = duration_seconds(tts_files[segment.index])
            segment.target_audio_duration = min(segment.source_audio_duration, block_duration)
            segment.tempo_factor = segment.source_audio_duration / max(0.12, segment.target_audio_duration)

        if segment.tempo_factor and segment.tempo_factor > 1.38:
            warning = f"Segment {segment.index} required {segment.tempo_factor:.2f}x compression."
            segment.sync_warning = segment.sync_warning or warning
            warnings.append(warning)

        concat_entries.append(block_path)
        if progress_callback and (
            position == 0 or (position + 1) % 10 == 0 or position + 1 == len(segments)
        ):
            progress_callback(f"Synchronized {position + 1}/{len(segments)} segments")

    concat_file = work_dir / "timeline.ffconcat"
    concat_file.write_text(
        "ffconcat version 1.0\n" + "\n".join(ffconcat_quote(path) for path in concat_entries) + "\n",
        encoding="utf-8",
    )
    run_command(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-af",
            f"apad,atrim=0:{video_duration:.6f},loudnorm=I=-16:LRA=11:TP=-1.5",
            "-ar",
            "48000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        description="Building final dubbed audio timeline",
    )
    return warnings
