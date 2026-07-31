from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

from .models import SpeechSegment
from .utils import ensure_directory, estimate_tts_rate, stable_hash


ProgressCallback = Callable[[str], None]


async def _synthesize_one(
    segment: SpeechSegment,
    output_path: Path,
    *,
    voice: str,
    rate: str,
    pitch: str,
    volume: str,
    retries: int = 3,
) -> None:
    import edge_tts

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            communication = edge_tts.Communicate(
                segment.text,
                voice,
                rate=rate,
                pitch=pitch,
                volume=volume,
            )
            temporary = output_path.with_suffix(".partial.mp3")
            await communication.save(str(temporary))
            temporary.replace(output_path)
            return
        except Exception as exc:  # network failures vary by platform
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(1.5 * attempt)
    raise RuntimeError(f"TTS failed for segment {segment.index}: {last_error}")


async def synthesize_segments_async(
    segments: list[SpeechSegment],
    output_dir: Path,
    *,
    voice: str,
    pitch: str,
    volume: str,
    workers: int,
    adaptive_rate: bool,
    force: bool,
    progress_callback: ProgressCallback | None = None,
) -> dict[int, Path]:
    ensure_directory(output_dir)
    semaphore = asyncio.Semaphore(max(1, workers))
    completed = 0
    lock = asyncio.Lock()
    outputs: dict[int, Path] = {}

    async def run(segment: SpeechSegment) -> None:
        nonlocal completed
        rate = estimate_tts_rate(segment.text, segment.duration) if adaptive_rate else "+0%"
        segment.tts_rate = rate
        cache_key = stable_hash(segment.text, voice, rate, pitch, volume)
        path = output_dir / f"{segment.index:05d}_{cache_key}.mp3"
        outputs[segment.index] = path
        if force or not path.exists() or path.stat().st_size == 0:
            async with semaphore:
                await _synthesize_one(
                    segment,
                    path,
                    voice=voice,
                    rate=rate,
                    pitch=pitch,
                    volume=volume,
                )
        async with lock:
            completed += 1
            if progress_callback and (completed == 1 or completed % 10 == 0 or completed == len(segments)):
                progress_callback(f"Synthesized {completed}/{len(segments)} English segments")

    await asyncio.gather(*(run(segment) for segment in segments))
    return outputs


def synthesize_segments(
    segments: list[SpeechSegment],
    output_dir: Path,
    *,
    voice: str,
    pitch: str = "+0Hz",
    volume: str = "+0%",
    workers: int = 4,
    adaptive_rate: bool = True,
    force: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> dict[int, Path]:
    try:
        import edge_tts  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("edge-tts is not installed. Run: pip install -r requirements.txt") from exc

    return asyncio.run(
        synthesize_segments_async(
            segments,
            output_dir,
            voice=voice,
            pitch=pitch,
            volume=volume,
            workers=workers,
            adaptive_rate=adaptive_rate,
            force=force,
            progress_callback=progress_callback,
        )
    )


async def list_english_voices() -> list[dict]:
    import edge_tts

    voices = await edge_tts.list_voices()
    return sorted(
        [voice for voice in voices if str(voice.get("Locale", "")).startswith("en-")],
        key=lambda item: (item.get("Locale", ""), item.get("ShortName", "")),
    )
