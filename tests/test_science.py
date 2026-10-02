"""Testes unitários do módulo de Artigos Científicos."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from src.dubbing.voice_synthesizer import WordTimestamp
from src.science.ai_curator import AIScienceCurator, _extract_clean_json, _remove_emojis
from src.science.card_renderer import ScienceCardRenderer
from src.science.generator import ScienceGenerationError, ScienceShortsGenerator
from src.science.models import ScienceArticle


class TestScienceModels:
    """Testes dos modelos de dados de ciência."""

    def test_science_article_defaults(self):
        art = ScienceArticle(title="Descoberta sobre envelhecimento celular")
        assert art.title == "Descoberta sobre envelhecimento celular"
        assert art.journal == "Nature Aging"
        assert art.category == "BIOTECNOLOGIA"
        assert art.hook_text == "Descoberta sobre envelhecimento celular"
        assert art.full_script == "Descoberta sobre envelhecimento celular"
        assert "#Shorts" in art.tags


class TestScienceCardRenderer:
    """Testes da geração visual do card científico."""

    def test_render_card_dimensions_and_alpha(self):
        renderer = ScienceCardRenderer()
        article = ScienceArticle(
            title="Cientistas acabaram de reverter a idade celular em mamíferos em mais de quarenta por cento.",
            journal="Nature Aging",
            category="LONGEVIDADE",
            doi="10.1038/s43587-024",
            reads_count="110.2k",
        )
        img = renderer.render_card(article, card_width=960)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGBA"
        assert img.width == 960
        assert img.height > 200

    def test_wrap_text(self):
        renderer = ScienceCardRenderer()
        font = renderer._get_font(30, bold=True)
        long_text = "Um texto de teste com termos científicos como astrofísica, relatividade geral e biotecnologia molecular."
        lines = renderer._wrap_text(long_text, font, max_width=400)
        assert len(lines) >= 2


class TestAIScienceCurator:
    """Testes da IA curadora de ciência e fallbacks."""

    def test_curator_fallback_when_no_api_key(self):
        curator = AIScienceCurator(api_key="")
        article = curator.generate_article()
        assert isinstance(article, ScienceArticle)
        assert len(article.title) > 10
        assert len(article.full_script) > 50
        assert len(article.journal) > 2

    def test_remove_emojis(self):
        dirty = "🔬 DESCOBERTA CIENTÍFICA 🧬 NA NATURE! 🚀"
        cleaned = _remove_emojis(dirty)
        assert "🔬" not in cleaned
        assert "🧬" not in cleaned
        assert "DESCOBERTA CIENTÍFICA NA NATURE!" == cleaned

    def test_extract_clean_json(self):
        raw = '```json\n{"title": "Novo Planeta", "full_script": "Astrônomos acharam...", "journal": "Science"}\n```'
        data = _extract_clean_json(raw)
        assert data["title"] == "Novo Planeta"
        assert data["journal"] == "Science"


class TestScienceShortsGenerator:
    """Testes do gerador de vídeo científico."""

    @patch("src.science.generator.subprocess.run")
    def test_generate_video_flow(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        mock_synth = MagicMock()
        dummy_audio = tmp_path / "voice.mp3"
        dummy_audio.write_bytes(b"dummy mp3 data")
        dummy_words = [
            WordTimestamp("Cientistas", 0.0, 0.4),
            WordTimestamp("descobriram", 0.4, 0.9),
            WordTimestamp("tudo", 0.9, 1.3),
        ]
        mock_synth.synthesize.return_value = (dummy_audio, dummy_words)

        dummy_bg = tmp_path / "dummy_space.mp4"
        dummy_bg.write_bytes(b"0" * 20000)

        out_file = tmp_path / "out" / "science.mp4"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(b"dummy final mp4")

        generator = ScienceShortsGenerator(
            output_dir=tmp_path / "out",
            temp_dir=tmp_path / "tmp",
            voice_synthesizer=mock_synth,
            default_bg_path=dummy_bg,
        )

        article = ScienceArticle(
            title="Avanço histórico na medicina regenerativa",
            full_script="Cientistas descobriram tudo ontem à noite na Nature.",
        )

        result = generator.generate_video(
            article=article,
            background_video=dummy_bg,
            output_filename=out_file,
            voice_mode="male",
        )

        assert result == out_file
        assert mock_synth.synthesize.call_count == 1
        assert mock_run.call_count == 1

    @patch("src.science.generator.subprocess.run")
    @patch("src.science.generator.get_audio_duration_seconds")
    def test_generate_video_dual_voice_flow(self, mock_duration, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mock_duration.return_value = 5.0

        mock_synth = MagicMock()
        dummy_audio = tmp_path / "voice_part.mp3"
        dummy_audio.write_bytes(b"dummy mp3 data")
        mock_synth.synthesize.return_value = (
            dummy_audio,
            [WordTimestamp("Olá", 0.0, 0.5), WordTimestamp("mundo", 0.5, 1.0)],
        )

        dummy_bg = tmp_path / "dummy_space.mp4"
        dummy_bg.write_bytes(b"0" * 20000)

        out_file = tmp_path / "out" / "science_dual.mp4"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(b"dummy final mp4")

        generator = ScienceShortsGenerator(
            output_dir=tmp_path / "out",
            temp_dir=tmp_path / "tmp",
            voice_synthesizer=mock_synth,
            default_bg_path=dummy_bg,
        )

        article = ScienceArticle(
            title="Avanço histórico na medicina regenerativa",
            segments=[
                {"speaker": "male", "text": "Primeira parte com apresentador."},
                {"speaker": "female", "text": "Segunda parte com cientista."},
            ],
        )

        result = generator.generate_video(
            article=article,
            background_video=dummy_bg,
            output_filename=out_file,
            voice_mode="dual",
        )

        assert result == out_file
        assert mock_synth.synthesize.call_count == 2
        # mock_run é chamado para o concat de áudio e para o render final do vídeo
        assert mock_run.call_count >= 2

    def test_resolve_background_thematic(self, tmp_path):
        generator = ScienceShortsGenerator(
            output_dir=tmp_path / "out",
            temp_dir=tmp_path / "tmp",
        )
        bio_bg = generator.resolve_background(category="BIOTECNOLOGIA", topic="Proteína IL-11 e longevidade")
        assert "dna" in bio_bg.name.lower() or bio_bg.exists()

        astro_bg = generator.resolve_background(category="ASTROFÍSICA", topic="Galáxias primitivas do James Webb")
        assert "space" in astro_bg.name.lower() or astro_bg.exists()
