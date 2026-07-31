from dubber.models import SpeechSegment


def test_segment_round_trip() -> None:
    segment = SpeechSegment(index=1, start=2.0, end=5.5, text="Hello world.")
    rebuilt = SpeechSegment.from_dict(segment.to_dict())
    assert rebuilt == segment
    assert rebuilt.duration == 3.5
