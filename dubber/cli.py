from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .errors import DubberError
from .pipeline import PipelineConfig, run_pipeline
from .tts import list_english_voices
from .utils import parse_glossary


console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-dubber",
        description=(
            "Download a permitted YouTube video, translate its speech into English, "
            "synthesize timed English audio, and produce a validated dubbed MP4."
        ),
    )
    parser.add_argument("url", nargs="?", help="YouTube URL to process")
    parser.add_argument("--output", type=Path, default=Path("outputs"), help="Output root")
    parser.add_argument("--model", default="small", help="faster-whisper model name")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument(
        "--compute-type",
        default="auto",
        help="CTranslate2 compute type, e.g. int8, float16, or auto",
    )
    parser.add_argument(
        "--mode",
        choices=["quality", "fast"],
        default="quality",
        help=(
            "quality performs source ASR plus English translation; fast performs one "
            "English pass and can still repair likely missed speech using VAD"
        ),
    )
    parser.add_argument(
        "--inference-profile",
        choices=["accurate", "balanced", "speed"],
        default="balanced",
        help="balanced uses batched CPU inference; accurate keeps beam-8 cinematic decoding",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Whisper batch size; 4 is safe on most PCs, 8 is faster but uses more RAM",
    )
    parser.add_argument(
        "--cpu-threads",
        type=int,
        default=0,
        help="CPU threads for CTranslate2; 0 uses its default",
    )
    parser.add_argument(
        "--word-timestamps",
        action="store_true",
        help="Enable expensive word-level alignment; segment timestamps are used by default",
    )
    parser.add_argument("--language", help="Optional ISO language code; otherwise auto-detected")
    parser.add_argument("--voice", default="en-US-AriaNeural")
    parser.add_argument("--pitch", default="+0Hz")
    parser.add_argument("--volume", default="+0%")
    parser.add_argument("--tts-workers", type=int, default=4)
    parser.add_argument(
        "--no-adaptive-rate",
        action="store_true",
        help="Disable first-pass TTS speed estimation",
    )
    parser.add_argument(
        "--preserve-background",
        action="store_true",
        help="Use optional Demucs separation to restore music/effects below the dub",
    )
    parser.add_argument("--background-volume", type=float, default=0.28)
    parser.add_argument(
        "--cookies-from-browser",
        choices=["chrome", "edge", "firefox", "brave", "opera", "vivaldi"],
        help="Use browser cookies only when you have legitimate access to the video",
    )
    parser.add_argument(
        "--content-profile",
        choices=["speech", "cinematic"],
        default="speech",
        help="Use cinematic for trailers, music-heavy audio, chants, and rapid cuts",
    )
    parser.add_argument(
        "--glossary",
        help="Comma-separated names/terms Whisper should preserve, e.g. Ram,Sita,Ayodhya",
    )
    parser.add_argument(
        "--replacements-file",
        type=Path,
        help="Optional JSON map for deterministic proper-name corrections",
    )
    parser.add_argument(
        "--repair-missed-speech",
        action="store_true",
        help="Run a targeted second translation pass on source speech windows that were skipped",
    )
    parser.add_argument("--force", action="store_true", help="Rebuild cached stages")
    parser.add_argument("--list-voices", action="store_true", help="List available English voices")
    return parser


def _print_voices() -> None:
    voices = asyncio.run(list_english_voices())
    table = Table(title="Available English Edge TTS voices")
    table.add_column("Locale")
    table.add_column("Short name")
    table.add_column("Gender")
    for voice in voices:
        table.add_row(
            str(voice.get("Locale", "")),
            str(voice.get("ShortName", "")),
            str(voice.get("Gender", "")),
        )
    console.print(table)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_voices:
        _print_voices()
        return
    if not args.url:
        parser.error("A YouTube URL is required unless --list-voices is used.")

    console.print(
        Panel.fit(
            "[bold]Idealabs Automated Video Dubber[/bold]\n"
            "Resumable • timestamp-aware • quality-scored",
            border_style="blue",
        )
    )

    config = PipelineConfig(
        url=args.url,
        output_root=args.output,
        model_name=args.model,
        device=args.device,
        compute_type=args.compute_type,
        mode=args.mode,
        language=args.language,
        voice=args.voice,
        pitch=args.pitch,
        volume=args.volume,
        tts_workers=max(1, args.tts_workers),
        adaptive_tts_rate=not args.no_adaptive_rate,
        preserve_background=args.preserve_background,
        background_volume=max(0.0, min(1.0, args.background_volume)),
        cookies_from_browser=args.cookies_from_browser,
        force=args.force,
        content_profile=args.content_profile,
        glossary=parse_glossary(args.glossary),
        replacements_file=args.replacements_file,
        repair_missed_speech=args.repair_missed_speech,
        inference_profile=args.inference_profile,
        batch_size=max(1, args.batch_size),
        cpu_threads=max(0, args.cpu_threads),
        word_timestamps=args.word_timestamps,
    )

    try:
        result = run_pipeline(config, progress_callback=lambda message: console.print(message))
    except (DubberError, RuntimeError, ValueError, FileNotFoundError) as exc:
        console.print(f"[bold red]Pipeline failed:[/bold red] {exc}")
        sys.exit(1)

    console.print(
        Panel.fit(
            f"[bold green]Dub completed successfully[/bold green]\n"
            f"Video: {result.output_video}\n"
            f"Quality report: {result.quality_report}\n"
            f"Processing time: {result.processing_seconds:.1f}s",
            border_style="green",
        )
    )
