# Architecture and Engineering Decisions

## Goal

Convert a permitted YouTube video in a supported source language into an English-dubbed MP4 that is understandable, natural enough for review, synchronized to the original visual timeline, and reliable on long inputs.

## Design principles

1. **A complete result is more valuable than a fragile impressive demo.**
2. **Every expensive stage must be resumable.**
3. **Timing errors must be measured, not hidden.**
4. **Long media should not be loaded entirely into Python memory.**
5. **The core assignment should require no paid API.**
6. **Optional features must fail clearly without breaking the core path.**

## Components

### `downloader.py`

Embeds yt-dlp rather than shelling out to a brittle command string. It requests MP4 video and M4A audio when available, disables playlists, retries fragments, and emits progress hooks.

### `media.py`

Centralizes FFmpeg and FFprobe calls. All subprocess failures are converted into actionable exceptions containing the tail of FFmpeg's diagnostic output.

### `transcriber.py`

Uses faster-whisper with:

- voice activity detection
- word timestamps
- beam search
- repetition controls
- previous-text conditioning disabled to reduce long-form repetition cascades
- optional source-language hint

Quality mode uses two auditable passes:

1. `task="transcribe"` for the original-language transcript
2. `task="translate"` for timestamped English

Fast mode runs only the English translation pass.

### `tts.py`

Synthesizes one segment at a time with Edge TTS. Segment files are content-addressed using a hash of text, voice, rate, pitch, and volume. Requests use bounded concurrency, retries, atomic partial files, and cache reuse.

### `timeline.py`

The key non-basic component.

For every segment:

1. Probe actual generated TTS duration.
2. Calculate the target speech window.
3. Build a compatible FFmpeg `atempo` chain.
4. Pad or trim the fitted speech to its exact timeline block.
5. Concatenate PCM blocks in timestamp order.
6. Normalize final speech loudness.

This prevents cumulative timeline drift and avoids holding the full two-hour audio in Python memory.

### `background.py`

Optional Demucs integration separates the non-vocal stem from full-quality source audio. The stem is mixed beneath the English speech at a conservative volume. The core pipeline remains independent of this heavyweight feature.

### `report.py`

Generates machine-readable JSON and a standalone HTML review page. It validates output existence and duration, then surfaces timing pressure instead of pretending all segments are equally natural.

### `state.py`

Persists completed stages to `run_state.json`. Combined with file-level caches, this makes reruns safe after interruption.

## Data model

Each English speech segment contains:

```json
{
  "index": 42,
  "start": 81.22,
  "end": 84.95,
  "text": "The system checks the payment before approval.",
  "tts_rate": "+12%",
  "source_audio_duration": 4.21,
  "target_audio_duration": 3.73,
  "tempo_factor": 1.129,
  "sync_warning": null
}
```

This makes every dubbing decision inspectable.

## Failure handling

| Failure | Behavior |
|---|---|
| Invalid URL | Rejected before processing |
| FFmpeg absent | Clear installation error |
| Download interruption | yt-dlp retries; rerun resumes download behavior |
| Whisper failure | Existing source and audio remain cached |
| TTS request failure | Three retries; successful segments remain cached |
| Pipeline interruption | `run_state.json` and output files support rerun |
| Segment overlap | Available timeline space is used and warning is logged |
| Excessive speed fit | Audio is created but the segment is flagged in the report |
| Optional Demucs missing | Clear optional-install instruction |

## Scale considerations for the two-hour video

- No giant in-memory Python audio object.
- Segment TTS requests have bounded concurrency.
- Every generated segment is independently cached.
- Timeline blocks are PCM files concatenated by FFmpeg.
- Output diagnostics are incremental and inspectable.
- Fast mode avoids a second Whisper pass when runtime is constrained.

## Future extensions

### Speaker diarization

Add a `Diarizer` interface returning speaker labels for time intervals. Map each label to a distinct English TTS voice and preserve that mapping in diagnostics.

### Consent-based voice cloning

Add a `VoiceProvider` implementation backed by a local cloning model. Require an explicit consent flag and reference-audio provenance in run metadata.

### Translation refinement

Add a `Translator` interface that can route Indian languages through IndicTrans2 and use the Whisper English output as a fallback. Evaluate changes against a manually reviewed sample set.

### Better prosody

Estimate source pitch, intensity, and speaking-rate curves, then map them to TTS controls or a prosody-capable synthesis model.


## Coverage repair and cinematic mode

The quality pipeline first creates an independent source-language transcript and an English translation. It then compares their time coverage. Any source speech window with no English overlap is sent through a targeted second translation pass using exact clip timestamps. This avoids silently dropping short lines in trailers and music-heavy material. A user-supplied glossary biases decoding toward domain names, while an optional JSON replacement map provides deterministic final corrections. Timeline construction trims TTS boundary silence and preserves natural TTS pace whenever the generated line fits before the next original utterance; compression is applied only to prevent collision.
