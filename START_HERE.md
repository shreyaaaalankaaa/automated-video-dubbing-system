# Start Here

## What is already built

This repository contains the complete assignment implementation—not only an outline:

- YouTube URL CLI input
- yt-dlp retrieval
- source-language transcription
- English speech translation
- natural English segment synthesis
- adaptive timeline synchronization
- final MP4 audio replacement
- terminal progress
- crash recovery and caching
- SRT/JSON transcripts
- HTML/JSON quality reports
- optional background music/effects restoration
- tests, CI, Docker, setup scripts, architecture notes, and walkthrough script

## First local check

```powershell
cd idealabs-video-dubber
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/smoke_test.py
```

## First real video

Start with a permitted two-to-five-minute video:

```powershell
python main.py "YOUTUBE_URL" --mode quality --model small --device cpu
```

## Final assignment runs

For the 30-minute video, use quality mode:

```powershell
python main.py "THIRTY_MINUTE_URL" --mode quality --model medium --device cuda --compute-type float16
```

For the two-hour video, use fast mode when runtime is constrained:

```powershell
python main.py "TWO_HOUR_URL" --mode fast --model small --device cuda --compute-type float16
```

Use CPU and `--compute-type int8` when CUDA is unavailable.

## What to show in a demo

1. `dubbed_english.mp4`
2. `quality_report.html`
3. source and English `.srt` files
4. interruption-and-resume behavior
5. `segment_diagnostics.json`
6. the architecture diagram in `README.md`

## Remaining work that requires your input

The implementation is complete, but the two required output videos cannot be generated until you choose permitted 30-minute and two-hour YouTube URLs and run the model/TTS pipeline on your machine.
