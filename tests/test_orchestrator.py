"""Testes unitários e de integração para o PipelineOrchestrator e CLI."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.config import Settings
from src.database import Database
from src.models import Channel, Clip, Post, Video
from src.scout.monitor import Episode
from src.curator.transcript import TranscriptSegment
from src.curator.analyzer import ClipMetadata
from src.editor.subtitles import WordTimestamp
from src.publisher.base import BasePublisher, PublishResult
from src.orchestrator import PipelineOrchestrator


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    """Configurações temporárias para testes isolados."""
    storage_dir = tmp_path / "storage"
    temp_dir = storage_dir / "temp"
    output_dir = storage_dir / "output"
    db_path = storage_dir / "test_pipeline.db"
    return Settings(
        BASE_DIR=tmp_path,
        STORAGE_DIR=storage_dir,
        TEMP_DIR=temp_dir,
        OUTPUT_DIR=output_dir,
        DB_PATH=db_path,
        POLL_INTERVAL_MINUTES=30,
        POST_INTERVAL_HOURS=2,
        MAX_CLIPS_PER_VIDEO=2,
        MIN_CLIP_DURATION=30,
        MAX_CLIP_DURATION=60,
    )


@pytest.fixture
def memory_db() -> Database:
    """Banco de dados SQLite em memória para testes velozes."""
    db = Database(":memory:")
    db.init_db()
    return db


@pytest.fixture
def mock_publisher() -> BasePublisher:
    """Mock genérico de publicador que retorna sucesso."""
    pub = MagicMock(spec=BasePublisher)
    pub.publish.return_value = PublishResult(
        success=True,
        platform="mock_platform",
        post_id="post_999",
        url="https://social.test/post/999",
    )
    return pub


class TestOrchestratorInit:
    def test_default_initialization(self, mock_settings: Settings, memory_db: Database):
        """Verifica a inicialização padrão com todos os componentes acoplados."""
        orchestrator = PipelineOrchestrator(settings=mock_settings, db=memory_db)
        assert orchestrator.settings == mock_settings
        assert orchestrator.db == memory_db
        assert orchestrator.scout is not None
        assert orchestrator.transcript_fetcher is not None
        assert orchestrator.curator is not None
        assert orchestrator.downloader is not None
        assert orchestrator.renderer is not None
        assert isinstance(orchestrator.publishers, dict)

    def test_custom_dependency_injection(self, mock_settings: Settings, memory_db: Database):
        """Verifica a injeção personalizada de dependências e publicadores."""
        custom_scout = MagicMock()
        custom_curator = MagicMock()
        custom_pub = MagicMock(spec=BasePublisher)
        publishers = {"custom": custom_pub}

        orchestrator = PipelineOrchestrator(
            settings=mock_settings,
            db=memory_db,
            publishers=publishers,
            scout=custom_scout,
            curator=custom_curator,
        )
        assert orchestrator.scout == custom_scout
        assert orchestrator.curator == custom_curator
        assert orchestrator.publishers["custom"] == custom_pub


class TestProcessEpisode:
    def test_process_episode_success(
        self, mock_settings: Settings, memory_db: Database, tmp_path: Path
    ):
        """Testa o fluxo completo de processamento de um episódio até o agendamento de posts."""
        episode = Episode(
            video_id="yt_vid_123",
            channel_id="UC_CANAL",
            title="Episódio Histórico",
        )

        # Mocks dos componentes
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_transcript.return_value = [
            TranscriptSegment(text="Olá mundo do podcast", start=10.0, duration=5.0),
            TranscriptSegment(text="Momento incrível agora", start=15.0, duration=15.0),
        ]
        mock_fetcher.format_transcript_with_timestamps.return_value = "[00:10 - 00:30] Transcrição..."

        mock_curator = MagicMock()
        mock_curator.analyze_transcript.return_value = [
            ClipMetadata(
                start_time=10.0,
                end_time=30.0,
                hook_title="REVELAÇÃO CHOCANTE!",
                viral_score=9.8,
            )
        ]

        raw_video_path = tmp_path / "storage" / "temp" / "yt_vid_123_10_30.mp4"
        raw_video_path.parent.mkdir(parents=True, exist_ok=True)
        raw_video_path.write_bytes(b"dummy_raw_video")

        mock_downloader = MagicMock()
        mock_downloader.download_segment.return_value = raw_video_path

        rendered_video_path = tmp_path / "storage" / "output" / "clip_1.mp4"
        rendered_video_path.parent.mkdir(parents=True, exist_ok=True)
        rendered_video_path.write_bytes(b"dummy_rendered_video")

        mock_renderer = MagicMock()
        mock_renderer.render_clip.return_value = rendered_video_path

        orchestrator = PipelineOrchestrator(
            settings=mock_settings,
            db=memory_db,
            transcript_fetcher=mock_fetcher,
            curator=mock_curator,
            downloader=mock_downloader,
            renderer=mock_renderer,
        )

        with patch("src.orchestrator.extract_subtitles_with_whisper") as mock_whisper:
            mock_whisper.return_value = [
                WordTimestamp(word="Olá", start=10.0, end=10.5),
                WordTimestamp(word="mundo", start=10.5, end=11.0),
            ]
            clips = orchestrator.process_episode(episode)

        assert len(clips) == 1
        clip = clips[0]
        assert clip.hook_title == "REVELAÇÃO CHOCANTE!"
        assert clip.viral_score == 9.8
        assert clip.file_path == str(rendered_video_path)

        # Valida que o vídeo foi gravado no banco
        assert memory_db.is_video_processed("yt_vid_123") is True

        # Valida que as postagens para as 4 plataformas foram agendadas
        pending = memory_db.get_pending_posts()
        assert len(pending) == 4
        platforms = {p.platform for p in pending}
        assert {"youtube_shorts", "tiktok", "instagram_reels", "kwai"}.issubset(platforms)

    def test_process_episode_no_transcript(
        self, mock_settings: Settings, memory_db: Database
    ):
        """Garante que vídeos sem transcrição são marcados como processados sem gerar cortes."""
        episode = Episode(
            video_id="yt_no_subs",
            channel_id="UC_CANAL",
            title="Sem Legendas",
        )
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_transcript.return_value = []

        orchestrator = PipelineOrchestrator(
            settings=mock_settings,
            db=memory_db,
            transcript_fetcher=mock_fetcher,
        )

        clips = orchestrator.process_episode(episode)
        assert clips == []
        assert memory_db.is_video_processed("yt_no_subs") is True
        assert len(memory_db.get_pending_posts()) == 0

    def test_process_episode_no_viral_moments_found(
        self, mock_settings: Settings, memory_db: Database
    ):
        """Garante que quando a IA não identifica ganchos virais nenhum corte é criado."""
        episode = Episode(
            video_id="yt_boring",
            channel_id="UC_CANAL",
            title="Vídeo Monótono",
        )
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_transcript.return_value = [
            TranscriptSegment(text="Conversa morna", start=0.0, duration=10.0)
        ]
        mock_fetcher.format_transcript_with_timestamps.return_value = "[00:00 - 00:10] Conversa morna"

        mock_curator = MagicMock()
        mock_curator.analyze_transcript.return_value = []

        orchestrator = PipelineOrchestrator(
            settings=mock_settings,
            db=memory_db,
            transcript_fetcher=mock_fetcher,
            curator=mock_curator,
        )

        clips = orchestrator.process_episode(episode)
        assert clips == []
        assert memory_db.is_video_processed("yt_boring") is True

    def test_process_episode_whisper_failure_fallback(
        self, mock_settings: Settings, memory_db: Database, tmp_path: Path
    ):
        """Testa que falhas de extração de legendas com Whisper não abortam a renderização."""
        episode = Episode(
            video_id="yt_whisper_err",
            channel_id="UC_CANAL",
            title="Erro no Whisper",
        )
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_transcript.return_value = [
            TranscriptSegment(text="Áudio teste", start=0.0, duration=10.0)
        ]
        mock_fetcher.format_transcript_with_timestamps.return_value = "Texto"

        mock_curator = MagicMock()
        mock_curator.analyze_transcript.return_value = [
            ClipMetadata(start_time=0.0, end_time=30.0, hook_title="Fallback Whisper", viral_score=8.0)
        ]

        raw_path = tmp_path / "raw.mp4"
        raw_path.write_bytes(b"raw")
        mock_downloader = MagicMock()
        mock_downloader.download_segment.return_value = raw_path

        rendered_path = tmp_path / "rendered.mp4"
        rendered_path.write_bytes(b"rendered")
        mock_renderer = MagicMock()
        mock_renderer.render_clip.return_value = rendered_path

        orchestrator = PipelineOrchestrator(
            settings=mock_settings,
            db=memory_db,
            transcript_fetcher=mock_fetcher,
            curator=mock_curator,
            downloader=mock_downloader,
            renderer=mock_renderer,
        )

        with patch("src.orchestrator.extract_subtitles_with_whisper", side_effect=RuntimeError("Whisper OOM")):
            clips = orchestrator.process_episode(episode)

        assert len(clips) == 1
        # renderer foi chamado com words=None como fallback
        mock_renderer.render_clip.assert_called_once()
        assert mock_renderer.render_clip.call_args.kwargs.get("words") is None


class TestRunScoutCycle:
    def test_run_scout_cycle_processes_multiple(
        self, mock_settings: Settings, memory_db: Database
    ):
        """Verifica a varredura e processamento sequencial de episódios descobertos."""
        ep1 = Episode(video_id="v1", channel_id="c1", title="Ep 1")
        ep2 = Episode(video_id="v2", channel_id="c1", title="Ep 2")

        mock_scout = MagicMock()
        mock_scout.scan_all_channels.return_value = [ep1, ep2]

        orchestrator = PipelineOrchestrator(
            settings=mock_settings,
            db=memory_db,
            scout=mock_scout,
        )

        with patch.object(orchestrator, "process_episode") as mock_proc:
            mock_proc.return_value = [MagicMock(spec=Clip)]
            count = orchestrator.run_scout_cycle()

        assert count == 2
        assert mock_proc.call_count == 2

    def test_run_scout_cycle_handles_episode_error_gracefully(
        self, mock_settings: Settings, memory_db: Database
    ):
        """Garante que erro em um episódio não interrompe os demais."""
        ep1 = Episode(video_id="v_err", channel_id="c1", title="Erro")
        ep2 = Episode(video_id="v_ok", channel_id="c1", title="Sucesso")

        mock_scout = MagicMock()
        mock_scout.scan_all_channels.return_value = [ep1, ep2]

        orchestrator = PipelineOrchestrator(
            settings=mock_settings,
            db=memory_db,
            scout=mock_scout,
        )

        with patch.object(orchestrator, "process_episode") as mock_proc:
            mock_proc.side_effect = [Exception("Download falhou"), [MagicMock(spec=Clip)]]
            count = orchestrator.run_scout_cycle()

        assert count == 1
        assert mock_proc.call_count == 2


class TestRunPublishingCycle:
    def test_publishing_cycle_success_and_cleanup(
        self, mock_settings: Settings, memory_db: Database, tmp_path: Path
    ):
        """Verifica publicação com sucesso em múltiplas plataformas e exclusão de arquivo temporário."""
        clip_file = tmp_path / "clip_cleanup.mp4"
        clip_file.write_bytes(b"content")

        video = memory_db.mark_video_processed("vid_pub", "ch_1", "Video Pub")
        clip = memory_db.save_clip(
            video_id=video.id,
            start_time=0.0,
            end_time=30.0,
            hook_title="Gancho Top",
            viral_score=9.0,
            file_path=str(clip_file),
            status="ready",
        )

        post1 = memory_db.create_post(clip_id=clip.id, platform="youtube_shorts")
        post2 = memory_db.create_post(clip_id=clip.id, platform="tiktok")

        mock_yt = MagicMock(spec=BasePublisher)
        mock_yt.publish.return_value = PublishResult(success=True, platform="youtube_shorts", post_id="yt_1")

        mock_tt = MagicMock(spec=BasePublisher)
        mock_tt.publish.return_value = PublishResult(success=True, platform="tiktok", post_id="tt_1")

        publishers = {
            "youtube_shorts": mock_yt,
            "tiktok": mock_tt,
        }

        orchestrator = PipelineOrchestrator(
            settings=mock_settings,
            db=memory_db,
            publishers=publishers,
        )

        assert clip_file.exists() is True
        posted_count = orchestrator.run_publishing_cycle()

        assert posted_count == 2
        # Posts marcados como 'posted'
        assert len(memory_db.get_pending_posts()) == 0

        # Arquivo temporário de vídeo removido porque todos os posts foram concluídos
        assert clip_file.exists() is False

    def test_publishing_cycle_partial_posts_keeps_clip_file(
        self, mock_settings: Settings, memory_db: Database, tmp_path: Path
    ):
        """Garante que o arquivo de vídeo não é apagado enquanto houver posts pendentes para o clipe."""
        clip_file = tmp_path / "clip_partial.mp4"
        clip_file.write_bytes(b"content")

        video = memory_db.mark_video_processed("vid_part", "ch_1", "Video Part")
        clip = memory_db.save_clip(
            video_id=video.id,
            start_time=0.0,
            end_time=30.0,
            hook_title="Gancho Parcial",
            viral_score=9.0,
            file_path=str(clip_file),
            status="ready",
        )

        memory_db.create_post(clip_id=clip.id, platform="youtube_shorts")
        memory_db.create_post(clip_id=clip.id, platform="tiktok")

        # Configura publicador apenas para youtube_shorts
        mock_yt = MagicMock(spec=BasePublisher)
        mock_yt.publish.return_value = PublishResult(success=True, platform="youtube_shorts", post_id="yt_1")

        publishers = {"youtube_shorts": mock_yt}

        orchestrator = PipelineOrchestrator(
            settings=mock_settings,
            db=memory_db,
            publishers=publishers,
        )

        posted_count = orchestrator.run_publishing_cycle()
        assert posted_count == 1

        # Ainda resta 1 pendente (tiktok)
        pending = memory_db.get_pending_posts()
        assert len(pending) == 1
        assert pending[0].platform == "tiktok"

        # Arquivo NÃO deve ser apagado
        assert clip_file.exists() is True

    def test_publishing_cycle_failure_records_error(
        self, mock_settings: Settings, memory_db: Database, tmp_path: Path
    ):
        """Verifica registro do erro no banco quando o publicador falha."""
        clip_file = tmp_path / "clip_fail.mp4"
        clip_file.write_bytes(b"content")

        video = memory_db.mark_video_processed("vid_fail", "ch_1", "Video Fail")
        clip = memory_db.save_clip(
            video_id=video.id,
            start_time=0.0,
            end_time=30.0,
            hook_title="Gancho Fail",
            viral_score=9.0,
            file_path=str(clip_file),
            status="ready",
        )

        post = memory_db.create_post(clip_id=clip.id, platform="instagram_reels")

        mock_ig = MagicMock(spec=BasePublisher)
        mock_ig.publish.return_value = PublishResult(
            success=False,
            platform="instagram_reels",
            error="Meta Graph API rate limit",
        )

        publishers = {"instagram_reels": mock_ig}

        orchestrator = PipelineOrchestrator(
            settings=mock_settings,
            db=memory_db,
            publishers=publishers,
        )

        posted_count = orchestrator.run_publishing_cycle()
        assert posted_count == 0

        # Post atualizado para 'failed'
        assert len(memory_db.get_pending_posts()) == 0
        with memory_db.get_connection() as conn:
            row = conn.execute("SELECT status, error_log FROM posts WHERE id = ?", (post.id,)).fetchone()
            assert row["status"] == "failed"
            assert "rate limit" in row["error_log"]

    def test_publishing_cycle_missing_video_file_fails(
        self, mock_settings: Settings, memory_db: Database
    ):
        """Verifica que postagem com arquivo ausente é marcada como falha."""
        video = memory_db.mark_video_processed("vid_missing", "ch_1", "Missing")
        clip = memory_db.save_clip(
            video_id=video.id,
            start_time=0.0,
            end_time=30.0,
            hook_title="Hook",
            viral_score=8.0,
            file_path="storage/non_existent_file.mp4",
            status="ready",
        )
        post = memory_db.create_post(clip_id=clip.id, platform="youtube_shorts")

        mock_yt = MagicMock(spec=BasePublisher)
        orchestrator = PipelineOrchestrator(
            settings=mock_settings,
            db=memory_db,
            publishers={"youtube_shorts": mock_yt},
        )

        posted_count = orchestrator.run_publishing_cycle()
        assert posted_count == 0
        mock_yt.publish.assert_not_called()

        with memory_db.get_connection() as conn:
            row = conn.execute("SELECT status, error_log FROM posts WHERE id = ?", (post.id,)).fetchone()
            assert row["status"] == "failed"
            assert "não encontrado" in row["error_log"].lower() or "not found" in row["error_log"].lower()


class TestScheduler:
    def test_setup_scheduler_background(
        self, mock_settings: Settings, memory_db: Database
    ):
        """Valida configuração correta dos jobs no BackgroundScheduler."""
        from apscheduler.schedulers.background import BackgroundScheduler

        orchestrator = PipelineOrchestrator(settings=mock_settings, db=memory_db)
        scheduler = orchestrator.setup_scheduler(blocking=False)

        assert isinstance(scheduler, BackgroundScheduler)
        jobs = {job.id: job for job in scheduler.get_jobs()}
        assert "scout_cycle" in jobs
        assert "publishing_cycle" in jobs

    def test_setup_scheduler_blocking(
        self, mock_settings: Settings, memory_db: Database
    ):
        """Valida retorno do BlockingScheduler quando solicitado."""
        from apscheduler.schedulers.blocking import BlockingScheduler

        orchestrator = PipelineOrchestrator(settings=mock_settings, db=memory_db)
        scheduler = orchestrator.setup_scheduler(blocking=True)

        assert isinstance(scheduler, BlockingScheduler)
        jobs = {job.id: job for job in scheduler.get_jobs()}
        assert "scout_cycle" in jobs
        assert "publishing_cycle" in jobs


class TestCliMain:
    def test_cli_add_channel(self, tmp_path: Path):
        """Valida execução do comando add-channel via CLI."""
        from main import main

        test_db_path = tmp_path / "cli_test.db"
        with patch("main.settings") as mock_settings, patch("src.orchestrator.default_settings", mock_settings):
            mock_settings.DB_PATH = test_db_path
            exit_code = main(["add-channel", "UC_CLI_123", "Canal CLI Teste"])

        assert exit_code == 0
        db = Database(test_db_path)
        channels = db.get_active_channels()
        assert len(channels) == 1
        assert channels[0].channel_id == "UC_CLI_123"
        assert channels[0].name == "Canal CLI Teste"

    def test_cli_once(self):
        """Valida execução do comando once via CLI."""
        from main import main

        with patch("main.PipelineOrchestrator") as MockOrchestrator:
            mock_inst = MockOrchestrator.return_value
            mock_inst.run_scout_cycle.return_value = 1
            mock_inst.run_publishing_cycle.return_value = 2

            exit_code = main(["once"])

            assert exit_code == 0
            mock_inst.run_scout_cycle.assert_called_once()
            mock_inst.run_publishing_cycle.assert_called_once()

    def test_cli_run(self):
        """Valida execução do comando run via CLI."""
        from main import main

        with patch("main.PipelineOrchestrator") as MockOrchestrator:
            mock_inst = MockOrchestrator.return_value
            mock_scheduler = MagicMock()
            mock_inst.setup_scheduler.return_value = mock_scheduler

            exit_code = main(["run"])

            assert exit_code == 0
            mock_inst.setup_scheduler.assert_called_once_with(blocking=True)
            mock_scheduler.start.assert_called_once()
