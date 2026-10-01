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
    assert channel.language == "pt"
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
    assert ch1.language == "pt"

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
    assert ch.language == "pt"
    assert len(db.get_active_channels()) == 1


def test_channel_language_support(tmp_path: Path):
    """Testa cadastro e filtragem de canais por idioma."""
    db = Database(tmp_path / "test.db")
    db.init_db()

    # Canal com idioma padrão (pt)
    ch_pt1 = db.add_channel(channel_id="UC_PT1", name="Canal PT 1")
    assert ch_pt1.language == "pt"

    # Canal explicitamente configurado como pt
    ch_pt2 = db.add_channel(channel_id="UC_PT2", name="Canal PT 2", language="pt")
    assert ch_pt2.language == "pt"

    # Canal configurado como en
    ch_en1 = db.add_channel(channel_id="UC_EN1", name="Huberman Lab", language="en")
    assert ch_en1.language == "en"

    # Canal configurado como en adicional
    ch_en2 = db.add_channel(channel_id="UC_EN2", name="Lex Fridman", language="en")
    assert ch_en2.language == "en"

    # Busca geral sem filtro de idioma (deve trazer todos os ativos)
    all_active = db.get_active_channels()
    assert len(all_active) == 4

    # Busca filtrando por idioma pt
    pt_channels = db.get_active_channels(language="pt")
    assert len(pt_channels) == 2
    assert {c.channel_id for c in pt_channels} == {"UC_PT1", "UC_PT2"}
    assert all(c.language == "pt" for c in pt_channels)

    # Busca filtrando por idioma en
    en_channels = db.get_active_channels(language="en")
    assert len(en_channels) == 2
    assert {c.channel_id for c in en_channels} == {"UC_EN1", "UC_EN2"}
    assert all(c.language == "en" for c in en_channels)

    # Busca por idioma inexistente
    es_channels = db.get_active_channels(language="es")
    assert len(es_channels) == 0


def test_database_migration_adds_language_column(tmp_path: Path):
    """Testa migração de banco legado sem a coluna language."""
    db_file = tmp_path / "legacy.db"

    # Cria tabela no esquema legado sem a coluna language
    conn = sqlite3.connect(db_file)
    conn.execute(
        """
        CREATE TABLE channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO channels (channel_id, name, active, created_at) VALUES ('UC_LEGACY', 'Legacy Channel', 1, '2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    # Inicializa o repositório Database com o banco legado existente
    db = Database(db_file)

    # Verifica se a migração adicionou a coluna language com valor padrão 'pt'
    active_channels = db.get_active_channels()
    assert len(active_channels) == 1
    legacy_channel = active_channels[0]
    assert legacy_channel.channel_id == "UC_LEGACY"
    assert legacy_channel.language == "pt"

    # Atualiza canal existente alterando seu idioma para 'en'
    updated = db.add_channel(channel_id="UC_LEGACY", name="Legacy Channel Renamed", language="en")
    assert updated.language == "en"
    assert updated.name == "Legacy Channel Renamed"

    # Confirma que filtro por en agora encontra o canal atualizado
    en_channels = db.get_active_channels(language="en")
    assert len(en_channels) == 1
    assert en_channels[0].channel_id == "UC_LEGACY"
    assert en_channels[0].language == "en"

