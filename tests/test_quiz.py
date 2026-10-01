"""Testes unitários para o módulo de geração de vídeos de Quiz."""

from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

from src.quiz import (
    AIQuizCurator,
    QuizData,
    QuizGenerationError,
    QuizGenerator,
    QuizPipelineOrchestrator,
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


class TestAIQuizCurator:
    """Testes da curadoria por inteligência artificial e fallbacks."""

    def test_curator_fallback_when_no_client(self):
        curator = AIQuizCurator(api_key="")
        quiz = curator.generate_quiz(category="ciencia_e_universo")
        assert len(quiz.questions) == 3
        assert "CIENCIA" in quiz.theme.title.upper()
        for q in quiz.questions:
            assert len(q.options) >= 2
            assert 0 <= q.correct_index < len(q.options)

    def test_remove_emojis_utility(self):
        from src.quiz.ai_curator import _remove_emojis
        text_with_emoji = "🧠 TESTE DE INTELIGÊNCIA ⚡ 💡!"
        cleaned = _remove_emojis(text_with_emoji)
        assert "TESTE DE INTELIGÊNCIA !" == cleaned
        assert "🧠" not in cleaned
        assert "⚡" not in cleaned

    def test_extract_clean_json(self):
        from src.quiz.ai_curator import _extract_clean_json
        raw = "Aqui está seu quiz:\n```json\n{\"theme_title\": \"TESTE\", \"questions\": []}\n```\nObrigado!"
        data = _extract_clean_json(raw)
        assert data is not None
        assert data["theme_title"] == "TESTE"


class TestQuizDatabase:
    """Testes de persistência de histórico de quizzes no SQLite."""

    def test_record_and_get_quiz_history(self, tmp_path):
        from src.database import Database
        db = Database(tmp_path / "test.db")
        assert db.count_quizzes_today() == 0

        # Grava 2 quizzes
        db.record_quiz(
            theme="DESAFIO DE CIENCIA",
            title="TESTE DE CIENCIA #Shorts",
            video_path="/path/to/quiz1.mp4",
            youtube_id="yt_123",
            youtube_url="https://youtube.com/shorts/yt_123",
            status="published",
        )
        db.record_quiz(
            theme="DESAFIO DE ANIMAIS",
            title="TESTE DE ANIMAIS #Shorts",
            video_path="/path/to/quiz2.mp4",
            youtube_id="yt_456",
            youtube_url="https://youtube.com/shorts/yt_456",
            status="published",
        )

        assert db.count_quizzes_today() == 2
        history = db.get_quiz_history(limit=10)
        assert len(history) == 2
        assert history[0]["title"] == "TESTE DE ANIMAIS #Shorts"


class TestQuizPipelineOrchestrator:
    """Testes do orquestrador autônomo (6 vídeos/dia)."""

    def test_run_cycle_success(self, tmp_path):
        from src.database import Database
        from src.publisher.base import PublishResult
        from src.quiz.orchestrator import QuizPipelineOrchestrator

        db = Database(tmp_path / "test_orch.db")
        mock_curator = MagicMock()
        q1 = QuizQuestion("P1?", ["A", "B"], 0)
        mock_curator.generate_quiz.return_value = QuizData("Título Quiz", [q1])

        mock_generator = MagicMock()
        dummy_mp4 = tmp_path / "test.mp4"
        dummy_mp4.write_bytes(b"mp4")
        mock_generator.generate_video.return_value = dummy_mp4

        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = PublishResult(
            success=True,
            platform="youtube_shorts",
            post_id="vid_999",
            url="https://youtube.com/shorts/vid_999",
        )

        orch = QuizPipelineOrchestrator(
            db=db,
            curator=mock_curator,
            generator=mock_generator,
            publisher=mock_publisher,
            daily_limit=6,
        )

        res = orch.run_cycle()
        assert res["success"] is True
        assert res["url"] == "https://youtube.com/shorts/vid_999"
        assert db.count_quizzes_today() == 1

    def test_run_cycle_daily_limit_reached(self, tmp_path):
        from src.database import Database
        from src.quiz.orchestrator import QuizPipelineOrchestrator

        db = Database(tmp_path / "test_orch_limit.db")
        # Força 6 posts já gravados hoje
        for i in range(6):
            db.record_quiz(f"T{i}", f"Title{i}", f"/p/{i}.mp4", f"id_{i}", f"url_{i}")

        orch = QuizPipelineOrchestrator(db=db, daily_limit=6)
        res = orch.run_cycle()
        assert res["success"] is False
        assert res["reason"] == "daily_limit_reached"

    def test_setup_scheduler_background(self, tmp_path):
        from src.database import Database
        from src.quiz.orchestrator import QuizPipelineOrchestrator

        db = Database(tmp_path / "test_orch_sched.db")
        orch = QuizPipelineOrchestrator(db=db)
        scheduler = orch.setup_scheduler(interval_hours=4, run_immediately=False, blocking=False)
        assert scheduler.running
        job = scheduler.get_job("quiz_auto_publisher")
        assert job is not None
        scheduler.shutdown(wait=False)

