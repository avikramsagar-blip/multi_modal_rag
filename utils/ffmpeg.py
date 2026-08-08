"""
utils/ffmpeg.py

FFmpeg utilities for video processing.
Requires FFmpeg to be installed as a system binary (available on PATH).
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def extract_audio(video_path: str | Path, output_ext: str = "wav") -> Path:
    """
    Extract the audio track from a video file to a temporary WAV file.
    Returns the Path to the extracted audio file.
    Raises RuntimeError if FFmpeg fails or no audio stream is present.
    """
    video_path = Path(video_path)
    tmp_audio = Path(tempfile.mktemp(suffix=f".{output_ext}"))

    cmd = [
        "ffmpeg",
        "-y",                     # overwrite output
        "-i", str(video_path),
        "-vn",                    # no video
        "-acodec", "pcm_s16le",   # WAV format
        "-ar", "16000",           # 16 kHz sample rate (Whisper optimal)
        "-ac", "1",               # mono
        str(tmp_audio),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Check if failure is due to no audio stream
        if "no audio" in result.stderr.lower() or "does not contain any stream" in result.stderr.lower():
            raise ValueError("Video file has no audio track.")
        raise RuntimeError(
            f"FFmpeg audio extraction failed:\n{result.stderr}"
        )

    if not tmp_audio.exists() or tmp_audio.stat().st_size == 0:
        raise ValueError("Video file has no audio track.")

    return tmp_audio


def extract_keyframes(
    video_path: str | Path,
    interval_sec: int = 10,
    max_frames: int = 30,
) -> list[tuple[float, Image.Image]]:
    """
    Extract keyframes from a video at a fixed interval.

    Returns a list of (timestamp_seconds, PIL.Image) tuples.
    Frames are already converted to RGB.
    """
    video_path = Path(video_path)

    # Use a temp directory for frame PNGs
    with tempfile.TemporaryDirectory() as tmpdir:
        out_pattern = str(Path(tmpdir) / "frame_%04d.png")

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vf", f"fps=1/{interval_sec}",   # 1 frame every N seconds
            "-frames:v", str(max_frames),
            "-q:v", "2",
            out_pattern,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg keyframe extraction failed:\n{result.stderr}"
            )

        frame_files = sorted(Path(tmpdir).glob("frame_*.png"))
        frames: list[tuple[float, Image.Image]] = []

        for i, frame_path in enumerate(frame_files):
            timestamp = i * interval_sec
            img = Image.open(frame_path).convert("RGB")
            # Copy to memory so it survives TemporaryDirectory cleanup
            img_copy = img.copy()
            img.close()
            frames.append((float(timestamp), img_copy))

    return frames


def get_video_duration(video_path: str | Path) -> float:
    """Return video duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed:\n{result.stderr}")
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0
