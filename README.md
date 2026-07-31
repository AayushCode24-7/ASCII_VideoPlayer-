# ascii-video

Paste any video URL and watch it play as live ASCII art in your terminal.

Works with anything [yt-dlp](https://github.com/yt-dlp/yt-dlp) supports (YouTube,
X/Twitter, TikTok, Instagram, Reddit, Vimeo, etc.) as well as direct video
file links (`.mp4`, `.webm`, `.m3u8`...).

## Install

**Option A — straight from GitHub (recommended):**

```bash
pip install git+https://github.com/AayushCode24-7/ASCII_VideoPlayer-.git
```

This installs the `ascii-video` command globally (inside whatever
virtualenv/Python you run it in).

**Option B — clone and install locally:**

```bash
git clone https://github.com/AayushCode24-7/ASCII_VideoPlayer-.git
cd ascii-video
pip install -e .
```

**Option C — no install, just run the script:**

```bash
git clone https://github.com/AayushCode24-7/ASCII_VideoPlayer-.git
cd ascii-video
pip install -r requirements.txt
python ascii_video.py
```

Either way, also install `ffmpeg` (only needed for the `--audio` flag, and
recommended generally since OpenCV's video backend relies on it):
- macOS: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`
- Windows: `choco install ffmpeg` (or download from ffmpeg.org and add to PATH)

## Usage

If installed via Option A or B, just run:

```bash
ascii-video
Paste a video URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Or pass the URL directly:

```bash
ascii-video "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

This gives the video output with sound:

```bash
python -m --width 160 "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --a
```

If running from source without installing (Option C), replace `ascii-video`
with `python ascii_video.py` in the commands above.

Press `Ctrl+C` at any time to stop playback.

### Options

| Flag         | Description                                                        |
|--------------|----------------------------------------------------------------------|
| `--width N`  | Number of ASCII columns (default: your terminal's current width)   |
| `--no-color` | Render in monochrome instead of full-color ANSI                    |
| `--audio`    | Also play audio (downloads the full file first, needs ffmpeg)      |

Example:

```bash
ascii-video --width 160 "https://x.com/someuser/status/12345"
```

## How it works

1. `yt-dlp` resolves the page URL to either a direct streamable video URL
   (no full download needed) or, if that's not possible for the given
   source, downloads the video to a temp file.
2. `OpenCV` reads the video frame by frame.
3. Each frame is downsampled to fit your terminal, converted to grayscale
   for brightness, and mapped to an ASCII density ramp (`" .:-=+*#%@"`).
4. In color mode, each character is also wrapped in a 24-bit ANSI color
   escape matching the original pixel color.
5. Frames are printed to the terminal in place (cursor repositioned, not
   fully cleared) at roughly the source video's frame rate.

## Notes / limitations

- For best results, use a terminal that supports 24-bit ("truecolor") ANSI
  colors (most modern terminals do: iTerm2, Windows Terminal, GNOME
  Terminal, Alacritty, Kitty, etc.).
- Very high-res terminals / large `--width` values will use more CPU per
  frame — reduce `--width` if playback stutters.
- `--audio` sync is best-effort (playback starts roughly alongside the
  video, no frame-accurate sync).
- Some sites throttle or block direct stream URLs; the script automatically
  falls back to downloading the full file in that case.
