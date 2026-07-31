from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .background import separate_background
from .downloader import download_video
from .media import (
    duration_seconds,
    extract_audio,
    extract_full_audio,
    mix_background,
    mux_video,
    require_binary,
)
from .models import SpeechSegment, TranscriptionResult, VideoMetadata
from .report import build_quality_report
from .state import RunState
from .timeline import build_dubbed_timeline
from .transcriber import repair_translation_coverage, transcribe_audio
from .tts import synthesize_segments
from .utils import (
    ensure_directory,
    read_json,
    stable_hash,
    validate_youtube_url,
    apply_replacements,
    load_replacements,
    write_json,
    write_srt,
)


ProgressCallback = Callable[[str], None]


@dataclass(slots=True)
class PipelineConfig:
    url: str
    output_root: Path
    model_name: str = "small"
    device: str = "cpu"
    compute_type: str = "auto"
    mode: str = "quality"
    language: str | None = None
    voice: str = "en-US-AriaNeural"
    pitch: str = "+0Hz"
    volume: str = "+0%"
    tts_workers: int = 4
    adaptive_tts_rate: bool = True
    preserve_background: bool = False
    background_volume: float = 0.28
    cookies_from_browser: str | None = None
    force: bool = False
    content_profile: str = "speech"
    glossary: list[str] | None = None
    replacements_file: Path | None = None
    repair_missed_speech: bool = False


@dataclass(slots=True)
class PipelineResult:
    output_dir: Path
    output_video: Path
    quality_report: Path
    processing_seconds: float


def _load_transcription(path: Path) -> TranscriptionResult:
    data = read_json(path)
    return TranscriptionResult(
        language=data["language"],
        language_probability=float(data["language_probability"]),
        duration=float(data["duration"]),
        task=data["task"],
        model=data["model"],
        segments=[SpeechSegment.from_dict(item) for item in data["segments"]],
    )


def _save_metadata(path: Path, metadata: VideoMetadata) -> None:
    write_json(path, metadata.to_dict())


def _load_metadata(path: Path) -> VideoMetadata:
    data = read_json(path)
    return VideoMetadata(
        video_id=data["video_id"],
        title=data["title"],
        source_url=data["source_url"],
        duration=float(data["duration"]),
        uploader=data.get("uploader"),
        upload_date=data.get("upload_date"),
        webpage_url=data["webpage_url"],
        video_path=Path(data["video_path"]),
    )


def run_pipeline(
    config: PipelineConfig,
    *,
    progress_callback: ProgressCallback | None = None,
) -> PipelineResult:
    started = time.perf_counter()
    url = validate_youtube_url(config.url)
    require_binary("ffmpeg")
    require_binary("ffprobe")

    session_name = f"run_{stable_hash(url, length=10)}"
    output_dir = ensure_directory(config.output_root / session_name)
    work_dir = ensure_directory(output_dir / "work")
    state = RunState.load(output_dir / "run_state.json")

    metadata_path = output_dir / "source_metadata.json"
    if config.force or not state.completed("download") or not metadata_path.exists():
        if progress_callback:
            progress_callback("[1/8] Downloading source video")
        metadata = download_video(
            url,
            output_dir,
            cookies_from_browser=config.cookies_from_browser,
            progress_callback=progress_callback,
        )
        _save_metadata(metadata_path, metadata)
        state.mark("download", video_path=str(metadata.video_path))
    else:
        metadata = _load_metadata(metadata_path)

    if not metadata.video_path.exists():
        raise FileNotFoundError(
            f"Checkpoint references a missing source video: {metadata.video_path}. Use --force."
        )
    if metadata.duration <= 0:
        metadata.duration = duration_seconds(metadata.video_path)
        _save_metadata(metadata_path, metadata)

    audio_path = work_dir / "source_16k_mono.wav"
    if config.force or not state.completed("audio") or not audio_path.exists():
        if progress_callback:
            progress_callback("[2/8] Extracting speech-ready audio")
        extract_audio(metadata.video_path, audio_path)
        state.mark("audio", audio_path=str(audio_path))

    source_transcript_path = output_dir / "source_transcript.json"
    if config.mode == "quality":
        if config.force or not source_transcript_path.exists():
            if progress_callback:
                progress_callback("[3/8] Transcribing source-language speech")
            source_result = transcribe_audio(
                audio_path,
                model_name=config.model_name,
                device=config.device,
                compute_type=config.compute_type,
                task="transcribe",
                language=config.language,
                content_profile=config.content_profile,
                glossary=config.glossary,
                progress_callback=progress_callback,
            )
            write_json(source_transcript_path, source_result.to_dict())
            write_srt(output_dir / "source_transcript.srt", source_result.segments)
        else:
            source_result = _load_transcription(source_transcript_path)
        detected_language = source_result.language
    else:
        detected_language = config.language

    english_path = output_dir / "english_transcript.json"
    repaired_count = 0
    if config.force or not state.completed("translation") or not english_path.exists():
        if progress_callback:
            progress_callback("[4/8] Translating speech into timestamped English")
        english_result = transcribe_audio(
            audio_path,
            model_name=config.model_name,
            device=config.device,
            compute_type=config.compute_type,
            task="translate",
            language=detected_language,
            content_profile=config.content_profile,
            glossary=config.glossary,
            progress_callback=progress_callback,
        )
        if config.mode == "quality" and (config.repair_missed_speech or config.content_profile == "cinematic"):
            english_result.segments, repaired_count = repair_translation_coverage(
                audio_path,
                source_segments=source_result.segments,
                translated_segments=english_result.segments,
                model_name=config.model_name,
                device=config.device,
                compute_type=config.compute_type,
                language=detected_language or english_result.language,
                glossary=config.glossary,
                progress_callback=progress_callback,
            )
    else:
        english_result = _load_transcription(english_path)

    replacement_count = apply_replacements(
        english_result.segments, load_replacements(config.replacements_file)
    )
    write_json(english_path, english_result.to_dict())
    write_srt(output_dir / "english_transcript.srt", english_result.segments)
    state.mark(
        "translation",
        language=english_result.language,
        coverage_repairs=repaired_count,
        glossary_replacements=replacement_count,
    )

    segments = english_result.segments
    tts_dir = ensure_directory(work_dir / "tts_segments")
    if progress_callback:
        progress_callback("[5/8] Synthesizing natural English speech with cache support")
    tts_files = synthesize_segments(
        segments,
        tts_dir,
        voice=config.voice,
        pitch=config.pitch,
        volume=config.volume,
        workers=config.tts_workers,
        adaptive_rate=config.adaptive_tts_rate,
        force=config.force,
        progress_callback=progress_callback,
    )
    state.mark("tts", segment_count=len(tts_files), voice=config.voice)

    speech_timeline = work_dir / "dubbed_speech.wav"
    if progress_callback:
        progress_callback("[6/8] Fitting speech to the original timeline")
    warnings = build_dubbed_timeline(
        segments,
        tts_files,
        speech_timeline,
        video_duration=metadata.duration,
        work_dir=work_dir,
        force=config.force,
        progress_callback=progress_callback,
    )
    write_json(output_dir / "segment_diagnostics.json", [item.to_dict() for item in segments])
    state.mark("timeline", warnings=len(warnings))

    final_audio = output_dir / "dubbed_audio.wav"
    if config.preserve_background:
        if progress_callback:
            progress_callback("[7/8] Separating and restoring music/effects background")
        background_dir = ensure_directory(work_dir / "background_separation")
        full_audio = work_dir / "source_full_quality.wav"
        if config.force or not full_audio.exists():
            extract_full_audio(metadata.video_path, full_audio)
        background = separate_background(full_audio, background_dir)
        mix_background(
            speech_timeline,
            background,
            final_audio,
            background_volume=config.background_volume,
        )
    else:
        shutil.copy2(speech_timeline, final_audio)

    output_video = output_dir / "dubbed_english.mp4"
    if progress_callback:
        progress_callback("[8/8] Muxing English audio and validating final output")
    mux_video(metadata.video_path, final_audio, output_video)
    state.mark("mux", output_video=str(output_video))

    processing_seconds = time.perf_counter() - started
    build_quality_report(
        metadata=metadata,
        output_video=output_video,
        dubbed_audio=final_audio,
        segments=segments,
        language=english_result.language,
        language_probability=english_result.language_probability,
        model_name=config.model_name,
        voice=config.voice,
        processing_seconds=processing_seconds,
        warnings=warnings,
        output_dir=output_dir,
        background_preserved=config.preserve_background,
        content_profile=config.content_profile,
        glossary_terms=config.glossary or [],
    )
    state.mark("report", report=str(output_dir / "quality_report.html"))

    return PipelineResult(
        output_dir=output_dir,
        output_video=output_video,
        quality_report=output_dir / "quality_report.html",
        processing_seconds=processing_seconds,
    )
