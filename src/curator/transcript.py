"""Módulo para busca e formatação de transcrições do YouTube."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Union

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None  # type: ignore

logger = logging.getLogger(__name__)


# Compatibilidade retroativa para versões do youtube-transcript-api
if YouTubeTranscriptApi is not None and not hasattr(YouTubeTranscriptApi, "get_transcript"):
    @staticmethod
    def _compat_get_transcript(video_id: str, languages: Sequence[str] = ("pt", "pt-BR", "en"), **kwargs) -> List[Dict[str, Any]]:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=languages)
        return [{"text": getattr(s, "text", ""), "start": getattr(s, "start", 0.0), "duration": getattr(s, "duration", 0.0)} for s in fetched]

    setattr(YouTubeTranscriptApi, "get_transcript", _compat_get_transcript)


class TranscriptNotFoundError(Exception):
    """Exceção levantada quando nenhuma transcrição é encontrada para o vídeo."""
    pass


@dataclass
class TranscriptSegment:
    """Segmento individual de transcrição com marcação de tempo."""

    text: str
    start: float
    duration: float

    @property
    def end(self) -> float:
        """Timestamp de encerramento do segmento."""
        return round(self.start + self.duration, 3)


def format_seconds_to_timestamp(seconds: float) -> str:
    """Converte segundos para timestamp legível (MM:SS ou HH:MM:SS)."""
    total_secs = max(0, int(seconds))
    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    secs = total_secs % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_transcript_with_timestamps(
    segments: Optional[List[TranscriptSegment]],
    chunk_interval: int = 15,
) -> str:
    """Agrupa segmentos de transcrição em janelas de tempo legíveis para a LLM.

    Exemplo:
        [01:15 - 01:30] Texto falado agrupado...
    """
    if not segments:
        return ""

    if chunk_interval <= 0:
        chunk_interval = 15

    # Agrupa segmentos por janela temporal
    chunks: Dict[int, List[str]] = {}
    for seg in segments:
        if not seg.text or not seg.text.strip():
            continue
        chunk_idx = int(seg.start // chunk_interval)
        if chunk_idx not in chunks:
            chunks[chunk_idx] = []
        chunks[chunk_idx].append(seg.text.strip())

    formatted_lines: List[str] = []
    for chunk_idx in sorted(chunks.keys()):
        window_start = chunk_idx * chunk_interval
        window_end = window_start + chunk_interval
        start_ts = format_seconds_to_timestamp(window_start)
        end_ts = format_seconds_to_timestamp(window_end)
        chunk_text = " ".join(chunks[chunk_idx])
        formatted_lines.append(f"[{start_ts} - {end_ts}] {chunk_text}")

    return "\n".join(formatted_lines)


class TranscriptFetcher:
    """Responsável por buscar transcrições de vídeos do YouTube."""

    def __init__(self, api: Any = None) -> None:
        self.api = api or YouTubeTranscriptApi

    def _get_raw_transcript(
        self, video_id: str, languages: Sequence[str]
    ) -> Union[List[Dict[str, Any]], Sequence[Any]]:
        """Invoca a API do YouTubeTranscriptApi de forma compatível."""
        if not self.api:
            raise TranscriptNotFoundError("youtube-transcript-api não está instalado.")

        # Se houver método estático ou mock get_transcript
        if hasattr(self.api, "get_transcript"):
            return self.api.get_transcript(video_id, languages=languages)

        # Se for instância com método fetch
        instance = self.api() if isinstance(self.api, type) else self.api
        if hasattr(instance, "fetch"):
            return instance.fetch(video_id, languages=languages)

        raise TranscriptNotFoundError("Nenhum método compatível de transcrição encontrado.")

    def fetch_transcript(
        self,
        video_id: Optional[str],
        languages: Optional[List[str]] = None,
        raise_on_error: bool = False,
    ) -> List[TranscriptSegment]:
        """Obtém a lista de segmentos de transcrição para o vídeo informado.

        Args:
            video_id: ID do vídeo no YouTube.
            languages: Lista prioritária de códigos de idioma.
            raise_on_error: Se True, propaga TranscriptNotFoundError em caso de falha.
        """
        if not video_id or not str(video_id).strip():
            logger.debug("ID de vídeo vazio ou inválido fornecido.")
            return []

        cleaned_id = str(video_id).strip()
        langs = languages or ["pt", "pt-BR", "en"]

        try:
            raw_data = self._get_raw_transcript(cleaned_id, langs)
            if not raw_data:
                if raise_on_error:
                    raise TranscriptNotFoundError(f"Transcrição vazia para vídeo {cleaned_id}.")
                return []

            segments: List[TranscriptSegment] = []
            for item in raw_data:
                if isinstance(item, dict):
                    text = str(item.get("text", "")).strip()
                    start = float(item.get("start", 0.0))
                    duration = float(item.get("duration", 0.0))
                else:
                    text = str(getattr(item, "text", "")).strip()
                    start = float(getattr(item, "start", 0.0))
                    duration = float(getattr(item, "duration", 0.0))

                if text:
                    segments.append(
                        TranscriptSegment(
                            text=text,
                            start=round(start, 3),
                            duration=round(duration, 3),
                        )
                    )

            if not segments and raise_on_error:
                raise TranscriptNotFoundError(f"Nenhum texto extraído da transcrição do vídeo {cleaned_id}.")

            return segments

        except Exception as exc:
            logger.warning("Falha ao obter transcrição para vídeo %s: %s", cleaned_id, exc)
            if raise_on_error:
                raise TranscriptNotFoundError(f"Falha ao obter transcrição de {cleaned_id}: {exc}") from exc
            return []

    def format_transcript_with_timestamps(
        self,
        segments: Optional[List[TranscriptSegment]],
        chunk_interval: int = 15,
    ) -> str:
        """Método de conveniência associado à instância do fetcher."""
        return format_transcript_with_timestamps(segments, chunk_interval=chunk_interval)
