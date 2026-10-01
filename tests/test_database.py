import sqlite3
from datetime import datetime
from pathlib import Path
import pytest

from src.database import Database
from src.models import Channel, Video, Clip, Post


def test_models_instantiation():
    """Valida a instanciação dos modelos com valores padrão e tipos esperados."""
    channel = Channel(channel_id="UC123", name="Canal Teste")
    assert channel.channel_id == "UC123"
    assert channel.name == "Canal Teste"
    assert channel.active is True
    assert channel.id is None
    assert isinstance(channel.created_at, datetime)

    video = Video(channel_id="UC123", youtube_id="yt_abc", title="Vídeo Teste")
    assert video.channel_id == "UC123"
    assert video.youtube_id == "yt_abc"
    assert video.title == "Vídeo Teste"
    assert video.id is None
    assert isinstance(video.processed_at, datetime)

    clip = Clip(
        video_id=1,
        start_time=10.0,
        end_time=40.0,
        hook_title="Gancho Viral",
        viral_score=8.5,
        file_path="storage/output/clip.mp4",
    )
    assert clip.video_id == 1
    assert clip.start_time == 10.0
    assert clip.end_time == 40.0
    assert clip.hook_title == "Gancho Viral"
    assert clip.viral_score == 8.5
    assert clip.status == "pending_render"
    assert clip.file_path == "storage/output/clip.mp4"
    assert isinstance(clip.created_at, datetime)

    post = Post(clip_id=1, platform="youtube_shorts")
    assert post.clip_id == 1
    assert post.platform == "youtube_shorts"
    assert post.status == "pending"
    assert post.external_post_id is None
    assert post.error_log is None
    assert post.posted_at is None


def test_init_db_creates_tables(tmp_path: Path):
    """Garante que a inicialização do banco cria as tabelas necessárias."""
    db_file = tmp_path / "test.db"
    db = Database(db_file)
    db.init_db()

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    expected_tables = {"channels", "videos", "clips", "posts"}
    assert expected_tables.issubset(tables)


def test_channel_operations(tmp_path: Path):
    """Testa adição e listagem de canais ativos."""
    db = Database(tmp_path / "test.db")
    db.init_db()

    ch1 = db.add_channel(channel_id="UC001", name="Canal 1")
    assert isinstance(ch1, Channel)
    assert ch1.id is not None
    assert ch1.channel_id == "UC001"
    assert ch1.name == "Canal 1"
    assert ch1.active is True

    ch2 = db.add_channel(channel_id="UC002", name="Canal 2")
    assert ch2.id is not None

    active_channels = db.get_active_channels()
    assert len(active_channels) == 2
    channel_ids = [c.channel_id for c in active_channels]
    assert "UC001" in channel_ids
    assert "UC002" in channel_ids

    # Atualizar canal para inativo direto no banco e verificar filtro
    with db.get_connection() as conn:
        conn.execute("UPDATE channels SET active = 0 WHERE channel_id = ?", ("UC002",))

    active_after = db.get_active_channels()
    assert len(active_after) == 1
    assert active_after[0].channel_id == "UC001"


def test_video_processing_state(tmp_path: Path):
    """Testa marcação de vídeo como processado e verificação de idempotência."""
    db = Database(tmp_path / "test.db")
    db.init_db()

    db.add_channel(channel_id="UC_PODCAST", name="Podcast Canal")

    assert db.is_video_processed("yt_video_001") is False

    video = db.mark_video_processed(
        youtube_id="yt_video_001",
        channel_id="UC_PODCAST",
        title="Episódio 1 Completo",
    )

    assert isinstance(video, Video)
    assert video.id is not None
    assert video.youtube_id == "yt_video_001"
    assert video.channel_id == "UC_PODCAST"
    assert video.title == "Episódio 1 Completo"
    assert isinstance(video.processed_at, datetime)

    assert db.is_video_processed("yt_video_001") is True
    assert db.is_video_processed("yt_video_002") is False


def test_clip_creation(tmp_path: Path):
    """Testa salvamento e recuperação de clipes com métricas virais."""
    db = Database(tmp_path / "test.db")
    db.init_db()

    video = db.mark_video_processed("yt_clip_vid", "UC_GENERIC", "Vídeo de Teste")

    clip = db.save_clip(
        video_id=video.id,
        start_time=15.5,
        end_time=45.0,
        hook_title="Momento Chocante",
        viral_score=9.2,
        file_path="storage/output/clip_1.mp4",
    )

    assert isinstance(clip, Clip)
    assert clip.id is not None
    assert clip.video_id == video.id
    assert clip.start_time == 15.5
    assert clip.end_time == 45.0
    assert clip.hook_title == "Momento Chocante"
    assert clip.viral_score == 9.2
    assert clip.file_path == "storage/output/clip_1.mp4"
    assert clip.status == "pending_render"


def test_post_lifecycle_and_filtering(tmp_path: Path):
    """Testa ciclo de vida das postagens: criação, filtro por plataforma e atualização de status."""
    db = Database(tmp_path / "test.db")
    db.init_db()

    video = db.mark_video_processed("yt_v1", "UC_P", "Video Teste")
    clip = db.save_clip(
        video_id=video.id,
        start_time=0.0,
        end_time=30.0,
        hook_title="Hook Top",
        viral_score=8.0,
    )

    post_yt = db.create_post(clip_id=clip.id, platform="youtube_shorts")
    post_tt = db.create_post(clip_id=clip.id, platform="tiktok")

    assert post_yt.id is not None
    assert post_yt.status == "pending"
    assert post_tt.id is not None
    assert post_tt.status == "pending"

    # Buscar todos pendentes
    all_pending = db.get_pending_posts()
    assert len(all_pending) == 2

    # Filtrar por plataforma
    pending_tt = db.get_pending_posts(platform="tiktok")
    assert len(pending_tt) == 1
    assert pending_tt[0].id == post_tt.id
    assert pending_tt[0].platform == "tiktok"

    # Atualizar status com sucesso
    db.update_post_status(
        post_id=post_tt.id,
        status="posted",
        external_post_id="tt_video_998877",
    )

    # Verificar que TikTok não está mais pendente
    pending_tt_after = db.get_pending_posts(platform="tiktok")
    assert len(pending_tt_after) == 0

    pending_yt_after = db.get_pending_posts(platform="youtube_shorts")
    assert len(pending_yt_after) == 1

    # Atualizar outro post com erro
    db.update_post_status(
        post_id=post_yt.id,
        status="failed",
        error_log="Quota exceeded",
    )

    pending_yt_after_failure = db.get_pending_posts(platform="youtube_shorts")
    assert len(pending_yt_after_failure) == 0

    # Validar campos gravados no banco
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, external_post_id, posted_at FROM posts WHERE id = ?", (post_tt.id,))
        row_tt = cursor.fetchone()
        assert row_tt[0] == "posted"
        assert row_tt[1] == "tt_video_998877"
        assert row_tt[2] is not None  # posted_at deve estar preenchido

        cursor.execute("SELECT status, error_log FROM posts WHERE id = ?", (post_yt.id,))
        row_yt = cursor.fetchone()
        assert row_yt[0] == "failed"
        assert row_yt[1] == "Quota exceeded"


def test_in_memory_database():
    """Garante que a classe Database suporta ':memory:' para testes isolados ultra-rápidos."""
    db = Database(":memory:")
    db.init_db()

    ch = db.add_channel("UC_MEM", "Canal Memória")
    assert ch.id == 1
    assert len(db.get_active_channels()) == 1
