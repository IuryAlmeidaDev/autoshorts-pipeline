"""Monitor de feeds RSS/Atom do YouTube para descoberta e scouting de novos episódios."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

import requests

from src.database import Database

logger = logging.getLogger(__name__)

ATOM_NS = "http://www.w3.org/2005/Atom"
YT_NS = "http://www.youtube.com/xml/schemas/2015"
NAMESPACES = {
    "atom": ATOM_NS,
    "yt": YT_NS,
}

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class Episode:
    """Representação de um episódio descoberto via feed RSS."""

    video_id: str
    channel_id: str
    title: str
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    link: str = ""


def _parse_datetime(dt_str: Optional[str]) -> datetime:
    """Faz o parse seguro de timestamps ISO 8601 do feed Atom."""
    if not dt_str:
        return datetime.now(timezone.utc)

    cleaned = dt_str.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError) as e:
        logger.debug("Falha ao converter data %s: %s", dt_str, e)
        return datetime.now(timezone.utc)


def parse_youtube_feed(feed_content: Optional[str]) -> List[Episode]:
    """Extrai episódios a partir do conteúdo XML do feed Atom do YouTube.

    Trata com segurança feeds vazios, tags ausentes ou XML malformatado.
    """
    if not feed_content or not isinstance(feed_content, str) or not feed_content.strip():
        return []

    try:
        root = ET.fromstring(feed_content.strip())
    except ET.ParseError as e:
        logger.warning("Falha ao analisar XML do feed RSS: %s", e)
        return []

    # Localiza as tags de entrada <entry>
    entries = root.findall("atom:entry", NAMESPACES)
    if not entries:
        entries = root.findall(f"{{{ATOM_NS}}}entry")
    if not entries:
        entries = root.findall("entry")

    episodes: List[Episode] = []

    for entry in entries:
        # Extração do videoId
        video_id_el = entry.find("yt:videoId", NAMESPACES)
        if video_id_el is None:
            video_id_el = entry.find(f"{{{YT_NS}}}videoId")
        if video_id_el is None:
            video_id_el = entry.find("videoId")

        video_id = video_id_el.text.strip() if (video_id_el is not None and video_id_el.text) else ""

        # Extração do channelId
        channel_id_el = entry.find("yt:channelId", NAMESPACES)
        if channel_id_el is None:
            channel_id_el = entry.find(f"{{{YT_NS}}}channelId")
        if channel_id_el is None:
            channel_id_el = entry.find("channelId")

        channel_id = channel_id_el.text.strip() if (channel_id_el is not None and channel_id_el.text) else ""

        # Extração do título
        title_el = entry.find("atom:title", NAMESPACES)
        if title_el is None:
            title_el = entry.find(f"{{{ATOM_NS}}}title")
        if title_el is None:
            title_el = entry.find("title")

        title = title_el.text.strip() if (title_el is not None and title_el.text) else ""

        # Ignora se não houver video_id
        if not video_id:
            continue

        # Extração da data de publicação
        published_el = entry.find("atom:published", NAMESPACES)
        if published_el is None:
            published_el = entry.find(f"{{{ATOM_NS}}}published")
        if published_el is None:
            published_el = entry.find("published")

        pub_text = published_el.text if published_el is not None else None
        published_at = _parse_datetime(pub_text)

        # Extração do link
        link = ""
        link_elements = entry.findall("atom:link", NAMESPACES)
        if not link_elements:
            link_elements = entry.findall(f"{{{ATOM_NS}}}link")
        if not link_elements:
            link_elements = entry.findall("link")

        for el in link_elements:
            rel = el.attrib.get("rel", "")
            href = el.attrib.get("href", "")
            if rel == "alternate" and href:
                link = href
                break
            elif href and not link:
                link = href

        if not link:
            link = f"https://www.youtube.com/watch?v={video_id}"

        episodes.append(
            Episode(
                video_id=video_id,
                channel_id=channel_id,
                title=title,
                published_at=published_at,
                link=link,
            )
        )

    return episodes


def fetch_channel_feed(channel_id: str, timeout: int = 15) -> str:
    """Faz requisição HTTP GET para o feed RSS oficial do YouTube."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            return response.text
        logger.warning(
            "Resposta inesperada ao obter feed do canal %s: status %d",
            channel_id,
            response.status_code,
        )
        return ""
    except Exception as exc:
        logger.warning("Erro de conexão ao buscar feed do canal %s: %s", channel_id, exc)
        return ""


class ScoutMonitor:
    """Monitor responsável por varrer canais do YouTube e identificar novos vídeos."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def scan_all_channels(self) -> List[Episode]:
        """Busca canais ativos no banco, consulta os feeds e retorna vídeos não processados."""
        active_channels = self.db.get_active_channels()
        new_episodes: List[Episode] = []

        for channel in active_channels:
            logger.info("Escaneando canal %s (%s)...", channel.name, channel.channel_id)
            feed_content = fetch_channel_feed(channel.channel_id)
            if not feed_content:
                continue

            episodes = parse_youtube_feed(feed_content)
            for episode in episodes:
                if not self.db.is_video_processed(episode.video_id):
                    new_episodes.append(episode)

        return new_episodes
