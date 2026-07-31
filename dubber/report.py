from __future__ import annotations

import html
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .media import duration_seconds, probe
from .models import SpeechSegment, VideoMetadata
from .utils import write_json


def build_quality_report(
    *,
    metadata: VideoMetadata,
    output_video: Path,
    dubbed_audio: Path,
    segments: list[SpeechSegment],
    language: str,
    language_probability: float,
    model_name: str,
    voice: str,
    processing_seconds: float,
    warnings: list[str],
    output_dir: Path,
    background_preserved: bool,
    content_profile: str = "speech",
    glossary_terms: list[str] | None = None,
) -> dict[str, Any]:
    source_duration = metadata.duration or duration_seconds(metadata.video_path)
    output_duration = duration_seconds(output_video)
    audio_duration = duration_seconds(dubbed_audio)
    tempo_factors = [
        segment.tempo_factor for segment in segments if segment.tempo_factor is not None
    ]
    severe_timing = [factor for factor in tempo_factors if not 0.78 <= factor <= 1.38]
    av_drift = abs(output_duration - source_duration)

    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "project": "Idealabs Automated Video Dubbing System",
        "source": {
            "title": metadata.title,
            "video_id": metadata.video_id,
            "url": metadata.webpage_url,
            "uploader": metadata.uploader,
            "duration_seconds": round(source_duration, 3),
        },
        "pipeline": {
            "whisper_model": model_name,
            "detected_language": language,
            "language_probability": round(language_probability, 4),
            "tts_voice": voice,
            "background_preserved": background_preserved,
            "content_profile": content_profile,
            "glossary_terms": glossary_terms or [],
            "coverage_repaired_segments": sum(1 for segment in segments if segment.coverage_repair),
            "segments": len(segments),
            "processing_seconds": round(processing_seconds, 3),
            "realtime_factor": round(processing_seconds / max(1.0, source_duration), 4),
        },
        "quality_gates": {
            "output_exists": output_video.exists() and output_video.stat().st_size > 0,
            "audio_duration_seconds": round(audio_duration, 3),
            "duration_drift_seconds": round(av_drift, 3),
            "duration_gate_passed": av_drift <= 0.75,
            "mean_tempo_factor": round(statistics.mean(tempo_factors), 3)
            if tempo_factors
            else None,
            "median_tempo_factor": round(statistics.median(tempo_factors), 3)
            if tempo_factors
            else None,
            "max_tempo_factor": round(max(tempo_factors), 3) if tempo_factors else None,
            "min_tempo_factor": round(min(tempo_factors), 3) if tempo_factors else None,
            "segments_outside_preferred_tempo_range": len(severe_timing),
            "timing_warning_rate": round(len(severe_timing) / max(1, len(segments)), 4),
        },
        "outputs": {
            "dubbed_video": str(output_video),
            "dubbed_audio": str(dubbed_audio),
            "video_probe": probe(output_video),
        },
        "warnings": warnings,
        "segment_diagnostics": [segment.to_dict() for segment in segments],
    }
    write_json(output_dir / "quality_report.json", report)
    _write_html_report(output_dir / "quality_report.html", report)
    return report


def _status_badge(passed: bool) -> str:
    label = "PASS" if passed else "CHECK"
    css = "pass" if passed else "check"
    return f'<span class="badge {css}">{label}</span>'


def _write_html_report(path: Path, report: dict[str, Any]) -> None:
    source = report["source"]
    pipeline = report["pipeline"]
    gates = report["quality_gates"]
    warnings = report["warnings"]
    warning_rows = "".join(f"<li>{html.escape(item)}</li>" for item in warnings[:100])
    if not warning_rows:
        warning_rows = "<li>No pipeline warnings.</li>"

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dubbing Quality Report</title>
<style>
:root {{ color-scheme: dark; --bg:#0b1020; --card:#121a30; --ink:#f4f7ff; --muted:#aeb9d6; --line:#263252; --accent:#7c9cff; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:linear-gradient(135deg,#080c18,#111a32); color:var(--ink); font:15px/1.55 Inter,Segoe UI,Arial,sans-serif; }}
main {{ max-width:1050px; margin:0 auto; padding:48px 24px 72px; }}
.hero {{ padding:34px; border:1px solid var(--line); border-radius:24px; background:rgba(18,26,48,.88); box-shadow:0 24px 70px rgba(0,0,0,.3); }}
h1 {{ margin:0 0 10px; font-size:38px; letter-spacing:-1px; }}
h2 {{ margin:32px 0 14px; font-size:20px; }}
p,.muted {{ color:var(--muted); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:14px; margin-top:24px; }}
.card {{ padding:18px; border:1px solid var(--line); border-radius:16px; background:var(--card); }}
.label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.09em; }}
.value {{ margin-top:6px; font-size:22px; font-weight:700; overflow-wrap:anywhere; }}
.badge {{ display:inline-block; padding:4px 9px; border-radius:999px; font-size:11px; font-weight:800; letter-spacing:.08em; }}
.pass {{ background:#173d31; color:#72efc0; }} .check {{ background:#4b3515; color:#ffd27a; }}
ul {{ margin:0; padding-left:22px; color:var(--muted); }}
code {{ color:#c8d5ff; }}
footer {{ margin-top:38px; color:var(--muted); font-size:12px; }}
</style>
</head>
<body><main>
<section class="hero">
<div class="label">Idealabs Digital Assignment</div>
<h1>Automated English Dubbing — Quality Report</h1>
<p>{html.escape(source['title'])}</p>
<div class="grid">
  <div class="card"><div class="label">Detected language</div><div class="value">{html.escape(pipeline['detected_language'])}</div></div>
  <div class="card"><div class="label">Speech segments</div><div class="value">{pipeline['segments']}</div></div>
  <div class="card"><div class="label">Recovered segments</div><div class="value">{pipeline['coverage_repaired_segments']}</div></div>
  <div class="card"><div class="label">Processing time</div><div class="value">{pipeline['processing_seconds']:.1f}s</div></div>
  <div class="card"><div class="label">Realtime factor</div><div class="value">{pipeline['realtime_factor']:.3f}×</div></div>
</div>
</section>
<h2>Quality gates</h2>
<div class="grid">
  <div class="card"><div class="label">Playable output</div><div class="value">{_status_badge(gates['output_exists'])}</div></div>
  <div class="card"><div class="label">A/V duration drift</div><div class="value">{gates['duration_drift_seconds']:.3f}s {_status_badge(gates['duration_gate_passed'])}</div></div>
  <div class="card"><div class="label">Median tempo fit</div><div class="value">{gates['median_tempo_factor'] or 'N/A'}×</div></div>
  <div class="card"><div class="label">Timing warnings</div><div class="value">{gates['segments_outside_preferred_tempo_range']}</div></div>
</div>
<h2>Architecture record</h2>
<div class="card">
<p><strong>ASR/translation:</strong> {html.escape(pipeline['whisper_model'])} via faster-whisper</p>
<p><strong>English voice:</strong> {html.escape(pipeline['tts_voice'])}</p>
<p><strong>Background preserved:</strong> {pipeline['background_preserved']}</p>
<p><strong>Content profile:</strong> {html.escape(pipeline['content_profile'])}</p>
<p><strong>Glossary terms:</strong> {html.escape(', '.join(pipeline['glossary_terms']) or 'None')}</p>
<p><strong>Language confidence:</strong> {pipeline['language_probability']:.3f}</p>
</div>
<h2>Warnings requiring human review</h2>
<div class="card"><ul>{warning_rows}</ul></div>
<footer>Generated automatically. Final linguistic and voice-quality review should still be performed by a human.</footer>
</main></body></html>"""
    path.write_text(document, encoding="utf-8")
