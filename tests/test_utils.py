from pathlib import Path

import pytest

from dubber.models import SpeechSegment
from dubber.utils import (
    atempo_chain,
    estimate_tts_rate,
    apply_replacements,
    merge_micro_segments,
    parse_glossary,
    seconds_to_srt_timestamp,
    validate_youtube_url,
    write_srt,
)


def test_validate_youtube_url_accepts_supported_hosts() -> None:
    assert validate_youtube_url("https://youtu.be/abc123") == "https://youtu.be/abc123"
    assert (
        validate_youtube_url("https://www.youtube.com/watch?v=abc123")
        == "https://www.youtube.com/watch?v=abc123"
    )


def test_validate_youtube_url_rejects_other_hosts() -> None:
    with pytest.raises(ValueError):
        validate_youtube_url("https://example.com/video")


def test_atempo_chain_stays_within_compatible_factors() -> None:
    chain = atempo_chain(5.0)
    values = [float(item.split("=")[1]) for item in chain.split(",")]
    assert all(0.5 <= value <= 2.0 for value in values)
    product = 1.0
    for value in values:
        product *= value
    assert product == pytest.approx(5.0)


def test_estimate_tts_rate_is_clamped() -> None:
    assert estimate_tts_rate("one two three four five", 0.1) == "+45%"
    assert estimate_tts_rate("one", 60.0) == "-15%"


def test_merge_micro_segments() -> None:
    segments = [
        SpeechSegment(index=0, start=0.0, end=0.4, text="Hello"),
        SpeechSegment(index=1, start=0.5, end=2.0, text="and welcome"),
        SpeechSegment(index=2, start=3.0, end=5.0, text="Next topic"),
    ]
    merged = merge_micro_segments(segments)
    assert len(merged) == 2
    assert merged[0].start == 0.0
    assert merged[0].end == 2.0
    assert "Hello" in merged[0].text
    assert "welcome" in merged[0].text


def test_srt_output(tmp_path: Path) -> None:
    path = tmp_path / "captions.srt"
    write_srt(path, [SpeechSegment(index=0, start=1.2, end=2.345, text="Hello.")])
    content = path.read_text(encoding="utf-8")
    assert "00:00:01,200 --> 00:00:02,345" in content
    assert seconds_to_srt_timestamp(3661.001) == "01:01:01,001"


def test_glossary_and_replacements() -> None:
    assert parse_glossary("Ram, Sita,ram, Ayodhya") == ["Ram", "Sita", "Ayodhya"]
    segments = [SpeechSegment(index=0, start=0.0, end=1.0, text="Rum returned to ayodia.")]
    count = apply_replacements(segments, {"Rum": "Ram", "ayodia": "Ayodhya"})
    assert count == 2
    assert segments[0].text == "Ram returned to Ayodhya."
