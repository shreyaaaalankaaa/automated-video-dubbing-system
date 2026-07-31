# Submission Checklist

## Before running the final videos

- [ ] Use videos you own or have permission to process.
- [ ] Confirm FFmpeg and FFprobe work from the terminal.
- [ ] Run the test suite.
- [ ] Test the complete pipeline on a two-to-five-minute video.
- [ ] Choose videos with clear speech and limited overlapping speakers for the core submission.
- [ ] Record the machine specifications used for processing.

## Required run 1 — approximately 30 minutes

- [ ] Save the source YouTube URL.
- [ ] Run in `quality` mode.
- [ ] Review source and English SRT files.
- [ ] Watch at least the opening, middle, and ending sections.
- [ ] Review every warning in `quality_report.html`.
- [ ] Record exact wall-clock processing time.
- [ ] Upload the dubbed output to a shareable Drive folder.

## Required run 2 — approximately two hours

- [ ] Save the source YouTube URL.
- [ ] Use `fast` or `quality` mode based on hardware and deadline.
- [ ] Demonstrate resume behavior once by stopping after several TTS segments and rerunning.
- [ ] Review high-warning segments from the report.
- [ ] Record exact wall-clock processing time.
- [ ] Upload the dubbed output to a shareable Drive folder.

## Repository cleanup

- [ ] Do not commit video, WAV, MP3, model, or output files.
- [ ] Confirm `README.md` displays correctly on GitHub.
- [ ] Add one screenshot of `quality_report.html` to the repository description or submission folder.
- [ ] Confirm setup commands work in a clean virtual environment.
- [ ] Confirm no private cookies, tokens, or local paths are committed.
- [ ] Add the two final run metrics to the table below.

| Run | Source duration | Source language | Model/device | Processing time | Realtime factor | Timing warnings |
|---|---:|---|---|---:|---:|---:|
| 30-minute video |  |  |  |  |  |  |
| 2-hour video |  |  |  |  |  |  |

## Walkthrough video

- [ ] Keep it under two minutes.
- [ ] Show the result in the first 15 seconds.
- [ ] Explain timeline fitting and resume support.
- [ ] Open the HTML quality report.
- [ ] State limitations honestly.
- [ ] Avoid reading code line by line.

## Submission folder

Recommended Drive structure:

```text
Idealabs_Dubbing_Assignment_Sai_Divya_Lanka/
├── 01_Thirty_Minute_Run/
│   ├── source_link.txt
│   ├── dubbed_english.mp4
│   ├── quality_report.html
│   └── run_metrics.txt
├── 02_Two_Hour_Run/
│   ├── source_link.txt
│   ├── dubbed_english.mp4
│   ├── quality_report.html
│   └── run_metrics.txt
├── 03_Walkthrough/
│   └── architecture_walkthrough.mp4
└── 04_Code/
    └── github_repository_link.txt
```
