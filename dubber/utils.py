from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .models import SpeechSegment


_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def validate_youtube_url(url: str) -> str:
    candidate = url.strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in _YOUTUBE_HOSTS:
        raise ValueError("Provide a valid youtube.com or youtu.be URL.")
    return candidate


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    ensure_directory(path.parent)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def stable_hash(*parts: str, length: int = 16) -> str:
    digest = hashlib.sha256("\u241f".join(parts).encode("utf-8")).hexdigest()
    return digest[:length]


def clean_spoken_text(text: str) -> str:
    cleaned = re.sub(r"\[(music|applause|laughter|silence)\]", "", text, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def estimate_tts_rate(text: str, target_seconds: float, base_wpm: float = 165.0) -> str:
    words = max(1, len(text.split()))
    target_seconds = max(0.5, target_seconds)
    desired_wpm = words / target_seconds * 60.0
    percent = round((desired_wpm / base_wpm - 1.0) * 100)
    percent = max(-15, min(45, percent))
    sign = "+" if percent >= 0 else ""
    return f"{sign}{percent}%"


def atempo_chain(factor: float) -> str:
    if factor <= 0 or not math.isfinite(factor):
        raise ValueError("Tempo factor must be a positive finite number.")
    values: list[float] = []
    remaining = factor
    while remaining > 2.0:
        values.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        values.append(0.5)
        remaining /= 0.5
    if not math.isclose(remaining, 1.0, rel_tol=1e-4, abs_tol=1e-4) or not values:
        values.append(remaining)
    return ",".join(f"atempo={value:.6f}" for value in values)


def merge_micro_segments(
    segments: Iterable[SpeechSegment],
    *,
    minimum_duration: float = 0.8,
    maximum_gap: float = 0.35,
    maximum_merged_duration: float = 12.0,
) -> list[SpeechSegment]:
    ordered = list(segments)
    if not ordered:
        return []

    merged: list[SpeechSegment] = []
    for current in ordered:
        current.text = clean_spoken_text(current.text)
        if not current.text:
            continue
        if not merged:
            merged.append(current)
            continue

        previous = merged[-1]
        gap = max(0.0, current.start - previous.end)
        combined_duration = current.end - previous.start
        should_merge = (
            (previous.duration < minimum_duration or len(previous.text.split()) <= 2)
            and gap <= maximum_gap
            and combined_duration <= maximum_merged_duration
        )
        if should_merge:
            previous.end = current.end
            previous.text = clean_spoken_text(f"{previous.text} {current.text}")
            previous.words.extend(current.words)
        else:
            merged.append(current)

    for index, segment in enumerate(merged):
        segment.index = index
    return merged



def parse_glossary(value: str | None) -> list[str]:
    if not value:
        return []
    seen: set[str] = set()
    terms: list[str] = []
    for item in value.split(","):
        term = item.strip()
        key = term.casefold()
        if term and key not in seen:
            terms.append(term)
            seen.add(key)
    return terms


def load_replacements(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    data = read_json(path)
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        raise ValueError("Replacement file must be a JSON object of wrong-text to corrected-text pairs.")
    return data


def apply_replacements(segments: Iterable[SpeechSegment], replacements: dict[str, str]) -> int:
    changes = 0
    ordered = sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True)
    for segment in segments:
        updated = segment.text
        for wrong, correct in ordered:
            pattern = re.compile(rf"(?<!\w){re.escape(wrong)}(?!\w)", flags=re.I)
            updated, count = pattern.subn(correct, updated)
            changes += count
        segment.text = clean_spoken_text(updated)
    return changes

def seconds_to_srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(path: Path, segments: Iterable[SpeechSegment]) -> None:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            f"{index}\n{seconds_to_srt_timestamp(segment.start)} --> "
            f"{seconds_to_srt_timestamp(segment.end)}\n{segment.text}\n"
        )
    path.write_text("\n".join(blocks), encoding="utf-8")


def ffconcat_quote(path: Path) -> str:
    escaped = str(path.resolve()).replace("'", "'\\''")
    return f"file '{escaped}'"
