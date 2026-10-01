"""Modelos de dados para o pipeline AutoShorts."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Channel:
    channel_id: str = ""
    name: str = ""
    active: bool = True
    language: str = "pt"
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Video:
    channel_id: str = ""
    youtube_id: str = ""
    title: str = ""
    id: Optional[int] = None
    processed_at: datetime = field(default_factory=datetime.now)


@dataclass
class Clip:
    video_id: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    hook_title: str = ""
    viral_score: float = 0.0
    file_path: Optional[str] = None
    status: str = "pending_render"
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Post:
    clip_id: int = 0
    platform: str = ""
    status: str = "pending"
    external_post_id: Optional[str] = None
    error_log: Optional[str] = None
    posted_at: Optional[datetime] = None
    id: Optional[int] = None
