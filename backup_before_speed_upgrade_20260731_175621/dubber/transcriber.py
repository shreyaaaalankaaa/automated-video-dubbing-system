from __future__ import annotations

from pathlib import Path
from typing import Callable

from .models import SpeechSegment, TranscriptionResult
from .utils import merge_micro_segments


ProgressCallback = Callable[[str], None]


def _resolve_compute_type(device: str, compute_type: str) -> str:
    if compute_type != "auto":
        return compute_type
    return "float16" if device == "cuda" else "int8"


def _decode_options(content_profile: str) -> dict:
    if content_profile == "cinematic":
        return {
            "beam_size": 8,
            "best_of": 8,
            "patience": 1.2,
            "vad_parameters": {
                "threshold": 0.30,
                "min_speech_duration_ms": 100,
                "min_silence_duration_ms": 180,
                "speech_pad_ms": 300,
            },
        }
    return {
        "beam_size": 5,
        "best_of": 5,
        "patience": 1.0,
        "vad_parameters": {
            "min_silence_duration_ms": 400,
            "speech_pad_ms": 180,
        },
    }


def _collect_segments(generated, progress_callback: ProgressCallback | None = None) -> list[SpeechSegment]:
    segments: list[SpeechSegment] = []
    for index, item in enumerate(generated):
        words = []
        if item.words:
            words = [
                {
                    "start": word.start,
                    "end": word.end,
                    "word": word.word,
                    "probability": word.probability,
                }
                for word in item.words
            ]
        segments.append(
            SpeechSegment(
                index=index,
                start=float(item.start),
                end=float(item.end),
                text=item.text.strip(),
                words=words,
            )
        )
        if progress_callback and index % 20 == 0:
            progress_callback(f"Decoded {index + 1} timestamped speech segments")
    return merge_micro_segments(segments)


def transcribe_audio(
    audio_path: Path,
    *,
    model_name: str,
    device: str,
    compute_type: str,
    task: str,
    language: str | None = None,
    content_profile: str = "speech",
    glossary: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> TranscriptionResult:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Run: pip install -r requirements.txt"
        ) from exc

    if progress_callback:
        progress_callback(f"Loading Whisper model '{model_name}' on {device}")

    model = WhisperModel(
        model_name,
        device=device,
        compute_type=_resolve_compute_type(device, compute_type),
    )
    options = _decode_options(content_profile)
    hotwords = ", ".join(glossary or []) or None
    generated, info = model.transcribe(
        str(audio_path),
        task=task,
        language=language,
        beam_size=options["beam_size"],
        best_of=options["best_of"],
        patience=options["patience"],
        vad_filter=True,
        vad_parameters=options["vad_parameters"],
        word_timestamps=True,
        condition_on_previous_text=False,
        repetition_penalty=1.15,
        no_repeat_ngram_size=3,
        hallucination_silence_threshold=1.0,
        hotwords=hotwords,
        language_detection_segments=3,
    )

    segments = _collect_segments(generated, progress_callback)
    return TranscriptionResult(
        language=str(info.language),
        language_probability=float(info.language_probability),
        duration=float(info.duration),
        segments=segments,
        task=task,
        model=model_name,
    )


def _overlap_seconds(first: SpeechSegment, second: SpeechSegment) -> float:
    return max(0.0, min(first.end, second.end) - max(first.start, second.start))


def repair_translation_coverage(
    audio_path: Path,
    *,
    source_segments: list[SpeechSegment],
    translated_segments: list[SpeechSegment],
    model_name: str,
    device: str,
    compute_type: str,
    language: str,
    glossary: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[SpeechSegment], int]:
    """Target only source-language windows that received no English translation."""
    missing: list[SpeechSegment] = []
    for source in source_segments:
        required = min(0.25, max(0.08, source.duration * 0.12))
        covered = any(_overlap_seconds(source, translated) >= required for translated in translated_segments)
        if source.text.strip() and not covered:
            missing.append(source)

    if not missing:
        return translated_segments, 0

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Run: pip install -r requirements.txt"
        ) from exc

    if progress_callback:
        progress_callback(
            f"Coverage check found {len(missing)} source speech windows without an English dub; repairing"
        )

    model = WhisperModel(
        model_name,
        device=device,
        compute_type=_resolve_compute_type(device, compute_type),
    )
    clips: list[str] = []
    for segment in missing:
        clips.extend([f"{max(0.0, segment.start - 0.18):.3f}", f"{segment.end + 0.22:.3f}"])

    generated, _ = model.transcribe(
        str(audio_path),
        task="translate",
        language=language,
        clip_timestamps=",".join(clips),
        beam_size=8,
        best_of=8,
        patience=1.2,
        vad_filter=False,
        word_timestamps=True,
        condition_on_previous_text=False,
        repetition_penalty=1.15,
        no_repeat_ngram_size=3,
        hotwords=", ".join(glossary or []) or None,
    )
    repaired_candidates = _collect_segments(generated)

    repaired = 0
    combined = list(translated_segments)
    for candidate in repaired_candidates:
        if not candidate.text.strip():
            continue
        duplicate = any(
            _overlap_seconds(candidate, existing) >= min(0.35, candidate.duration * 0.45)
            for existing in combined
        )
        if duplicate:
            continue
        candidate.coverage_repair = True
        combined.append(candidate)
        repaired += 1

    combined.sort(key=lambda item: (item.start, item.end))
    combined = merge_micro_segments(combined, minimum_duration=0.45, maximum_gap=0.18)
    for index, segment in enumerate(combined):
        segment.index = index
    return combined, repaired
