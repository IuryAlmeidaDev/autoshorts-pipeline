"""Testes unitários para o módulo de geração de vídeos de Quiz."""

from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

from src.quiz import (
    QuizData,
    QuizGenerationError,
    QuizGenerator,
    QuizQuestion,
    QuizTheme,
    QuizFrameRenderer,
    SoundEffectsGenerator,
)


class TestQuizModels:
    """Testes dos modelos de dados do Quiz."""

    def test_quiz_question_valid(self):
        q = QuizQuestion(
            question="Qual é o único mamífero capaz de voar?",
            options=["Esquilo", "Morcego", "Pinguim", "Ornitorrinco"],
            correct_index=1,
            explanation="Morcegos têm asas membranosas.",
        )
        assert q.correct_letter == "B"
        assert q.correct_text == "Morcego"

    def test_quiz_question_empty_raises(self):
        with pytest.raises(ValueError, match="não pode ser vazio"):
            QuizQuestion(
                question="   ",
                options=["A", "B"],
                correct_index=0,
            )

    def test_quiz_question_insufficient_options(self):
        with pytest.raises(ValueError, match="pelo menos duas opções"):
            QuizQuestion(
                question="Qual o número?",
                options=["Apenas Uma"],
                correct_index=0,
            )

    def test_quiz_question_invalid_correct_index(self):
        with pytest.raises(ValueError, match="inválido"):
            QuizQuestion(
                question="Pergunta?",
                options=["Opção 1", "Opção 2"],
                correct_index=5,
            )

    def test_quiz_data_defaults(self):
        q = QuizQuestion(question="P?", options=["A", "B"], correct_index=0)
        data = QuizData(title="Super Quiz", questions=[q])
        assert data.title == "Super Quiz"
        assert len(data.questions) == 1
        assert "Duvido" in data.intro_text
        assert "comentários" in data.outro_text
        assert isinstance(data.theme, QuizTheme)


class TestSoundEffects:
    """Testes de síntese matemática de efeitos sonoros."""

    def test_generate_countdown(self, tmp_path):
        sfx = SoundEffectsGenerator(output_dir=tmp_path)
        wav_path = sfx.generate_countdown(duration_sec=2)
        assert wav_path.exists()
        assert wav_path.stat().st_size > 0
        assert wav_path.name == "countdown_2s.wav"

    def test_generate_ding(self, tmp_path):
        sfx = SoundEffectsGenerator(output_dir=tmp_path)
        ding_path = sfx.generate_ding(duration_sec=0.5)
        assert ding_path.exists()
        assert ding_path.stat().st_size > 0
        assert ding_path.name == "ding_correct.wav"


class TestQuizFrameRenderer:
    """Testes da geração visual e layout dos quadros gráficos."""

    @pytest.fixture
    def renderer(self):
        return QuizFrameRenderer()

    @pytest.fixture
    def sample_question(self):
        return QuizQuestion(
            question="Quantos corações tem um polvo marinho gigante?",
            options=["1 coração", "2 corações", "3 corações", "4 corações"],
            correct_index=2,
            explanation="Dois bombeiam para as brânquias e um para o corpo.",
        )

    def test_get_background(self, renderer):
        bg = renderer.get_background()
        assert bg.size == (1080, 1920)
        assert bg.mode == "RGB"

    def test_render_intro_frame(self, renderer):
        img = renderer.render_intro_frame(total_questions=3)
        assert img.size == (1080, 1920)
        assert img.mode == "RGB"

    def test_render_question_frame_normal_and_countdown(self, renderer, sample_question):
        img = renderer.render_question_frame(
            question=sample_question,
            q_idx=0,
            total_questions=3,
            progress=0.75,
            show_reveal=False,
        )
        assert img.size == (1080, 1920)

    def test_render_question_frame_reveal(self, renderer, sample_question):
        img = renderer.render_question_frame(
            question=sample_question,
            q_idx=0,
            total_questions=3,
            progress=1.0,
            show_reveal=True,
        )
        assert img.size == (1080, 1920)

    def test_render_outro_frame(self, renderer):
        img = renderer.render_outro_frame()
        assert img.size == (1080, 1920)

    def test_wrap_text(self, renderer):
        img = Image.new("RGB", (100, 100))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        font = renderer._get_font(30)
        long_text = "Esta é uma pergunta bastante longa que certamente precisará de quebra de linhas para caber."
        lines = renderer.wrap_text(long_text, font, max_width=400, draw=draw)
        assert len(lines) > 1
        assert " ".join(lines) == long_text


class TestQuizGenerator:
    """Testes da orquestração do vídeo de Quiz."""

    @patch("src.quiz.generator.subprocess.run")
    @patch("src.quiz.generator.subprocess.Popen")
    def test_generate_video_flow(self, mock_popen, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mock_proc = MagicMock()
        import io
        mock_proc.stdin = io.BytesIO()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        mock_synth = MagicMock()
        dummy_audio = tmp_path / "dummy.mp3"
        dummy_audio.write_bytes(b"dummy mp3 data")
        mock_synth.synthesize.return_value = (dummy_audio, [])

        generator = QuizGenerator(
            output_dir=tmp_path / "out",
            temp_dir=tmp_path / "tmp",
            voice_synthesizer=mock_synth,
        )

        q1 = QuizQuestion("Qual o animal mais rápido?", ["Guepardo", "Tartaruga"], 0)
        quiz_data = QuizData(title="Quiz de Animais", questions=[q1])

        out_file = tmp_path / "out" / "final_quiz.mp4"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(b"final mp4 data")

        result = generator.generate_video(quiz_data, output_filename=out_file)
        assert result == out_file
        assert mock_synth.synthesize.call_count >= 3  # Intro, Question 1, Reveal 1, Outro
        assert mock_run.call_count >= 4
        assert mock_popen.call_count == 1  # 1 countdown timer
