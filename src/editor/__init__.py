"""Módulo de edição e processamento de vídeo do AutoShorts."""

from src.editor.downloader import (
    DownloadError,
    SurgicalDownloader,
    build_ytdlp_args,
    format_time_sec_to_hms,
)
from src.editor.renderer import (
    RenderError,
    VideoRenderer,
    build_ffmpeg_render_command,
    build_filter_complex,
    escape_ffmpeg_filter_path,
)
from src.editor.subtitles import (
    SubtitleError,
    WordTimestamp,
    extract_subtitles_with_whisper,
    format_ass_timestamp,
    generate_ass_subtitle,
)

__all__ = [
    # Downloader
    "DownloadError",
    "SurgicalDownloader",
    "build_ytdlp_args",
    "format_time_sec_to_hms",
    # Subtitles
    "SubtitleError",
    "WordTimestamp",
    "extract_subtitles_with_whisper",
    "format_ass_timestamp",
    "generate_ass_subtitle",
    # Renderer
    "RenderError",
    "VideoRenderer",
    "build_ffmpeg_render_command",
    "build_filter_complex",
    "escape_ffmpeg_filter_path",
]
