"""Testes unitários para o módulo de Scout e monitoramento de RSS do YouTube."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.database import Database
from src.scout.monitor import Episode, ScoutMonitor, fetch_channel_feed, parse_youtube_feed


SAMPLE_ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="http://www.youtube.com/feeds/videos.xml?channel_id=UC123456789"/>
  <id>yt:channel:UC123456789</id>
  <yt:channelId>UC123456789</yt:channelId>
  <title>Canal de Podcast Teste</title>
  <published>2026-01-01T00:00:00+00:00</published>
  <entry>
    <id>yt:video:vid_001</id>
    <yt:videoId>vid_001</yt:videoId>
    <yt:channelId>UC123456789</yt:channelId>
    <title>Episódio 1 - O Começo de Tudo</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=vid_001"/>
    <published>2026-09-30T10:00:00+00:00</published>
    <updated>2026-09-30T11:00:00+00:00</updated>
  </entry>
  <entry>
    <id>yt:video:vid_002</id>
    <yt:videoId>vid_002</yt:videoId>
    <yt:channelId>UC123456789</yt:channelId>
    <title>Episódio 2 - Segredos e Revelações</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=vid_002"/>
    <published>2026-10-01T15:30:00+00:00</published>
    <updated>2026-10-01T16:00:00+00:00</updated>
  </entry>
</feed>
"""

SAMPLE_FEED_MISSING_OPTIONAL = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>vid_003</yt:videoId>
    <yt:channelId>UC_ALT_CHANNEL</yt:channelId>
    <title>Episódio Sem Link Explícito</title>
    <published>2026-10-01T18:00:00Z</published>
  </entry>
</feed>
"""


def test_parse_youtube_feed_valid():
    """Valida extração correta de episódios a partir de Atom XML válido."""
    episodes = parse_youtube_feed(SAMPLE_ATOM_FEED)

    assert len(episodes) == 2

    ep1 = episodes[0]
    assert ep1.video_id == "vid_001"
    assert ep1.channel_id == "UC123456789"
    assert ep1.title == "Episódio 1 - O Começo de Tudo"
    assert ep1.link == "https://www.youtube.com/watch?v=vid_001"
    assert isinstance(ep1.published_at, datetime)
    assert ep1.published_at.year == 2026
    assert ep1.published_at.month == 9
    assert ep1.published_at.day == 30

    ep2 = episodes[1]
    assert ep2.video_id == "vid_002"
    assert ep2.channel_id == "UC123456789"
    assert ep2.title == "Episódio 2 - Segredos e Revelações"
    assert ep2.link == "https://www.youtube.com/watch?v=vid_002"
    assert ep2.published_at.year == 2026
    assert ep2.published_at.month == 10
    assert ep2.published_at.day == 1


def test_parse_youtube_feed_fallback_link():
    """Valida que gera link padrão quando tag link estiver ausente."""
    episodes = parse_youtube_feed(SAMPLE_FEED_MISSING_OPTIONAL)
    assert len(episodes) == 1
    assert episodes[0].video_id == "vid_003"
    assert episodes[0].channel_id == "UC_ALT_CHANNEL"
    assert episodes[0].link == "https://www.youtube.com/watch?v=vid_003"


@pytest.mark.parametrize(
    "invalid_input",
    [
        "",
        "   ",
        "<html><body>Not an XML feed</body></html>",
        "<feed></feed>",
        "<invalid <tag>>",
        None,
    ],
)
def test_parse_youtube_feed_malformed_or_empty(invalid_input):
    """Valida que entradas vazias ou malformadas retornam lista vazia sem quebrar."""
    episodes = parse_youtube_feed(invalid_input)
    assert episodes == []


def test_fetch_channel_feed_success():
    """Valida requisição HTTP GET com parâmetros e headers corretos."""
    channel_id = "UC123456789"
    expected_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    with patch("src.scout.monitor.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_ATOM_FEED
        mock_get.return_value = mock_response

        content = fetch_channel_feed(channel_id, timeout=10)

        assert content == SAMPLE_ATOM_FEED
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == expected_url
        assert kwargs["timeout"] == 10
        assert "User-Agent" in kwargs["headers"]


def test_fetch_channel_feed_http_error():
    """Valida tratamento seguro quando o servidor retorna erro HTTP (ex: 404)."""
    with patch("src.scout.monitor.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response

        content = fetch_channel_feed("UC_NON_EXISTENT")
        assert content == ""


def test_fetch_channel_feed_connection_exception():
    """Valida tratamento de exceção de rede (Timeout / ConnectionError)."""
    with patch("src.scout.monitor.requests.get") as mock_get:
        mock_get.side_effect = requests.RequestException("Network timeout")

        content = fetch_channel_feed("UC123456789")
        assert content == ""


def test_scout_monitor_scan_all_channels_filters_processed():
    """Valida que o monitor só retorna vídeos de canais ativos que ainda não foram processados."""
    db = Database(":memory:")
    c1 = db.add_channel(channel_id="UC_CHAN_1", name="Canal Um")
    c2 = db.add_channel(channel_id="UC_CHAN_2", name="Canal Dois")

    # Marca vid_001 como já processado no banco
    db.mark_video_processed(youtube_id="vid_001", channel_id=c1.channel_id, title="Episódio Antigo")

    monitor = ScoutMonitor(db=db)

    # Simula feeds para os canais
    feed_channel_1 = SAMPLE_ATOM_FEED  # Contém vid_001 (já processado) e vid_002 (novo)
    feed_channel_2 = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <yt:videoId>vid_004</yt:videoId>
        <yt:channelId>UC_CHAN_2</yt:channelId>
        <title>Canal 2 Vídeo Novo</title>
        <link rel="alternate" href="https://www.youtube.com/watch?v=vid_004"/>
        <published>2026-10-01T12:00:00+00:00</published>
      </entry>
    </feed>
    """

    def mock_fetch(channel_id, timeout=15):
        if channel_id == "UC_CHAN_1":
            return feed_channel_1
        elif channel_id == "UC_CHAN_2":
            return feed_channel_2
        return ""

    with patch("src.scout.monitor.fetch_channel_feed", side_effect=mock_fetch):
        new_episodes = monitor.scan_all_channels()

        # Esperado: vid_002 e vid_004 (vid_001 filtrado por já estar no banco)
        video_ids = [ep.video_id for ep in new_episodes]
        assert "vid_001" not in video_ids
        assert "vid_002" in video_ids
        assert "vid_004" in video_ids
        assert len(new_episodes) == 2


def test_scout_monitor_ignores_inactive_channels():
    """Valida que canais marcados como inativos não são escaneados."""
    db = Database(":memory:")
    c1 = db.add_channel(channel_id="UC_ACTIVE", name="Canal Ativo")
    c2 = db.add_channel(channel_id="UC_INACTIVE", name="Canal Inativo")

    # Desativa canal 2
    with db.get_connection() as conn:
        conn.execute("UPDATE channels SET active = 0 WHERE channel_id = ?", (c2.channel_id,))

    monitor = ScoutMonitor(db=db)

    with patch("src.scout.monitor.fetch_channel_feed") as mock_fetch:
        mock_fetch.return_value = SAMPLE_ATOM_FEED

        new_episodes = monitor.scan_all_channels()

        # Apenas UC_ACTIVE deve ter sido chamado
        called_channel_ids = [call.args[0] for call in mock_fetch.call_args_list]
        assert "UC_ACTIVE" in called_channel_ids
        assert "UC_INACTIVE" not in called_channel_ids


def test_scout_monitor_channel_fetch_failure_continues_others():
    """Valida que a falha de um canal não impede o monitoramento dos demais."""
    db = Database(":memory:")
    db.add_channel(channel_id="UC_FAIL", name="Canal Falho")
    db.add_channel(channel_id="UC_OK", name="Canal Saudável")

    monitor = ScoutMonitor(db=db)

    def mock_fetch(channel_id, timeout=15):
        if channel_id == "UC_FAIL":
            return ""  # simula erro de conexão
        return SAMPLE_ATOM_FEED

    with patch("src.scout.monitor.fetch_channel_feed", side_effect=mock_fetch):
        new_episodes = monitor.scan_all_channels()

        assert len(new_episodes) == 2
        assert {ep.video_id for ep in new_episodes} == {"vid_001", "vid_002"}
