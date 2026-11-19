# Cinematic quality profile

Use this profile only for trailers, chants, overlapping dialogue, and music-heavy clips.

```powershell
python main.py "YOUTUBE_URL" --mode quality --model medium --device cpu --compute-type int8 --language hi --content-profile cinematic --repair-missed-speech --glossary "Ram,Rama,Sita,Hanuman,Ravana,Ayodhya,Lakshman,Dasharatha" --replacements-file examples\ramayana_replacements.json --force
```

What changed:

- aggressive short-speech VAD for rapid cuts
- proper-name hotword glossary
- coverage audit against the source-language transcript
- targeted recovery pass for speech windows skipped by whole-audio translation
- deterministic name correction map
- leading/trailing TTS silence removal
- natural-speed timing that uses the pause before the next line and compresses only when required

A cinematic trailer remains a stress test, not the recommended 30-minute or two-hour evaluation source. Use clear, mostly single-speaker material for the required submission and include a trailer only as an optional robustness demo.
