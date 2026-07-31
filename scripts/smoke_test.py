from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dubber.media import duration_seconds, mux_video, require_binary  # noqa: E402
from dubber.models import SpeechSegment  # noqa: E402
from dubber.timeline import build_dubbed_timeline  # noqa: E402


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def main() -> None:
    ffmpeg = require_binary("ffmpeg")
    require_binary("ffprobe")
    root = Path(tempfile.mkdtemp(prefix="idealabs-dubber-smoke-"))
    try:
        source = root / "source.mp4"
        first = root / "first.mp3"
        second = root / "second.mp3"
        run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=640x360:d=6",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=48000:cl=mono",
                "-shortest",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(source),
            ]
        )
        run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1.8", str(first)])
        run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=660:duration=2.4", str(second)])

        segments = [
            SpeechSegment(index=0, start=0.5, end=2.0, text="First segment."),
            SpeechSegment(index=1, start=3.0, end=5.2, text="Second segment."),
        ]
        dubbed_audio = root / "dubbed.wav"
        build_dubbed_timeline(
            segments,
            {0: first, 1: second},
            dubbed_audio,
            video_duration=6.0,
            work_dir=root / "work",
            force=True,
        )
        output = root / "output.mp4"
        mux_video(source, dubbed_audio, output)

        audio_duration = duration_seconds(dubbed_audio)
        output_duration = duration_seconds(output)
        assert abs(audio_duration - 6.0) <= 0.05
        assert abs(output_duration - 6.0) <= 0.05
        print("PASS: timeline fitting, audio assembly, and MP4 muxing are operational.")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
