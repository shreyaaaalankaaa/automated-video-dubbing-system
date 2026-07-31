from __future__ import annotations

from pathlib import Path
from typing import Callable

from .errors import DownloadError
from .models import VideoMetadata
from .utils import ensure_directory


ProgressCallback = Callable[[str], None]


def download_video(
    url: str,
    output_dir: Path,
    *,
    cookies_from_browser: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> VideoMetadata:
    try:
        import yt_dlp
    except ImportError as exc:
        raise DownloadError("yt-dlp is not installed. Run: pip install -r requirements.txt") from exc

    ensure_directory(output_dir)

    def hook(status: dict) -> None:
        if not progress_callback:
            return
        state = status.get("status")
        if state == "downloading":
            percent = status.get("_percent_str", "").strip()
            speed = status.get("_speed_str", "").strip()
            progress_callback(f"Downloading {percent} {speed}".strip())
        elif state == "finished":
            progress_callback("Download complete; finalizing media container")

    options: dict = {
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(output_dir / "source.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "progress_hooks": [hook],
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "overwrites": True,
    }
    if cookies_from_browser:
        options["cookiesfrombrowser"] = (cookies_from_browser,)

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            prepared = Path(ydl.prepare_filename(info))
    except Exception as exc:
        raise DownloadError(f"Could not download the source video: {exc}") from exc

    candidates = [output_dir / "source.mp4", prepared]
    video_path = next((candidate for candidate in candidates if candidate.exists()), None)
    if video_path is None:
        matches = sorted(output_dir.glob("source.*"))
        video_path = matches[0] if matches else None
    if video_path is None:
        raise DownloadError("yt-dlp completed but the downloaded video file could not be located.")

    return VideoMetadata(
        video_id=str(info.get("id") or "unknown"),
        title=str(info.get("title") or "Untitled video"),
        source_url=url,
        duration=float(info.get("duration") or 0.0),
        uploader=info.get("uploader"),
        upload_date=info.get("upload_date"),
        webpage_url=str(info.get("webpage_url") or url),
        video_path=video_path,
    )
