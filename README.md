# Idealabs Automated Video Dubber

A production-style Python pipeline that accepts a permitted YouTube URL and creates an English-dubbed MP4 while preserving the original video stream and speech timing.

**Built for the Idealabs Digital internship assignment by Shreya Lanka.**

## Design goals

Beyond producing an MP4, the pipeline treats reliability and quality as requirements:

- **Resumable processing:** downloaded media, transcripts, TTS segments, and timeline blocks are checkpointed.
- **Segment-level TTS cache:** a failed two-hour run resumes instead of restarting.
- **Adaptive timing:** each English segment receives an estimated speaking rate and is then fitted to its original time window.
- **Quality gates:** the pipeline measures output duration drift, tempo-adjustment pressure, warning rate, processing time, and realtime factor.
- **Inspectable output:** every run generates `quality_report.html`, JSON diagnostics, source/English SRT files, and processing metadata.
- **Long-video-safe architecture:** audio is assembled from streamed FFmpeg blocks rather than loading a two-hour timeline into Python memory.
- **Optional background preservation:** Demucs can separate music/effects and mix them under the English dub.
- **Clean engineering:** typed modules, CLI validation, actionable errors, unit tests, linting, Docker support, and GitHub Actions.

## Pipeline

```text
YouTube URL
   │
   ▼
yt-dlp ───────────────► source.mp4
   │
   ▼
FFmpeg audio extraction
   │
   ├──► faster-whisper `transcribe` ─► source transcript + SRT (quality mode)
   │
   └──► faster-whisper `translate`  ─► timestamped English segments + SRT
                                           │
                                           ▼
                               edge-tts segment synthesis
                                           │
                                           ▼
                           adaptive duration fitting with FFmpeg
                                           │
                                           ▼
                             deterministic dubbed WAV timeline
                                           │
                       optional Demucs background restoration
                                           │
                                           ▼
                         stream-copy video + AAC English audio
                                           │
                                           ▼
                          dubbed MP4 + HTML/JSON quality report
```

## Core technologies

- Python 3.11+
- `yt-dlp` for source retrieval
- `faster-whisper` for multilingual speech recognition and English translation
- `edge-tts` for natural English speech
- FFmpeg/FFprobe for extraction, timing, loudness normalization, timeline creation, and muxing
- Optional Demucs for preserving non-vocal background audio
- Rich for clear terminal progress
- Pytest, Ruff, and GitHub Actions for engineering quality

## Installation on Windows

### 1. Install Python 3.11+

Confirm:

```powershell
python --version
```

### 2. Install FFmpeg

One simple Windows option:

```powershell
winget install Gyan.FFmpeg
```

Close and reopen the terminal, then verify:

```powershell
ffmpeg -version
ffprobe -version
```

### 3. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run a short permitted test video

```powershell
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" --output outputs --model small
```

Use only videos you own or are authorized to download and dub.

## Recommended commands

### Quality mode

Runs source-language transcription and English translation as separate auditable stages:

```powershell
python main.py "YOUTUBE_URL" `
  --mode quality `
  --model medium `
  --device cuda `
  --compute-type float16 `
  --voice en-US-AriaNeural `
  --tts-workers 4
```

### CPU-safe mode

```powershell
python main.py "YOUTUBE_URL" `
  --mode quality `
  --model small `
  --device cpu `
  --compute-type int8 `
  --tts-workers 3
```

### Faster two-hour run

Skips the separate source-language transcript pass but still creates timestamped English translation:

```powershell
python main.py "YOUTUBE_URL" `
  --mode fast `
  --model small `
  --device cuda `
  --compute-type float16 `
  --tts-workers 4
```

### Preserve music and sound effects

Install the optional dependency:

```powershell
pip install -e ".[background]"
```

Then:

```powershell
python main.py "YOUTUBE_URL" --preserve-background --background-volume 0.28
```

### List available English voices

```powershell
python main.py --list-voices
```

## Output structure

Each URL receives its own deterministic run directory:

```text
outputs/
└── run_<url_hash>/
    ├── source.mp4
    ├── source_metadata.json
    ├── source_transcript.json
    ├── source_transcript.srt
    ├── english_transcript.json
    ├── english_transcript.srt
    ├── segment_diagnostics.json
    ├── dubbed_audio.wav
    ├── dubbed_english.mp4
    ├── quality_report.json
    ├── quality_report.html
    ├── run_state.json
    └── work/
        ├── source_16k_mono.wav
        ├── tts_segments/
        ├── timeline_blocks/
        └── timeline.ffconcat
```

## Quality strategy

### Translation

`quality` mode produces both the source transcript and the English translation. This makes translation mistakes reviewable instead of hiding them inside the final audio.

### Natural voice

English speech is generated per timestamped segment. The system estimates an initial speaking-rate adjustment from text density, then performs measured FFmpeg fitting after probing the generated audio duration.

### Synchronization

Each segment is assigned a deterministic timeline block based on the next speech start time. This prevents cumulative drift across 30-minute and two-hour videos.

### Reliability

The TTS filename contains a hash of the text and voice settings. Rerunning the same job reuses successful segments. A network failure on segment 700 does not discard segments 1–699.

### Automated review

`quality_report.html` surfaces:

- source and output duration
- A/V duration drift
- detected source language and confidence
- total segments
- processing time and realtime factor
- mean/median/min/max tempo factor
- segments requiring aggressive timing adjustment
- overlap and synchronization warnings

## Resume behavior

Run the same command again. Existing stages and segment files are reused.

To rebuild everything:

```powershell
python main.py "YOUTUBE_URL" --force
```

## Testing

```powershell
pip install -r requirements-dev.txt
python -m compileall dubber main.py
ruff check dubber tests main.py
pytest
python scripts/smoke_test.py
```

## Evaluation-criteria mapping

| Idealabs criterion | Evidence in this repository |
|---|---|
| Fetch and transcribe | `downloader.py`, `transcriber.py`, source JSON/SRT |
| Translate meaning into English | Whisper translation pass, independent English JSON/SRT |
| Natural English synthesis | adaptive Edge TTS, configurable voice/pitch/volume |
| Replace original audio | deterministic WAV timeline and FFmpeg stream-copy mux |
| Terminal progress | eight named stages plus segment counters |
| 30-minute and two-hour reliability | checkpoints, per-segment cache, streamed timeline assembly |
| Accuracy and timing | word timestamps, segment timing, duration fit, quality warnings |
| Code quality and clarity | modular package, types, errors, tests, CI, architecture documentation |
| Ambitious enhancement | optional background separation/restoration |

## Honest limitations

- A generic Edge TTS voice does not literally clone the original speaker. The README and walkthrough state this clearly.
- Aggressive translation expansion may require noticeable tempo acceleration. These cases are flagged for human review.
- Speaker diarization and consent-based voice cloning are intentionally documented as extensions rather than presented as completed functionality.
- YouTube retrieval depends on current site behavior and the downloader must be kept updated.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/WALKTHROUGH_SCRIPT.md`](docs/WALKTHROUGH_SCRIPT.md)
- [`docs/SUBMISSION_CHECKLIST.md`](docs/SUBMISSION_CHECKLIST.md)
- [`docs/VALIDATION.md`](docs/VALIDATION.md)
- [`docs/CINEMATIC_PROFILE.md`](docs/CINEMATIC_PROFILE.md)

## License and responsible use

The source code is MIT licensed. Process only content you own or have permission to use. Do not clone or imitate a person's voice without explicit consent.

## Cinematic / trailer stress-test mode

For rapid cuts, background music, chants, short lines, and important proper names, use the cinematic profile. It adds aggressive short-speech detection, glossary-biased decoding, a source-vs-English coverage audit, targeted recovery of skipped speech windows, deterministic name correction, TTS silence trimming, and natural-speed timeline fitting.

```powershell
python main.py "YOUTUBE_URL" --mode quality --model medium --device cpu --compute-type int8 --language hi --content-profile cinematic --repair-missed-speech --glossary "Ram,Rama,Sita,Hanuman,Ravana,Ayodhya,Lakshman,Dasharatha" --replacements-file examples\ramayana_replacements.json --force
```

A trailer is intentionally treated as a robustness test. The required 30-minute and two-hour submissions should still use clear, permissioned, mostly single-speaker material so linguistic quality—not soundtrack separation—remains the primary evaluation.
