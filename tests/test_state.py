from pathlib import Path

from dubber.state import RunState


def test_run_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = RunState.load(path)
    assert not state.completed("download")

    state.mark("download", video_path="source.mp4")
    loaded = RunState.load(path)
    assert loaded.completed("download")
    assert loaded.stages["download"]["video_path"] == "source.mp4"
