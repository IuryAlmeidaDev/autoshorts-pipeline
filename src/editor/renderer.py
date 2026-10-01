"""Módulo de renderização e reenquadramento vertical (9:16) com legendas dinâmicas utilizando FFmpeg."""

import logging
from pathlib import Path
import subprocess
from typing import Optional, Union

from src.config import settings
from src.editor.subtitles import WordTimestamp, generate_ass_subtitle

logger = logging.getLogger(__name__)


class RenderError(Exception):
    """Exceção levantada em falhas durante o processamento ou renderização de vídeo."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def escape_ffmpeg_filter_path(path: Union[Path, str]) -> str:
    """Escapa caminhos de arquivos para utilização segura dentro de filtros do FFmpeg no Windows e Linux.

    No Windows, o caractere de dois-pontos da unidade de disco (ex: C:) precisa ser escapado
    como 'C\\:' e as barras invertidas devem ser substituídas por barras normais '/',
    evitando que o parser de filtros do FFmpeg interprete o ':' como separador de parâmetros.
    """
    posix_path = Path(path).as_posix()
    # Escapa dois-pontos de letras de unidade (ex: C: -> C\:)
    escaped = posix_path.replace(":", r"\:")
    # Escapa aspas simples
    escaped = escaped.replace("'", r"\'")
    return escaped


def _escape_drawtext_string(text: str) -> str:
    """Escapa caracteres especiais para a opção text do filtro drawtext do FFmpeg."""
    escaped = text.replace("\\", r"\\")
    escaped = escaped.replace("'", r"\'")
    escaped = escaped.replace(":", r"\:")
    escaped = escaped.replace("%", r"\%")
    return escaped


def build_filter_complex(
    mode: str = "smart_crop",
    subtitle_ass_path: Optional[Union[Path, str]] = None,
    hook_text: Optional[str] = None,
) -> str:
    """Constrói a string de filtros de vídeo (-vf) para conversão para formato 9:16 (1080x1920).

    Modos suportados:
        - smart_crop: Recorta a área central 9:16 de um vídeo 16:9 e escala para 1080x1920.
        - blurred_background: Cria um fundo desfocado 1080x1920 e posiciona o vídeo 16:9 no centro.

    Args:
        mode: 'smart_crop' ou 'blurred_background'.
        subtitle_ass_path: Caminho opcional para arquivo de legenda .ass.
        hook_text: Texto opcional de gancho viral para posicionar no topo do vídeo.

    Returns:
        String formatada para o parâmetro -vf do FFmpeg.

    Raises:
        ValueError: Se o modo for inválido.
    """
    if mode == "smart_crop":
        base_filter = "crop=ih*9/16:ih:(iw-ow)/2:0,scale=1080:1920"
    elif mode == "blurred_background":
        base_filter = (
            "split=2[bg_in][fg_in];"
            "[bg_in]crop=ih*9/16:ih:(iw-ow)/2:0,scale=1080:1920,boxblur=20:5[bg];"
            "[fg_in]scale=1080:-1[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
    else:
        raise ValueError(
            f"Modo inválido: '{mode}'. Modos suportados: 'smart_crop', 'blurred_background'."
        )

    additional_filters: list[str] = []

    # Adiciona texto de gancho no topo com caixa de destaque (Y=220)
    if hook_text and hook_text.strip():
        clean_text = _escape_drawtext_string(hook_text.strip())
        drawtext_filter = (
            f"drawtext=text='{clean_text}':fontsize=54:fontcolor=white:"
            f"borderw=4:bordercolor=black:box=1:boxcolor=black@0.7:boxborderw=16:"
            f"x=(w-text_w)/2:y=220"
        )
        additional_filters.append(drawtext_filter)

    # Adiciona filtro de legendas ASS dinâmicas
    if subtitle_ass_path:
        escaped_sub_path = escape_ffmpeg_filter_path(subtitle_ass_path)
        ass_filter = f"ass='{escaped_sub_path}'"
        additional_filters.append(ass_filter)

    if not additional_filters:
        return base_filter

    return f"{base_filter},{','.join(additional_filters)}"


def build_ffmpeg_render_command(
    input_video: Union[Path, str],
    output_video: Union[Path, str],
    filter_complex: str,
    ffmpeg_bin: str = "ffmpeg",
) -> list[str]:
    """Monta a lista de argumentos de comando do FFmpeg com codecs otimizados para Shorts/Reels/TikTok.

    Argumentos:
        - -y: Sobrescreve saída se existir.
        - -i: Arquivo de entrada.
        - -vf: Filtros de enquadramento 9:16, gancho e legendas.
        - -c:v libx264 -preset fast -crf 22: Otimização de tamanho/qualidade de vídeo.
        - -c:a aac -b:a 192k -ar 44100: Áudio cristalino de alta fidelidade.
    """
    return [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_video),
        "-vf",
        filter_complex,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "22",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "44100",
        str(output_video),
    ]


class VideoRenderer:
    """Motor de renderização e reenquadramento vertical 9:16 de cortes de podcast."""

    def __init__(
        self,
        temp_dir: Optional[Union[Path, str]] = None,
        output_dir: Optional[Union[Path, str]] = None,
        ffmpeg_bin: str = "ffmpeg",
    ):
        self.temp_dir = Path(temp_dir or settings.TEMP_DIR)
        self.output_dir = Path(output_dir or settings.OUTPUT_DIR)
        self.ffmpeg_bin = ffmpeg_bin

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def render_clip(
        self,
        input_video: Union[Path, str],
        hook_text: Optional[str] = None,
        words: Optional[list[WordTimestamp]] = None,
        output_name: str = "clip.mp4",
        mode: str = "smart_crop",
    ) -> Path:
        """Renderiza um corte em formato vertical 9:16 com gancho de texto e legendas dinâmicas.

        Args:
            input_video: Caminho para o corte horizontal MP4 original.
            hook_text: Texto do gancho de retenção a ser desenhado no topo.
            words: Lista de palavras com timestamps para geração de legendas dinâmicas.
            output_name: Nome do arquivo final MP4.
            mode: Modo de reenquadramento ('smart_crop' ou 'blurred_background').

        Returns:
            Caminho absoluto para o vídeo final renderizado.

        Raises:
            FileNotFoundError: Se o vídeo de entrada não existir.
            RenderError: Se o FFmpeg falhar ou o arquivo de saída não for gerado.
        """
        in_path = Path(input_video)
        if not in_path.exists():
            raise FileNotFoundError(f"Vídeo de entrada não encontrado: {in_path}")

        if not output_name.lower().endswith(".mp4"):
            output_name = f"{output_name}.mp4"

        output_path = (self.output_dir / output_name).resolve()

        subtitle_path: Optional[Path] = None
        if words:
            ass_content = generate_ass_subtitle(words)
            subtitle_path = self.temp_dir / f"{output_path.stem}_subs.ass"
            subtitle_path.write_text(ass_content, encoding="utf-8")
            logger.info(f"Arquivo de legendas ASS gerado em: {subtitle_path}")

        filter_str = build_filter_complex(
            mode=mode,
            subtitle_ass_path=subtitle_path,
            hook_text=hook_text,
        )

        cmd = build_ffmpeg_render_command(
            input_video=in_path,
            output_video=output_path,
            filter_complex=filter_str,
            ffmpeg_bin=self.ffmpeg_bin,
        )

        logger.info(f"Executando renderização FFmpeg para: {output_path.name}")
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            err_msg = exc.stderr or exc.stdout or str(exc)
            logger.error(f"Erro na execução do FFmpeg: {err_msg}")
            raise RenderError(f"Falha na execução do FFmpeg: {err_msg}") from exc
        except FileNotFoundError as exc:
            logger.error(f"Binário FFmpeg não encontrado ({self.ffmpeg_bin}): {exc}")
            raise RenderError(
                f"Binário do FFmpeg não encontrado ({self.ffmpeg_bin}). "
                "Certifique-se de que o FFmpeg está instalado e acessível no PATH."
            ) from exc

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RenderError(
                f"O arquivo final renderizado não foi criado ou possui 0 bytes: {output_path}"
            )

        logger.info(f"Renderização concluída com sucesso: {output_path}")
        return output_path
