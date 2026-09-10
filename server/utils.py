import logging
import subprocess
from pathlib import Path
from config import ALLOWED_EXTENSIONS, THUMBNAILS_DIR, VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)


def allowed_file(filename: str) -> bool:
    """Check if the uploaded file has a permitted extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def is_video(filename: str) -> bool:
    """Check if the filename has a video extension."""
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    return ext in VIDEO_EXTENSIONS


def get_thumbnail_path(media_id: str) -> Path:
    """Get the path to the thumbnail file for a media asset."""
    return THUMBNAILS_DIR / f"{media_id}.jpg"


def generate_video_thumbnail(video_path: Path, output_thumbnail_path: Path) -> bool:
    """Generate a snapshot thumbnail JPG from a video using ffmpeg."""
    try:
        output_thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        # Snapshot at 1.0 second, scale width to 480 maintaining aspect ratio
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", "00:00:01",
            "-i", str(video_path),
            "-frames:v", "1",
            "-update", "1",
            "-vf", "scale=480:-1",
            "-q:v", "2",
            str(output_thumbnail_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        if res.returncode == 0 and output_thumbnail_path.exists() and output_thumbnail_path.stat().st_size > 0:
            return True

        # Fallback for short clips (< 1s)
        cmd_fallback = [
            "ffmpeg",
            "-y",
            "-ss", "00:00:00.1",
            "-i", str(video_path),
            "-frames:v", "1",
            "-update", "1",
            "-vf", "scale=480:-1",
            "-q:v", "2",
            str(output_thumbnail_path),
        ]
        res = subprocess.run(cmd_fallback, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        return res.returncode == 0 and output_thumbnail_path.exists() and output_thumbnail_path.stat().st_size > 0
    except Exception as e:
        logger.error(f"Error generating video thumbnail for {video_path}: {e}")
        return False


def delete_thumbnail(media_id: str) -> None:
    """Delete snapshot thumbnail from disk if it exists."""
    thumb_path = get_thumbnail_path(media_id)
    if thumb_path.exists():
        try:
            thumb_path.unlink()
        except OSError as e:
            logger.warning(f"Failed to delete thumbnail {thumb_path}: {e}")
