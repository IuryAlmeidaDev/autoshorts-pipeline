"""Camada de persistência e gerenciamento de estados usando SQLite."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, List, Optional, Union

from src.models import Channel, Clip, Post, Video


class Database:
    """Repositório de dados e controle de estados de execução do AutoShorts."""

    def __init__(self, db_path: Union[Path, str]) -> None:
        self.db_path = str(db_path)
        self._is_memory = self.db_path == ":memory:"

        if self._is_memory:
            # Conexão persistente para banco de dados em memória
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row
            self._mem_conn.execute("PRAGMA foreign_keys = ON;")
        else:
            path_obj = Path(self.db_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            self._mem_conn = None

        self.init_db()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Fornece uma conexão contextual configurada com commits automáticos."""
        if self._is_memory:
            assert self._mem_conn is not None
            yield self._mem_conn
            self._mem_conn.commit()
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    def init_db(self) -> None:
        """Cria as tabelas relacionais se não existirem."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL,
                    youtube_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    processed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS clips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    hook_title TEXT NOT NULL,
                    viral_score REAL NOT NULL,
                    file_path TEXT,
                    status TEXT NOT NULL DEFAULT 'pending_render',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clip_id INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    external_post_id TEXT,
                    error_log TEXT,
                    posted_at TEXT,
                    FOREIGN KEY (clip_id) REFERENCES clips (id) ON DELETE CASCADE
                );
                """
            )

    def add_channel(self, channel_id: str, name: str) -> Channel:
        """Adiciona ou reativa um canal monitorado."""
        now_str = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO channels (channel_id, name, active, created_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    name = excluded.name,
                    active = 1
                RETURNING id, channel_id, name, active, created_at
                """,
                (channel_id, name, now_str),
            )
            row = cursor.fetchone()
            return Channel(
                id=row["id"],
                channel_id=row["channel_id"],
                name=row["name"],
                active=bool(row["active"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def get_active_channels(self) -> List[Channel]:
        """Retorna todos os canais configurados e ativos."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, channel_id, name, active, created_at FROM channels WHERE active = 1 ORDER BY id ASC"
            )
            rows = cursor.fetchall()
            return [
                Channel(
                    id=row["id"],
                    channel_id=row["channel_id"],
                    name=row["name"],
                    active=bool(row["active"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

    def is_video_processed(self, youtube_id: str) -> bool:
        """Verifica se um vídeo do YouTube já foi processado pelo pipeline."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM videos WHERE youtube_id = ? LIMIT 1", (youtube_id,))
            return cursor.fetchone() is not None

    def mark_video_processed(self, youtube_id: str, channel_id: str, title: str) -> Video:
        """Marca um vídeo como processado no histórico."""
        now_str = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO videos (channel_id, youtube_id, title, processed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(youtube_id) DO UPDATE SET
                    title = excluded.title
                RETURNING id, channel_id, youtube_id, title, processed_at
                """,
                (channel_id, youtube_id, title, now_str),
            )
            row = cursor.fetchone()
            return Video(
                id=row["id"],
                channel_id=row["channel_id"],
                youtube_id=row["youtube_id"],
                title=row["title"],
                processed_at=datetime.fromisoformat(row["processed_at"]),
            )

    def save_clip(
        self,
        video_id: int,
        start_time: float,
        end_time: float,
        hook_title: str,
        viral_score: float,
        file_path: Optional[str] = None,
        status: str = "pending_render",
    ) -> Clip:
        """Registra um trecho cortado e suas informações virais."""
        now_str = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO clips (video_id, start_time, end_time, hook_title, viral_score, file_path, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id, video_id, start_time, end_time, hook_title, viral_score, file_path, status, created_at
                """,
                (video_id, start_time, end_time, hook_title, viral_score, file_path, status, now_str),
            )
            row = cursor.fetchone()
            return Clip(
                id=row["id"],
                video_id=row["video_id"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                hook_title=row["hook_title"],
                viral_score=row["viral_score"],
                file_path=row["file_path"],
                status=row["status"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def create_post(self, clip_id: int, platform: str, status: str = "pending") -> Post:
        """Cria uma tarefa de publicação para uma plataforma."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO posts (clip_id, platform, status)
                VALUES (?, ?, ?)
                RETURNING id, clip_id, platform, status, external_post_id, error_log, posted_at
                """,
                (clip_id, platform, status),
            )
            row = cursor.fetchone()
            return Post(
                id=row["id"],
                clip_id=row["clip_id"],
                platform=row["platform"],
                status=row["status"],
                external_post_id=row["external_post_id"],
                error_log=row["error_log"],
                posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
            )

    def get_pending_posts(self, platform: Optional[str] = None) -> List[Post]:
        """Retorna postagens pendentes de publicação, opcionalmente filtradas por plataforma."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if platform:
                cursor.execute(
                    """
                    SELECT id, clip_id, platform, status, external_post_id, error_log, posted_at
                    FROM posts
                    WHERE status = 'pending' AND platform = ?
                    ORDER BY id ASC
                    """,
                    (platform,),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, clip_id, platform, status, external_post_id, error_log, posted_at
                    FROM posts
                    WHERE status = 'pending'
                    ORDER BY id ASC
                    """
                )
            rows = cursor.fetchall()
            return [
                Post(
                    id=row["id"],
                    clip_id=row["clip_id"],
                    platform=row["platform"],
                    status=row["status"],
                    external_post_id=row["external_post_id"],
                    error_log=row["error_log"],
                    posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
                )
                for row in rows
            ]

    def update_post_status(
        self,
        post_id: int,
        status: str,
        external_post_id: Optional[str] = None,
        error_log: Optional[str] = None,
    ) -> None:
        """Atualiza o status de uma postagem (ex: 'posted', 'failed') e registra data/hora."""
        now_str = datetime.now().isoformat() if status == "posted" else None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status == "posted":
                cursor.execute(
                    """
                    UPDATE posts
                    SET status = ?, external_post_id = ?, error_log = ?, posted_at = ?
                    WHERE id = ?
                    """,
                    (status, external_post_id, error_log, now_str, post_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE posts
                    SET status = ?, external_post_id = ?, error_log = ?
                    WHERE id = ?
                    """,
                    (status, external_post_id, error_log, post_id),
                )

    def get_clip(self, clip_id: int) -> Optional[Clip]:
        """Retorna um clipe a partir do seu ID numérico."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, video_id, start_time, end_time, hook_title, viral_score, file_path, status, created_at
                FROM clips
                WHERE id = ?
                """,
                (clip_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return Clip(
                id=row["id"],
                video_id=row["video_id"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                hook_title=row["hook_title"],
                viral_score=row["viral_score"],
                file_path=row["file_path"],
                status=row["status"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def get_posts_for_clip(self, clip_id: int) -> List[Post]:
        """Retorna todas as postagens vinculadas a um determinado clipe."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, clip_id, platform, status, external_post_id, error_log, posted_at
                FROM posts
                WHERE clip_id = ?
                ORDER BY id ASC
                """,
                (clip_id,),
            )
            rows = cursor.fetchall()
            return [
                Post(
                    id=row["id"],
                    clip_id=row["clip_id"],
                    platform=row["platform"],
                    status=row["status"],
                    external_post_id=row["external_post_id"],
                    error_log=row["error_log"],
                    posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
                )
                for row in rows
            ]
