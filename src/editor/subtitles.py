"""Módulo de extração e geração de legendas dinâmicas estilo TikTok/Reels em formato ASS."""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)


class SubtitleError(Exception):
    """Exceção levantada em falhas durante extração ou geração de legendas."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass
class WordTimestamp:
    """Representação de uma palavra com marcação temporal de início e fim."""

    word: str
    start: float
    end: float


def format_ass_timestamp(seconds: float) -> str:
    """Converte segundos em formato de timestamp ASS (H:MM:SS.cs).

    Exemplos:
        0.0 -> '0:00:00.00'
        1.25 -> '0:00:01.25'
        65.5 -> '0:01:05.50'
        3661.05 -> '1:01:01.05'
    """
    total_cs = max(0, round(float(seconds) * 100))
    hours = total_cs // 360000
    rem = total_cs % 360000
    minutes = rem // 6000
    rem = rem % 6000
    secs = rem // 100
    cs = rem % 100

    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _normalize_ass_color(color: str) -> str:
    """Garante que a cor ASS termine com &."""
    clean = color.strip()
    if not clean.endswith("&"):
        clean = f"{clean}&"
    return clean


def generate_ass_subtitle(
    words: list[WordTimestamp],
    words_per_screen: int = 3,
    highlight_color: str = "&H0000FFFF",
    primary_color: str = "&H00FFFFFF",
    outline_color: str = "&H00000000",
    back_color: str = "&H00000000",
    font_name: str = "Arial Black",
    font_size: int = 54,
    margin_v: int = 280,
) -> str:
    """Gera o conteúdo de um arquivo de legendas .ass com animação estilo karaokê palavra por palavra.

    Args:
        words: Lista de palavras com timestamps.
        words_per_screen: Quantidade de palavras exibidas simultaneamente na tela.
        highlight_color: Cor da palavra ativa em formato ASS (&HAABBGGRR).
        primary_color: Cor padrão das palavras em formato ASS (&HAABBGGRR).
        outline_color: Cor da borda em formato ASS.
        back_color: Cor da sombra/fundo em formato ASS.
        font_name: Nome da fonte instalada (ex: Arial Black).
        font_size: Tamanho da fonte em pontos.
        margin_v: Margem vertical inferior (em pixels para resolução 1080x1920).

    Returns:
        String formatada em especificação ASS v4.00+.
    """
    hl_color_tag = _normalize_ass_color(highlight_color)
    pri_color_tag = _normalize_ass_color(primary_color)

    # Cabeçalho padrão ASS para vídeo vertical 9:16 (1080x1920)
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},"
        f"{back_color},-1,0,0,0,100,100,0,0,1,4,0,2,40,40,{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    if not words:
        return header

    dialogue_lines: list[str] = []

    # Agrupa palavras em janelas de tamanho words_per_screen
    chunk_size = max(1, words_per_screen)
    for i in range(0, len(words), chunk_size):
        chunk = words[i : i + chunk_size]

        # Para cada palavra na janela, cria um evento com a palavra corrente destacada
        for active_idx, active_word in enumerate(chunk):
            start_ts = format_ass_timestamp(active_word.start)
            end_sec = max(active_word.end, active_word.start + 0.05)
            end_ts = format_ass_timestamp(end_sec)

            formatted_words = []
            for w_idx, w in enumerate(chunk):
                if w_idx == active_idx:
                    formatted_words.append(f"{{\\c{hl_color_tag}}}{w.word}{{\\c{pri_color_tag}}}")
                else:
                    formatted_words.append(w.word)

            line_text = " ".join(formatted_words)
            dialogue_lines.append(
                f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{line_text}"
            )

    return header + "\n".join(dialogue_lines) + "\n"


def extract_subtitles_with_whisper(
    audio_or_video_path: Union[Path, str],
    model_size: str = "base",
    device: str = "cpu",
    compute_type: str = "int8",
) -> list[WordTimestamp]:
    """Extrai palavras com timestamps de um arquivo de áudio ou vídeo utilizando faster-whisper.

    Args:
        audio_or_video_path: Caminho para o arquivo de mídia.
        model_size: Tamanho do modelo Whisper ('tiny', 'base', 'small', 'medium', 'large-v3').
        device: Dispositivo de execução ('cpu' ou 'cuda').
        compute_type: Precisão de quantização ('int8', 'float16', 'float32').

    Returns:
        Lista de objetos WordTimestamp com início e fim em segundos.

    Raises:
        FileNotFoundError: Se o arquivo de mídia não existir.
        SubtitleError: Se faster-whisper não estiver instalado ou falhar no processamento.
    """
    media_path = Path(audio_or_video_path)
    if not media_path.exists():
        raise FileNotFoundError(f"Arquivo de mídia não encontrado: {media_path}")

    try:
        import faster_whisper
    except (ImportError, ModuleNotFoundError) as exc:
        logger.error("faster-whisper não está instalado no ambiente.")
        raise SubtitleError(
            "O pacote faster-whisper não está instalado. "
            "Instale-o com 'pip install faster-whisper' para extrair legendas."
        ) from exc

    try:
        logger.info(
            f"Iniciando transcrição com Whisper ({model_size}, {device}, {compute_type}) para: {media_path.name}"
        )
        model = faster_whisper.WhisperModel(
            model_size, device=device, compute_type=compute_type
        )
        segments, _info = model.transcribe(str(media_path), word_timestamps=True)

        words: list[WordTimestamp] = []
        for segment in segments:
            seg_words = getattr(segment, "words", None)
            if seg_words:
                for w in seg_words:
                    word_clean = w.word.strip()
                    if word_clean:
                        words.append(
                            WordTimestamp(
                                word=word_clean,
                                start=float(w.start),
                                end=float(w.end),
                            )
                        )

        logger.info(f"Transcrição concluída. Total de palavras extraídas: {len(words)}")
        return words

    except Exception as exc:
        if isinstance(exc, SubtitleError):
            raise
        logger.error(f"Erro durante a transcrição Whisper: {exc}")
        raise SubtitleError(f"Falha ao extrair legendas via Whisper: {exc}") from exc
