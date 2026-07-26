#!/usr/bin/env python3
"""
ascii-video: paste any video URL (YouTube, Twitter/X, TikTok, direct .mp4, etc.)
and watch it play as live ASCII art in your terminal.

Usage:
    python ascii_video.py
    python ascii_video.py "https://youtube.com/watch?v=..."
    python ascii_video.py --width 120 --no-color "https://..."
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

# macOS builds of Python from python.org don't use the system certificate
# store, which makes urllib/yt-dlp fail HTTPS requests with
# CERTIFICATE_VERIFY_FAILED. Point SSL verification at certifi's bundle
# instead, before any network code runs.
try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

import cv2
import numpy as np

# Brightness -> character density ramp (dark to light)
ASCII_RAMP = " .:-=+*#%@"

# Terminal character cells are roughly twice as tall as they are wide,
# so we compress rows by this factor to keep the aspect ratio correct.
CHAR_ASPECT = 0.5


def get_stream_url(source_url: str) -> tuple[str, dict]:
    """Resolve a page URL (YouTube, X, TikTok, etc.) to a direct, playable
    stream URL using yt-dlp, without downloading the file."""
    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "best[ext=mp4]/best",
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(source_url, download=False)
        if info is None or "url" not in info:
            raise RuntimeError(f"yt-dlp could not resolve a stream URL for: {source_url}")
        return info["url"], info


def download_video(source_url: str, dest_dir: str) -> str:
    """Fallback: fully download the video with yt-dlp when direct
    streaming into OpenCV isn't possible (throttled / DRM-ish sources)."""
    import yt_dlp

    out_path = os.path.join(dest_dir, "video.mp4")
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "best[ext=mp4]/best",
        "noplaylist": True,
        "outtmpl": out_path,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.download([source_url])
        if info != 0:
            raise RuntimeError(f"yt-dlp failed to download: {source_url}")
    return out_path


def looks_like_direct_video(url: str) -> bool:
    return url.lower().split("?")[0].endswith((".mp4", ".webm", ".mov", ".m3u8", ".mkv"))


def frame_to_ascii(frame: np.ndarray, cols: int, use_color: bool) -> str:
    """Convert a single BGR frame (numpy array) into a printable ASCII
    string (with ANSI color codes if use_color is True)."""
    h, w = frame.shape[:2]
    rows = max(1, int((h / w) * cols * CHAR_ASPECT))
    small = cv2.resize(frame, (cols, rows), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    ramp_len = len(ASCII_RAMP) - 1

    lines = []
    if use_color:
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        for y in range(rows):
            parts = []
            last_color = None
            for x in range(cols):
                brightness = gray[y, x]
                ch = ASCII_RAMP[int(brightness / 255 * ramp_len)]
                r, g, b = rgb[y, x]
                color = (r, g, b)
                if color != last_color:
                    parts.append(f"\x1b[38;2;{r};{g};{b}m{ch}")
                    last_color = color
                else:
                    parts.append(ch)
            parts.append("\x1b[0m")
            lines.append("".join(parts))
    else:
        for y in range(rows):
            row_chars = (ASCII_RAMP[int(gray[y, x] / 255 * ramp_len)] for x in range(cols))
            lines.append("".join(row_chars))

    return "\n".join(lines)


def play_audio_async(video_path: str):
    """Best-effort audio playback in the background via ffplay, if
    ffmpeg/ffplay is installed on the system. Sync is approximate."""
    if shutil.which("ffplay") is None:
        return None
    return subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", video_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def open_capture(video_source: str) -> cv2.VideoCapture:
    """Open a VideoCapture, forcing the FFMPEG backend. Without this,
    OpenCV's auto-detection can misidentify long, querystring-heavy
    streaming URLs (e.g. googlevideo.com links) as an image-sequence
    pattern (CAP_IMAGES) and fail to open them."""
    cap = cv2.VideoCapture(video_source, cv2.CAP_FFMPEG)
    return cap


def run_player(video_source: str, cols: int, use_color: bool, with_audio: bool):
    cap = open_capture(video_source)
    if not cap.isOpened():
        raise RuntimeError("Could not open video stream for playback.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    frame_delay = 1.0 / fps

    audio_proc = None
    if with_audio and os.path.exists(video_source):
        audio_proc = play_audio_async(video_source)

    sys.stdout.write("\x1b[2J")  # clear screen once
    sys.stdout.write("\x1b[?25l")  # hide cursor

    try:
        next_frame_time = time.perf_counter()
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            ascii_frame = frame_to_ascii(frame, cols, use_color)
            sys.stdout.write("\x1b[H")  # cursor to top-left, no full clear (less flicker)
            sys.stdout.write(ascii_frame)
            sys.stdout.flush()

            next_frame_time += frame_delay
            sleep_time = next_frame_time - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                next_frame_time = time.perf_counter()
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        sys.stdout.write("\x1b[0m\x1b[?25h\n")  # reset color, show cursor
        sys.stdout.flush()
        if audio_proc:
            audio_proc.terminate()


def main():
    parser = argparse.ArgumentParser(description="Play any video URL as ASCII art in your terminal.")
    parser.add_argument("url", nargs="?", help="Video URL (YouTube, X, TikTok, direct .mp4, etc.)")
    parser.add_argument("--width", type=int, default=None, help="Columns of ASCII output (default: terminal width)")
    parser.add_argument("--no-color", action="store_true", help="Render in monochrome instead of color")
    parser.add_argument("--audio", action="store_true", help="Also play audio (requires ffmpeg/ffplay, downloads full file)")
    args = parser.parse_args()

    url = args.url or input("Paste a video URL: ").strip()
    if not url:
        print("No URL provided.")
        sys.exit(1)

    term_cols = args.width or shutil.get_terminal_size((100, 40)).columns

    tmp_dir = None
    video_source = url

    try:
        if not looks_like_direct_video(url):
            print("Resolving video source...")
            try:
                if args.audio:
                    raise RuntimeError("audio requested, need local file")
                stream_url, info = get_stream_url(url)
                video_source = stream_url
                print(f"Streaming: {info.get('title', url)}")
            except Exception:
                print("Direct streaming unavailable, downloading instead...")
                tmp_dir = tempfile.mkdtemp(prefix="ascii_video_")
                video_source = download_video(url, tmp_dir)

        print("Starting playback... (Ctrl+C to quit)")
        time.sleep(0.5)
        try:
            run_player(video_source, term_cols, use_color=not args.no_color, with_audio=args.audio)
        except RuntimeError:
            # Streaming URL didn't open (throttling, missing headers, expired
            # link, etc). Fall back to a full download and retry once.
            if video_source == url:
                raise  # already a direct file URL, nothing else to try
            print("Stream failed to open, downloading full file instead...")
            if tmp_dir is None:
                tmp_dir = tempfile.mkdtemp(prefix="ascii_video_")
            video_source = download_video(url, tmp_dir)
            run_player(video_source, term_cols, use_color=not args.no_color, with_audio=args.audio)
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()