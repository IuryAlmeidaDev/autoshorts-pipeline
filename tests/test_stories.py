"""Testes unitários do módulo de Histórias do Reddit."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from src.dubbing.voice_synthesizer import WordTimestamp
from src.stories.ai_storyteller import AIStoryteller, _extract_clean_json, _remove_emojis
from src.stories.card_renderer import RedditCardRenderer
from src.stories.generator import RedditStoryGenerator, StoryGenerationError
from src.stories.models import RedditStory


class TestRedditStoryModels:
    """Testes dos modelos de dados de história."""

    def test_reddit_story_defaults(self):
        story = RedditStory(title="Meu vizinho fez algo inacreditável")
        assert story.title == "Meu vizinho fez algo inacreditável"
        assert story.subreddit == "r/desabafos"
        assert story.author == "u/anonimo_1994"
        assert story.upvotes == "14.8k"
        assert story.hook_text == "Meu vizinho fez algo inacreditável"
        assert story.full_script == "Meu vizinho fez algo inacreditável"
        assert "#Shorts" in story.tags


class TestRedditCardRenderer:
    """Testes da geração visual do card do post."""

    def test_render_card_dimensions_and_alpha(self):
        renderer = RedditCardRenderer()
        story = RedditStory(
            title="Descobri o maior segredo do meu chefe porque ele esqueceu o notebook na minha mesa.",
            subreddit="r/desabafos",
            author="u/marcos92",
            upvotes="22.5k",
            comments_count="1.9k",
        )
        img = renderer.render_card(story, card_width=960)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGBA"
        assert img.width == 960
        assert img.height > 200

    def test_wrap_text(self):
        renderer = RedditCardRenderer()
        font = renderer._get_font(30, bold=True)
        long_text = "Esta é uma frase deliberadamente longa criada para testar a quebra automática de linha no card do Reddit."
        lines = renderer._wrap_text(long_text, font, max_width=400)
        assert len(lines) >= 2


class TestAIStoryteller:
    """Testes da geração com IA e fallbacks."""

    def test_storyteller_fallback_when_no_api_key(self):
        storyteller = AIStoryteller(api_key="")
        story = storyteller.generate_story()
        assert isinstance(story, RedditStory)
        assert len(story.title) > 10
        assert len(story.full_script) > 50
        assert story.subreddit.startswith("r/")

    def test_remove_emojis(self):
        dirty = "🔥 UMA HISTÓRIA BIZARRA 😱 NO TRABALHO! 🚀"
        cleaned = _remove_emojis(dirty)
        assert "🔥" not in cleaned
        assert "😱" not in cleaned
        assert "UMA HISTÓRIA BIZARRA NO TRABALHO!" == cleaned

    def test_extract_clean_json(self):
        raw = '```json\n{"title": "História Teste", "full_script": "Roteiro teste"}\n```'
        data = _extract_clean_json(raw)
        assert data["title"] == "História Teste"
        assert data["full_script"] == "Roteiro teste"


class TestRedditStoryGenerator:
    """Testes do gerador de vídeo."""

    @patch("src.stories.generator.subprocess.run")
    def test_generate_video_flow(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        mock_synth = MagicMock()
        dummy_audio = tmp_path / "voice.mp3"
        dummy_audio.write_bytes(b"dummy mp3 data")
        dummy_words = [
            WordTimestamp("Eu", 0.0, 0.3),
            WordTimestamp("descobri", 0.3, 0.8),
            WordTimestamp("tudo", 0.8, 1.2),
        ]
        mock_synth.synthesize.return_value = (dummy_audio, dummy_words)

        dummy_bg = tmp_path / "dummy_bg.mp4"
        dummy_bg.write_bytes(b"0" * 20000)

        out_file = tmp_path / "out" / "story.mp4"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(b"dummy final mp4")

        generator = RedditStoryGenerator(
            output_dir=tmp_path / "out",
            temp_dir=tmp_path / "tmp",
            voice_synthesizer=mock_synth,
            default_bg_path=dummy_bg,
        )

        story = RedditStory(
            title="Meu chefe foi pego no flagra",
            full_script="Eu descobri tudo ontem à noite.",
        )

        result = generator.generate_video(
            story=story,
            background_video=dummy_bg,
            output_filename=out_file,
        )

        assert result == out_file
        assert mock_synth.synthesize.call_count == 1
        assert mock_run.call_count == 1
