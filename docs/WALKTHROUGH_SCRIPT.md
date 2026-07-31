# Two-Minute Walkthrough Script

## 0:00–0:15 — Result first

“I built an automated Python dubbing pipeline that accepts a permitted YouTube URL and creates an English-dubbed MP4. Here is the original clip, and here is the generated English output using the same video timeline.”

Show five to eight seconds of the source and dubbed output.

## 0:15–0:38 — Architecture

“The pipeline uses yt-dlp for retrieval, FFmpeg for media processing, faster-whisper for speech recognition and English translation, and Edge TTS for natural English synthesis. In quality mode, I save both the source-language transcript and the English transcript so translation decisions remain auditable.”

Show the architecture diagram in the README.

## 0:38–1:05 — Standout engineering decision

“The main challenge is not creating speech—it is preventing timing drift over a long video. I synthesize each timestamped segment independently, estimate an initial speaking rate, probe the real generated duration, and fit it into its original time window. The final audio is assembled as deterministic FFmpeg timeline blocks, so timing errors do not accumulate across a 30-minute or two-hour input.”

Show `timeline.py` and one segment in `segment_diagnostics.json`.

## 1:05–1:28 — Reliability

“Every expensive stage is resumable. Transcripts, TTS segments, and synchronized blocks are cached. If a two-hour run stops near the end, rerunning the same command reuses completed work rather than restarting. TTS requests also use bounded concurrency, retries, and atomic partial files.”

Show `run_state.json` and `work/tts_segments`.

## 1:28–1:48 — Quality evidence

“Each run creates a standalone HTML quality report. It records processing time, realtime factor, language confidence, output duration drift, and segments that required aggressive speed adjustment. This gives me a focused list for human review instead of hiding weak sections.”

Open `quality_report.html`.

## 1:48–2:00 — Honest close

“The core system is complete without a paid API. I also added optional background music and effects preservation using Demucs. Speaker diarization and consent-based voice cloning are designed as future extensions; I did not misrepresent a generic TTS voice as the original speaker.”
