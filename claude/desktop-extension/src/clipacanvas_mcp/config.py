"""Environment-based configuration for the Clip.A.Canvas MCP server."""

from __future__ import annotations

import os
from pathlib import Path


def _resolve_ffmpeg() -> str:
    """Resolve FFmpeg executable path."""
    env = os.environ.get("CLIPACANVAS_FFMPEG_EXE")
    if env:
        return env

    # Try to find bundled FFmpeg relative to this package
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    # Fall back to system PATH
    import shutil

    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if ffmpeg:
        return ffmpeg

    raise RuntimeError(
        "FFmpeg not found. Set CLIPACANVAS_FFMPEG_EXE or install imageio-ffmpeg."
    )


# ---------------------------------------------------------------------------
# Config singleton (lazily populated on first access)
# ---------------------------------------------------------------------------


class Config:
    ffmpeg_exe: str = os.environ.get("CLIPACANVAS_FFMPEG_EXE", "")
    browsers_path: str = os.environ.get("CLIPACANVAS_BROWSERS_PATH", "")
    max_duration: float = float(os.environ.get("CLIPACANVAS_MAX_DURATION", "12"))
    default_width: int = int(os.environ.get("CLIPACANVAS_DEFAULT_WIDTH", "540"))
    default_height: int = int(os.environ.get("CLIPACANVAS_DEFAULT_HEIGHT", "960"))
    default_bitrate: str = os.environ.get("CLIPACANVAS_DEFAULT_BITRATE", "5M")
    default_frame_rate: int = int(os.environ.get("CLIPACANVAS_DEFAULT_FRAME_RATE", "60"))

    def __init__(self) -> None:
        object.__setattr__(self, "ffmpeg_exe", _resolve_ffmpeg())
        browsers = os.environ.get("CLIPACANVAS_BROWSERS_PATH", "")
        if browsers:
            object.__setattr__(self, "browsers_path", browsers)
        object.__setattr__(
            self,
            "max_duration",
            float(os.environ.get("CLIPACANVAS_MAX_DURATION", "12")),
        )
        object.__setattr__(
            self,
            "default_width",
            int(os.environ.get("CLIPACANVAS_DEFAULT_WIDTH", "540")),
        )
        object.__setattr__(
            self,
            "default_height",
            int(os.environ.get("CLIPACANVAS_DEFAULT_HEIGHT", "960")),
        )
        object.__setattr__(
            self,
            "default_bitrate",
            os.environ.get("CLIPACANVAS_DEFAULT_BITRATE", "5M"),
        )
        object.__setattr__(
            self,
            "default_frame_rate",
            int(os.environ.get("CLIPACANVAS_DEFAULT_FRAME_RATE", "60")),
        )


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
