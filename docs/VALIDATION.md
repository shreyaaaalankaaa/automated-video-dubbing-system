# Validation Record

The repository was checked before packaging with the following local validations:

## Python compilation

```text
python -m compileall dubber main.py tests
Result: PASS
```

## Unit tests

```text
pytest -q
Result: 8 passed
```

The tests cover URL validation, timing-filter generation, adaptive-rate clamping, micro-segment merging, subtitle formatting, state persistence, and data-model round trips.

## Local FFmpeg integration smoke test

A synthetic six-second H.264/AAC video and two generated audio segments were processed through the real timeline builder and muxer.

Validated:

- TTS-duration probing
- segment tempo fitting
- pre-roll and inter-segment silence
- FFmpeg concat timeline generation
- exact six-second dubbed WAV
- stream-copy H.264 video with new AAC audio
- final MP4 containing video and audio streams

Observed result:

```text
Audio duration: 6.0 seconds
Output video duration: 6.0 seconds
Video codec: H.264
Audio codec: AAC, 48 kHz, mono
Result: PASS
```

The smoke test can be repeated locally:

```powershell
python scripts/smoke_test.py
```

## Scope not executed during packaging

A real YouTube/Whisper/Edge TTS run requires network access, model download, and a user-selected source video. The final 30-minute and two-hour assignment videos must therefore be run by the submitter and reviewed using the generated quality reports.
