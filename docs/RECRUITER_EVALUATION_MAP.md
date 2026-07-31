# Recruiter Evaluation Map

## What I would look for as the reviewer

### 1. Does it finish the actual assignment?

Yes. The CLI downloads one source video, creates English speech from translated timestamped segments, replaces the original audio, saves an MP4, and prints progress.

### 2. Can I understand the candidate's decisions quickly?

Yes. The README leads with the result and differentiation. The architecture is modular, the walkthrough is scripted, and every output contains auditable metadata.

### 3. Did the candidate merely connect libraries?

No. The candidate solved the difficult system concerns around long-video recovery, synchronization drift, segment caching, measurable quality, and optional preservation of background audio.

### 4. Is the code appropriate for a software-engineering-first internship?

Evidence:

- modules with single responsibilities
- typed data structures
- CLI argument validation
- centralized subprocess handling
- atomic JSON and TTS writes
- bounded async concurrency
- explicit error messages
- tests and CI
- no paid API requirement

### 5. Does the candidate understand tradeoffs?

The repository distinguishes:

- quality mode versus fast mode
- generic natural TTS versus true voice cloning
- reliable core requirements versus optional heavy processing
- automatic quality metrics versus mandatory human review

### 6. What should be demonstrated live?

1. Run a short video from the terminal.
2. Show generated source and English subtitles.
3. Interrupt and rerun during TTS to demonstrate caching.
4. Open segment diagnostics.
5. Open the HTML quality report.
6. Play the final dubbed MP4.
