import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.editor.downloader import (
    DownloadError,
    SurgicalDownloader,
    build_ytdlp_args,
    format_time_sec_to_hms,
)


class TestFormatTimeSecToHms:
    """Testes para a função format_time_sec_to_hms."""

    def test_zero_seconds(self):
        assert format_time_sec_to_hms(0) == "00:00:00.000"
        assert format_time_sec_to_hms(0.0) == "00:00:00.000"

    def test_fractional_seconds(self):
        assert format_time_sec_to_hms(65.5) == "00:01:05.500"
        assert format_time_sec_to_hms(84.5) == "00:01:24.500"

    def test_hours_format(self):
        assert format_time_sec_to_hms(3605.0) == "01:00:05.000"
        assert format_time_sec_to_hms(7322.125) == "02:02:02.125"

    def test_negative_seconds_clamped_to_zero(self):
        assert format_time_sec_to_hms(-10.0) == "00:00:00.000"

    def test_millisecond_rounding_precision(self):
        assert format_time_sec_to_hms(0.001) == "00:00:00.001"
        assert format_time_sec_to_hms(59.999) == "00:00:59.999"


class TestBuildYtdlpArgs:
    """Testes para a função build_ytdlp_args."""

    def test_build_ytdlp_args_basic(self):
        video_id = "abc123xyz"
        start_time = 10.0
        end_time = 30.5
        output_path = Path("/tmp/test_clip.mp4")

        args = build_ytdlp_args(
            video_id=video_id,
            start_time=start_time,
            end_time=end_time,
            output_path=output_path,
        )

        assert isinstance(args, list)
        assert "--download-sections" in args
        section_idx = args.index("--download-sections")
        assert args[section_idx + 1] == "*00:00:10.000-00:00:30.500"

        assert "--force-keyframes-at-cuts" in args
        assert "-f" in args
        format_idx = args.index("-f")
        assert "bestvideo" in args[format_idx + 1]

        assert "-o" in args
        output_idx = args.index("-o")
        assert args[output_idx + 1] == str(output_path)

        expected_url = f"https://www.youtube.com/watch?v={video_id}"
        assert expected_url in args
        assert args[-1] == expected_url

    def test_build_ytdlp_args_custom_format(self):
        custom_format = "mp4"
        args = build_ytdlp_args(
            video_id="video789",
            start_time=60.0,
            end_time=120.0,
            output_path="custom/out.mp4",
            format_spec=custom_format,
        )
        assert "-f" in args
        assert args[args.index("-f") + 1] == custom_format
        assert args[args.index("-o") + 1] == "custom/out.mp4"

    def test_build_ytdlp_args_invalid_video_id(self):
        with pytest.raises(ValueError, match="video_id cannot be empty"):
            build_ytdlp_args("", 0.0, 10.0, "out.mp4")

        with pytest.raises(ValueError, match="video_id cannot be empty"):
            build_ytdlp_args("   ", 0.0, 10.0, "out.mp4")

    def test_build_ytdlp_args_invalid_time_range(self):
        with pytest.raises(ValueError, match="start_time"):
            build_ytdlp_args("vid123", -1.0, 10.0, "out.mp4")

        with pytest.raises(ValueError, match="greater than start_time"):
            build_ytdlp_args("vid123", 20.0, 10.0, "out.mp4")

        with pytest.raises(ValueError, match="greater than start_time"):
            build_ytdlp_args("vid123", 10.0, 10.0, "out.mp4")


class TestSurgicalDownloader:
    """Testes para a classe SurgicalDownloader."""

    def test_init_default_and_custom_dir(self, tmp_path):
        dl_default = SurgicalDownloader()
        assert dl_default.temp_dir.exists()

        custom_dir = tmp_path / "custom_temp"
        dl_custom = SurgicalDownloader(temp_dir=custom_dir)
        assert dl_custom.temp_dir == custom_dir
        assert custom_dir.exists()

    def test_download_segment_success_subprocess(self, tmp_path):
        downloader = SurgicalDownloader(temp_dir=tmp_path)
        video_id = "test_vid_123"
        start_time = 15.0
        end_time = 45.0

        def fake_subprocess_run(cmd, **kwargs):
            # Encontra o caminho de saída nos argumentos CLI
            out_idx = cmd.index("-o")
            dest = Path(cmd[out_idx + 1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"fake mp4 video bytes")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="Downloaded section", stderr="")

        with patch("subprocess.run", side_effect=fake_subprocess_run) as mock_run:
            result_path = downloader.download_segment(video_id, start_time, end_time)

            assert mock_run.called
            assert result_path.exists()
            assert result_path.stat().st_size > 0
            assert result_path.name == f"{video_id}_{int(start_time)}_{int(end_time)}.mp4"

            called_cmd = mock_run.call_args[0][0]
            assert "--download-sections" in called_cmd
            assert "--force-keyframes-at-cuts" in called_cmd

    def test_download_segment_custom_filename(self, tmp_path):
        downloader = SurgicalDownloader(temp_dir=tmp_path)
        custom_name = "custom_clip_name.mp4"

        def fake_subprocess_run(cmd, **kwargs):
            out_idx = cmd.index("-o")
            dest = Path(cmd[out_idx + 1])
            dest.write_bytes(b"fake data")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=fake_subprocess_run):
            result = downloader.download_segment("vid1", 0.0, 10.0, output_filename=custom_name)
            assert result.name == custom_name
            assert result.parent == tmp_path
            assert result.exists()

    def test_download_segment_absolute_output_filename(self, tmp_path):
        downloader = SurgicalDownloader(temp_dir=tmp_path / "ignored")
        abs_output = tmp_path / "absolute_dir" / "abs_clip.mp4"

        def fake_subprocess_run(cmd, **kwargs):
            out_idx = cmd.index("-o")
            dest = Path(cmd[out_idx + 1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"video bytes")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=fake_subprocess_run):
            result = downloader.download_segment("vid1", 0.0, 10.0, output_filename=str(abs_output))
            assert result == abs_output
            assert result.exists()

    def test_download_segment_timeout_error(self, tmp_path):
        downloader = SurgicalDownloader(temp_dir=tmp_path, timeout=5)

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="yt-dlp", timeout=5)):
            with pytest.raises(DownloadError, match="timed out"):
                downloader.download_segment("vid1", 10.0, 20.0)

    def test_download_segment_private_video_error(self, tmp_path):
        downloader = SurgicalDownloader(temp_dir=tmp_path)

        mock_proc = subprocess.CompletedProcess(
            args=["yt-dlp"],
            returncode=1,
            stdout="",
            stderr="ERROR: [youtube] vid1: Private video. Sign in if you've been granted access to this video",
        )

        with patch("subprocess.run", return_value=mock_proc):
            with pytest.raises(DownloadError, match="private|inaccessible"):
                downloader.download_segment("vid1", 10.0, 20.0)

    def test_download_segment_nonzero_exit_code_error(self, tmp_path):
        downloader = SurgicalDownloader(temp_dir=tmp_path)

        mock_proc = subprocess.CompletedProcess(
            args=["yt-dlp"],
            returncode=1,
            stdout="",
            stderr="ERROR: [youtube] vid1: Video unavailable",
        )

        with patch("subprocess.run", return_value=mock_proc):
            with pytest.raises(DownloadError, match="exit code 1"):
                downloader.download_segment("vid1", 10.0, 20.0)

    def test_download_segment_executable_not_found(self, tmp_path):
        downloader = SurgicalDownloader(temp_dir=tmp_path, executable="non_existent_yt_dlp_binary")

        with patch("subprocess.run", side_effect=FileNotFoundError("Executable not found")):
            with pytest.raises(DownloadError, match="not found"):
                downloader.download_segment("vid1", 10.0, 20.0)

    def test_download_segment_output_file_not_created(self, tmp_path):
        downloader = SurgicalDownloader(temp_dir=tmp_path)

        # Retorna sucesso mas não escreve o arquivo no disco
        mock_proc = subprocess.CompletedProcess(
            args=["yt-dlp"],
            returncode=0,
            stdout="Fake success",
            stderr="",
        )

        with patch("subprocess.run", return_value=mock_proc):
            with pytest.raises(DownloadError, match="was not created or is empty"):
                downloader.download_segment("vid1", 10.0, 20.0)

    def test_download_segment_output_file_empty_zero_bytes(self, tmp_path):
        downloader = SurgicalDownloader(temp_dir=tmp_path)

        def fake_subprocess_run(cmd, **kwargs):
            out_idx = cmd.index("-o")
            dest = Path(cmd[out_idx + 1])
            dest.write_bytes(b"")  # arquivo com 0 bytes
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=fake_subprocess_run):
            with pytest.raises(DownloadError, match="was not created or is empty"):
                downloader.download_segment("vid1", 10.0, 20.0)

    def test_download_segment_invalid_time_args(self, tmp_path):
        downloader = SurgicalDownloader(temp_dir=tmp_path)
        with pytest.raises(ValueError):
            downloader.download_segment("vid1", -5.0, 10.0)

        with pytest.raises(ValueError):
            downloader.download_segment("vid1", 20.0, 10.0)

    def test_download_segment_ytdlp_api_mode_success(self, tmp_path):
        downloader = SurgicalDownloader(temp_dir=tmp_path, method="api")
        output_file = tmp_path / "api_clip.mp4"

        mock_ydl_instance = MagicMock()

        def fake_download(urls):
            output_file.write_bytes(b"mock video data via api")

        mock_ydl_instance.download.side_effect = fake_download
        mock_ydl_instance.__enter__.return_value = mock_ydl_instance

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl_instance) as mock_ydl_class:
            result = downloader.download_segment("vid_api_1", 10.0, 20.0, output_filename=str(output_file))

            assert mock_ydl_class.called
            ydl_opts = mock_ydl_class.call_args[0][0]
            assert "download_ranges" in ydl_opts
            assert ydl_opts.get("force_keyframes_at_cuts") is True
            assert result.exists()
            assert result.stat().st_size > 0

    def test_download_segment_ytdlp_api_mode_error(self, tmp_path):
        downloader = SurgicalDownloader(temp_dir=tmp_path, method="api")

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.download.side_effect = Exception("API connection dropped")
        mock_ydl_instance.__enter__.return_value = mock_ydl_instance

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl_instance):
            with pytest.raises(DownloadError, match="API connection dropped"):
                downloader.download_segment("vid_api_1", 10.0, 20.0)
