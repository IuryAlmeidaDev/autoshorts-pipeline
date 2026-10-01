"""Testes unitários para o gerador de legendas dinâmicas e renderizador de vídeo vertical (9:16)."""

from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.config import settings
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


class TestWordTimestamp:
    """Testes para o dataclass WordTimestamp."""

    def test_word_timestamp_fields(self):
        wt = WordTimestamp(word="incrível", start=1.25, end=1.85)
        assert wt.word == "incrível"
        assert wt.start == 1.25
        assert wt.end == 1.85


class TestFormatAssTimestamp:
    """Testes para a conversão de segundos em formato ASS (H:MM:SS.cs)."""

    def test_zero_seconds(self):
        assert format_ass_timestamp(0.0) == "0:00:00.00"

    def test_fractional_centiseconds(self):
        assert format_ass_timestamp(1.25) == "0:00:01.25"
        assert format_ass_timestamp(1.256) == "0:00:01.26"

    def test_minutes_and_hours(self):
        assert format_ass_timestamp(65.5) == "0:01:05.50"
        assert format_ass_timestamp(3661.05) == "1:01:01.05"

    def test_negative_clamped_to_zero(self):
        assert format_ass_timestamp(-5.0) == "0:00:00.00"


class TestGenerateAssSubtitle:
    """Testes para a geração de conteúdo de legendas .ass dinâmicas."""

    def test_generate_ass_subtitle_structure(self):
        words = [
            WordTimestamp(word="O", start=0.0, end=0.2),
            WordTimestamp(word="SEGREDO", start=0.2, end=0.6),
            WordTimestamp(word="DO", start=0.6, end=0.8),
            WordTimestamp(word="SUCESSO", start=0.8, end=1.4),
        ]
        ass_content = generate_ass_subtitle(words, words_per_screen=3)

        assert "[Script Info]" in ass_content
        assert "PlayResX: 1080" in ass_content
        assert "PlayResY: 1920" in ass_content
        assert "[V4+ Styles]" in ass_content
        assert "Style: Default" in ass_content
        assert "Arial Black" in ass_content
        assert "[Events]" in ass_content
        assert "Dialogue:" in ass_content
        assert "SEGREDO" in ass_content
        assert "SUCESSO" in ass_content

    def test_generate_ass_subtitle_highlight_tags(self):
        words = [
            WordTimestamp(word="VAMOS", start=1.0, end=1.3),
            WordTimestamp(word="CRESCER", start=1.3, end=1.8),
        ]
        highlight_color = "&H0000FFFF"
        ass_content = generate_ass_subtitle(
            words, words_per_screen=2, highlight_color=highlight_color
        )

        assert highlight_color in ass_content
        assert "0:00:01.00" in ass_content
        assert "0:00:01.30" in ass_content
        assert "0:00:01.80" in ass_content

    def test_generate_ass_subtitle_empty_words(self):
        ass_content = generate_ass_subtitle([])
        assert "[Script Info]" in ass_content
        assert "[V4+ Styles]" in ass_content
        assert "[Events]" in ass_content
        assert "Dialogue:" not in ass_content

    def test_generate_ass_subtitle_custom_styling(self):
        words = [WordTimestamp(word="TESTE", start=0.5, end=1.0)]
        ass_content = generate_ass_subtitle(
            words,
            words_per_screen=1,
            highlight_color="&H0000FF00",
            primary_color="&H00FFFFFF",
            font_size=60,
        )
        assert "&H0000FF00" in ass_content
        assert "60" in ass_content


class TestExtractSubtitlesWithWhisper:
    """Testes para extração de legendas com faster-whisper."""

    def test_file_not_found_raises_error(self, tmp_path):
        non_existent = tmp_path / "does_not_exist.mp4"
        with pytest.raises((FileNotFoundError, SubtitleError)):
            extract_subtitles_with_whisper(non_existent)

    def test_missing_faster_whisper_raises_subtitle_error(self, tmp_path):
        dummy_file = tmp_path / "video.mp4"
        dummy_file.write_bytes(b"dummy")

        with patch.dict(sys.modules, {"faster_whisper": None}):
            with pytest.raises(SubtitleError, match="faster-whisper"):
                extract_subtitles_with_whisper(dummy_file)

    def test_mock_whisper_success(self, tmp_path):
        dummy_file = tmp_path / "video.mp4"
        dummy_file.write_bytes(b"dummy content")

        mock_word1 = MagicMock()
        mock_word1.word = " Olá "
        mock_word1.start = 0.5
        mock_word1.end = 0.9

        mock_word2 = MagicMock()
        mock_word2.word = " mundo "
        mock_word2.start = 1.0
        mock_word2.end = 1.4

        mock_segment = MagicMock()
        mock_segment.words = [mock_word1, mock_word2]

        mock_whisper_model = MagicMock()
        mock_whisper_model.transcribe.return_value = ([mock_segment], MagicMock())

        mock_module = MagicMock()
        mock_module.WhisperModel.return_value = mock_whisper_model

        with patch.dict(sys.modules, {"faster_whisper": mock_module}):
            words = extract_subtitles_with_whisper(dummy_file, model_size="base")
            assert len(words) == 2
            assert words[0].word == "Olá"
            assert words[0].start == 0.5
            assert words[0].end == 0.9
            assert words[1].word == "mundo"


class TestEscapeFfmpegFilterPath:
    """Testes para tratamento de caminhos no filtro de legendas do FFmpeg."""

    def test_windows_path_drive_letter_and_slashes(self):
        win_path = r"C:\Users\User\storage\temp\subtitle.ass"
        escaped = escape_ffmpeg_filter_path(win_path)
        assert "\\" not in escaped.replace(r"\:", "")
        assert "/" in escaped
        assert "C\\:/" in escaped or escaped.startswith("C\\:")

    def test_posix_path(self):
        posix_path = "/tmp/storage/subtitle.ass"
        escaped = escape_ffmpeg_filter_path(posix_path)
        assert escaped == "/tmp/storage/subtitle.ass"


class TestBuildFilterComplex:
    """Testes para geração de strings de filtros FFmpeg (9:16)."""

    def test_smart_crop_basic(self):
        fc = build_filter_complex(mode="smart_crop")
        assert "crop=ih*9/16:ih:(iw-ow)/2:0" in fc
        assert "scale=1080:1920" in fc
        assert "drawtext" not in fc
        assert "ass=" not in fc and "subtitles=" not in fc

    def test_smart_crop_with_hook_text(self):
        fc = build_filter_complex(mode="smart_crop", hook_text="O SEGREDO REVELADO!")
        assert "crop=ih*9/16:ih:(iw-ow)/2:0" in fc
        assert "drawtext=" in fc
        assert "O SEGREDO REVELADO!" in fc

    def test_smart_crop_with_subtitles(self, tmp_path):
        sub_file = tmp_path / "sub.ass"
        sub_file.write_text("dummy", encoding="utf-8")
        fc = build_filter_complex(mode="smart_crop", subtitle_ass_path=sub_file)
        assert "ass=" in fc or "subtitles=" in fc
        assert "sub.ass" in fc

    def test_smart_crop_with_hook_and_subtitles(self, tmp_path):
        sub_file = tmp_path / "sub.ass"
        sub_file.write_text("dummy", encoding="utf-8")
        fc = build_filter_complex(
            mode="smart_crop",
            hook_text="GANCHO VIRAL",
            subtitle_ass_path=sub_file,
        )
        assert "crop=" in fc
        assert "drawtext=" in fc
        assert "ass=" in fc or "subtitles=" in fc

    def test_blurred_background_mode(self):
        fc = build_filter_complex(mode="blurred_background")
        assert "boxblur=" in fc or "boxblur" in fc
        assert "overlay" in fc
        assert "1080" in fc

    def test_blurred_background_with_hook_and_subtitles(self, tmp_path):
        sub_file = tmp_path / "sub.ass"
        sub_file.write_text("dummy", encoding="utf-8")
        fc = build_filter_complex(
            mode="blurred_background",
            hook_text="INCRÍVEL",
            subtitle_ass_path=sub_file,
        )
        assert "boxblur" in fc
        assert "overlay" in fc
        assert "drawtext=" in fc
        assert "ass=" in fc or "subtitles=" in fc

    def test_invalid_mode_raises_value_error(self):
        with pytest.raises(ValueError, match="Modo inválido"):
            build_filter_complex(mode="unsupported_mode")


class TestBuildFfmpegRenderCommand:
    """Testes para montagem do comando CLI do FFmpeg."""

    def test_build_ffmpeg_render_command(self):
        input_vid = Path("/videos/clip.mp4")
        output_vid = Path("/outputs/short.mp4")
        fc = "crop=ih*9/16:ih:(iw-ow)/2:0,scale=1080:1920"

        cmd = build_ffmpeg_render_command(
            input_video=input_vid,
            output_video=output_vid,
            filter_complex=fc,
            ffmpeg_bin="ffmpeg",
        )

        assert isinstance(cmd, list)
        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert "-i" in cmd
        assert str(input_vid) in cmd
        assert "-vf" in cmd
        assert fc in cmd
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert "-preset" in cmd
        assert "fast" in cmd
        assert "-crf" in cmd
        assert "22" in cmd
        assert "-c:a" in cmd
        assert "aac" in cmd
        assert "-b:a" in cmd
        assert "192k" in cmd
        assert "-ar" in cmd
        assert "44100" in cmd
        assert str(output_vid) in cmd


class TestVideoRenderer:
    """Testes de ponta a ponta com mock para a classe VideoRenderer."""

    def test_renderer_initialization_defaults(self, tmp_path):
        renderer = VideoRenderer(temp_dir=tmp_path / "temp", output_dir=tmp_path / "out")
        assert (tmp_path / "temp").exists()
        assert (tmp_path / "out").exists()

    def test_render_clip_input_file_not_found(self, tmp_path):
        renderer = VideoRenderer(temp_dir=tmp_path / "temp", output_dir=tmp_path / "out")
        with pytest.raises(FileNotFoundError):
            renderer.render_clip(
                input_video=tmp_path / "non_existent.mp4",
                hook_text="Gancho",
                words=[],
                output_name="test.mp4",
            )

    @patch("subprocess.run")
    def test_render_clip_success(self, mock_subprocess_run, tmp_path):
        temp_dir = tmp_path / "temp"
        out_dir = tmp_path / "out"
        renderer = VideoRenderer(temp_dir=temp_dir, output_dir=out_dir)

        input_video = tmp_path / "input_clip.mp4"
        input_video.write_bytes(b"dummy video data")

        words = [
            WordTimestamp(word="COMO", start=0.0, end=0.3),
            WordTimestamp(word="VENCER", start=0.3, end=0.8),
        ]

        def side_effect(cmd, **kwargs):
            out_file = out_dir / "clip_final.mp4"
            out_file.write_bytes(b"final mp4 simulated bytes")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_subprocess_run.side_effect = side_effect

        result_path = renderer.render_clip(
            input_video=input_video,
            hook_text="O SEGREDO",
            words=words,
            output_name="clip_final.mp4",
            mode="smart_crop",
        )

        assert result_path.exists()
        assert result_path.name == "clip_final.mp4"
        assert mock_subprocess_run.called

        # Verifica se o arquivo .ass foi criado no temp_dir
        ass_files = list(temp_dir.glob("*.ass"))
        assert len(ass_files) >= 1

    @patch("subprocess.run")
    def test_render_clip_ffmpeg_failure_raises_render_error(
        self, mock_subprocess_run, tmp_path
    ):
        renderer = VideoRenderer(temp_dir=tmp_path / "temp", output_dir=tmp_path / "out")
        input_video = tmp_path / "input.mp4"
        input_video.write_bytes(b"dummy")

        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["ffmpeg"], stderr="Error opening filter"
        )

        with pytest.raises(RenderError, match="Falha na execução do FFmpeg"):
            renderer.render_clip(
                input_video=input_video,
                hook_text="Erro",
                words=[],
                output_name="fail.mp4",
            )

    @patch("subprocess.run")
    def test_render_clip_output_not_created_raises_render_error(
        self, mock_subprocess_run, tmp_path
    ):
        renderer = VideoRenderer(temp_dir=tmp_path / "temp", output_dir=tmp_path / "out")
        input_video = tmp_path / "input.mp4"
        input_video.write_bytes(b"dummy")

        mock_subprocess_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with pytest.raises(RenderError, match="não foi criado"):
            renderer.render_clip(
                input_video=input_video,
                hook_text="Erro",
                words=[],
                output_name="not_created.mp4",
            )
