from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Callable

from .models import SpeechSegment, TranscriptionResult
from .utils import merge_micro_segments


ProgressCallback = Callable[[str], None]


def _resolve_compute_type(device: str, compute_type: str) -> str:
    if compute_type != "auto":
        return compute_type
    return "float16" if device == "cuda" else "int8"


def _decode_options(content_profile: str, inference_profile: str) -> dict:
    # Profiles intentionally separate decoding effort from speech sensitivity.
    # Lower VAD thresholds retain short lines under music; smaller beams improve speed.
    if inference_profile == "accurate":
        if content_profile == "cinematic":
            return {
                "beam_size": 8,
                "best_of": 8,
                "patience": 1.2,
                "use_batched": False,
                "word_timestamps": True,
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
            "use_batched": False,
            "word_timestamps": True,
            "vad_parameters": {
                "threshold": 0.42,
                "min_speech_duration_ms": 120,
                "min_silence_duration_ms": 400,
                "speech_pad_ms": 180,
            },
        }

    if inference_profile == "speed":
        return {
            "beam_size": 1,
            "best_of": 1,
            "patience": 1.0,
            "use_batched": True,
            "word_timestamps": False,
            "vad_parameters": {
                "threshold": 0.12 if content_profile == "cinematic" else 0.28,
                "min_speech_duration_ms": 40 if content_profile == "cinematic" else 80,
                "min_silence_duration_ms": 80 if content_profile == "cinematic" else 220,
                "speech_pad_ms": 400 if content_profile == "cinematic" else 240,
            },
        }

    # balanced: the default demo profile. It keeps short dialogue while
    # avoiding the expensive beam-8 and word-alignment path.
    return {
        "beam_size": 2,
        "best_of": 2,
        "patience": 1.0,
        "use_batched": True,
        "word_timestamps": False,
        "vad_parameters": {
            "threshold": 0.18 if content_profile == "cinematic" else 0.34,
            "min_speech_duration_ms": 60 if content_profile == "cinematic" else 100,
            "min_silence_duration_ms": 120 if content_profile == "cinematic" else 300,
            "speech_pad_ms": 350 if content_profile == "cinematic" else 220,
        },
    }


@lru_cache(maxsize=4)
def _load_model(
    model_name: str,
    device: str,
    compute_type: str,
    cpu_threads: int,
):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Run: pip install -r requirements.txt"
        ) from exc

    return WhisperModel(
        model_name,
        device=device,
        compute_type=_resolve_compute_type(device, compute_type),
        cpu_threads=max(0, cpu_threads),
    )


def _collect_segments(generated, progress_callback: ProgressCallback | None = None) -> list[SpeechSegment]:
    segments: list[SpeechSegment] = []
    for index, item in enumerate(generated):
        words = []
        if getattr(item, "words", None):
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
        if progress_callback and (index == 0 or (index + 1) % 20 == 0):
            progress_callback(f"Decoded {index + 1} timestamped speech segments")
    return merge_micro_segments(segments)


def _run_transcription(
    model,
    audio_path: Path,
    *,
    task: str,
    language: str | None,
    glossary: list[str] | None,
    options: dict,
    batch_size: int,
    word_timestamps: bool | None,
    clip_timestamps: list[dict[str, float]] | None = None,
    progress_callback: ProgressCallback | None = None,
):
    hotwords = ", ".join(glossary or []) or None
    use_word_timestamps = (
        options["word_timestamps"] if word_timestamps is None else word_timestamps
    )

    common = dict(
        task=task,
        language=language,
        beam_size=options["beam_size"],
        best_of=options["best_of"],
        patience=options["patience"],
        vad_filter=clip_timestamps is None,
        vad_parameters=options["vad_parameters"],
        word_timestamps=use_word_timestamps,
        condition_on_previous_text=False,
        repetition_penalty=1.12,
        no_repeat_ngram_size=3,
        hotwords=hotwords,
        language_detection_segments=3,
    )

    if options["use_batched"]:
        try:
            from faster_whisper import BatchedInferencePipeline

            batched = BatchedInferencePipeline(model=model)
            generated, info = batched.transcribe(
                str(audio_path),
                batch_size=max(1, batch_size),
                without_timestamps=False,
                clip_timestamps=clip_timestamps,
                log_progress=False,
                **common,
            )
            return generated, info
        except (ImportError, TypeError) as exc:
            # Older faster-whisper installations may not support every batched
            # option. Fall back safely rather than failing the submission.
            if progress_callback:
                progress_callback(f"Batched inference unavailable ({exc}); using standard decoding")

    regular_common = dict(common)
    regular_common.update(
        hallucination_silence_threshold=1.0,
    )
    if clip_timestamps:
        flat: list[str] = []
        for clip in clip_timestamps:
            flat.extend([f"{clip['start']:.3f}", f"{clip['end']:.3f}"])
        regular_common["clip_timestamps"] = ",".join(flat)
        regular_common["vad_filter"] = False
        regular_common.pop("vad_parameters", None)

    return model.transcribe(str(audio_path), **regular_common)


def transcribe_audio(
    audio_path: Path,
    *,
    model_name: str,
    device: str,
    compute_type: str,
    task: str,
    language: str | None = None,
    content_profile: str = "speech",
    inference_profile: str = "balanced",
    batch_size: int = 4,
    cpu_threads: int = 0,
    word_timestamps: bool | None = None,
    glossary: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> TranscriptionResult:
    if progress_callback:
        progress_callback(
            f"Loading/reusing Whisper model '{model_name}' on {device} "
            f"({inference_profile}, batch={max(1, batch_size)})"
        )

    model = _load_model(model_name, device, compute_type, cpu_threads)
    options = _decode_options(content_profile, inference_profile)
    generated, info = _run_transcription(
        model,
        audio_path,
        task=task,
        language=language,
        glossary=glossary,
        options=options,
        batch_size=batch_size,
        word_timestamps=word_timestamps,
        progress_callback=progress_callback,
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
    cpu_threads: int = 0,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[SpeechSegment], int]:
    """Target only source-language windows that received no English translation."""
    missing: list[SpeechSegment] = []
    for source in source_segments:
        required = min(0.25, max(0.08, source.duration * 0.12))
        covered = any(
            _overlap_seconds(source, translated) >= required
            for translated in translated_segments
        )
        if source.text.strip() and not covered:
            missing.append(source)

    if not missing:
        return translated_segments, 0

    if progress_callback:
        progress_callback(
            f"Coverage check found {len(missing)} source speech windows without an English dub; repairing"
        )

    model = _load_model(model_name, device, compute_type, cpu_threads)
    clips = [
        {"start": max(0.0, segment.start - 0.18), "end": segment.end + 0.22}
        for segment in missing
    ]
    options = _decode_options("cinematic", "balanced")
    generated, _ = _run_transcription(
        model,
        audio_path,
        task="translate",
        language=language,
        glossary=glossary,
        options=options,
        batch_size=4,
        word_timestamps=False,
        clip_timestamps=clips,
        progress_callback=progress_callback,
    )
    repaired_candidates = _collect_segments(generated)
    return _merge_repaired(translated_segments, repaired_candidates)


def _vad_windows(
    audio_path: Path,
    *,
    content_profile: str,
) -> list[dict[str, float]]:
    try:
        from faster_whisper.audio import decode_audio
        from faster_whisper.vad import VadOptions, get_speech_timestamps
    except ImportError as exc:
        raise RuntimeError("Your faster-whisper version does not expose VAD helpers") from exc

    sample_rate = 16000
    audio = decode_audio(str(audio_path), sampling_rate=sample_rate)
    profile = _decode_options(content_profile, "balanced")["vad_parameters"]
    vad_options = VadOptions(
        threshold=profile["threshold"],
        min_speech_duration_ms=profile["min_speech_duration_ms"],
        min_silence_duration_ms=profile["min_silence_duration_ms"],
        speech_pad_ms=profile["speech_pad_ms"],
        max_speech_duration_s=8.0,
    )
    timestamps = get_speech_timestamps(audio, vad_options)
    return [
        {
            "start": max(0.0, item["start"] / sample_rate),
            "end": max(0.0, item["end"] / sample_rate),
        }
        for item in timestamps
        if item["end"] > item["start"]
    ]


def repair_translation_coverage_vad(
    audio_path: Path,
    *,
    translated_segments: list[SpeechSegment],
    model_name: str,
    device: str,
    compute_type: str,
    language: str,
    content_profile: str,
    inference_profile: str,
    batch_size: int,
    cpu_threads: int,
    glossary: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[SpeechSegment], int]:
    """Fast coverage audit using VAD regions instead of a second full ASR pass."""
    windows = _vad_windows(audio_path, content_profile=content_profile)
    missing: list[dict[str, float]] = []
    for window in windows:
        duration = window["end"] - window["start"]
        overlap = sum(
            max(0.0, min(window["end"], seg.end) - max(window["start"], seg.start))
            for seg in translated_segments
        )
        # A low threshold catches short lines under music while avoiding a retry
        # for every tiny timestamp gap.
        if duration >= 0.28 and overlap / max(duration, 0.001) < 0.22:
            missing.append(
                {
                    "start": max(0.0, window["start"] - 0.15),
                    "end": window["end"] + 0.20,
                }
            )

    if not missing:
        return translated_segments, 0

    if progress_callback:
        progress_callback(
            f"Fast coverage audit found {len(missing)} likely missed speech windows; repairing only those"
        )

    model = _load_model(model_name, device, compute_type, cpu_threads)
    options = _decode_options(content_profile, inference_profile)
    # Repair needs slightly more decoding effort than the main speed pass.
    options = dict(options)
    options["beam_size"] = max(2, options["beam_size"])
    options["best_of"] = max(2, options["best_of"])
    generated, _ = _run_transcription(
        model,
        audio_path,
        task="translate",
        language=language,
        glossary=glossary,
        options=options,
        batch_size=max(1, batch_size),
        word_timestamps=False,
        clip_timestamps=missing,
        progress_callback=progress_callback,
    )
    repaired_candidates = _collect_segments(generated)
    return _merge_repaired(translated_segments, repaired_candidates)


def _merge_repaired(
    translated_segments: list[SpeechSegment],
    repaired_candidates: list[SpeechSegment],
) -> tuple[list[SpeechSegment], int]:
    repaired = 0
    combined = list(translated_segments)
    for candidate in repaired_candidates:
        if not candidate.text.strip():
            continue
        duplicate = any(
            _overlap_seconds(candidate, existing)
            >= min(0.35, max(0.08, candidate.duration * 0.45))
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
