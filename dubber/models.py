from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SpeechSegment:
    index: int
    start: float
    end: float
    text: str
    source_text: str | None = None
    words: list[dict[str, Any]] = field(default_factory=list)
    tts_rate: str = "+0%"
    source_audio_duration: float | None = None
    target_audio_duration: float | None = None
    tempo_factor: float | None = None
    sync_warning: str | None = None
    coverage_repair: bool = False

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpeechSegment":
        return cls(**data)


@dataclass(slots=True)
class VideoMetadata:
    video_id: str
    title: str
    source_url: str
    duration: float
    uploader: str | None
    upload_date: str | None
    webpage_url: str
    video_path: Path

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["video_path"] = str(self.video_path)
        return data


@dataclass(slots=True)
class TranscriptionResult:
    language: str
    language_probability: float
    duration: float
    segments: list[SpeechSegment]
    task: str
    model: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "language_probability": self.language_probability,
            "duration": self.duration,
            "task": self.task,
            "model": self.model,
            "segments": [segment.to_dict() for segment in self.segments],
        }
