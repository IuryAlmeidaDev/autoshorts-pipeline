"""Gerador e renderizador de vídeos de Artigos Científicos para Shorts e TikTok."""

import logging
import os
from pathlib import Path
import subprocess
from typing import Optional, Union
import uuid

from src.config import settings
from src.dubbing.voice_synthesizer import VoiceSynthesizer
from src.editor.subtitles import generate_ass_subtitle
from src.science.card_renderer import ScienceCardRenderer
from src.science.models import ScienceArticle

logger = logging.getLogger(__name__)


class ScienceGenerationError(Exception):
    """Exceção levantada em falhas durante a renderização do vídeo científico."""

    pass


class ScienceShortsGenerator:
    """Orquestrador completo de renderização de artigos científicos com visual espacial e legendas dinâmicas."""

    def __init__(
        self,
        output_dir: Optional[Union[Path, str]] = None,
        temp_dir: Optional[Union[Path, str]] = None,
        voice_synthesizer: Optional[VoiceSynthesizer] = None,
        card_renderer: Optional[ScienceCardRenderer] = None,
        default_bg_path: Optional[Union[Path, str]] = None,
    ):
        self.output_dir = Path(output_dir or settings.OUTPUT_DIR)
        self.temp_dir = Path(temp_dir or settings.TEMP_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.synthesizer = voice_synthesizer or VoiceSynthesizer(
            temp_dir=self.temp_dir,
            male_voice="pt-BR-AntonioNeural",
            female_voice="pt-BR-FranciscaNeural",
        )
        self.card_renderer = card_renderer or ScienceCardRenderer()

        if default_bg_path:
            self.default_bg_path = Path(default_bg_path)
        else:
            self.default_bg_path = Path(settings.BASE_DIR) / "assets" / "backgrounds" / "space_cosmic_vertical.mp4"

    def _run_ffmpeg(self, cmd: list[str], description: str = "") -> None:
        """Executa comandos FFmpeg capturando logs e erros detalhados."""
        logger.debug("Executando FFmpeg (%s): %s", description, " ".join(cmd))
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            logger.error("Falha no FFmpeg (%s):\nSTDERR:\n%s", description, result.stderr)
            raise ScienceGenerationError(f"Erro no FFmpeg ({description}): {result.stderr[:400]}")

    def generate_video(
        self,
        article: ScienceArticle,
        background_video: Optional[Union[Path, str]] = None,
        output_filename: Optional[Union[Path, str]] = None,
        voice_gender: str = "male",
    ) -> Path:
        """Gera o vídeo final 9:16 completo com áudio neural, card do artigo, background espacial e legendas dinâmicas."""
        session_id = f"science_{uuid.uuid4().hex[:8]}"
        session_dir = self.temp_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        if output_filename:
            final_output = Path(output_filename)
            if not final_output.is_absolute():
                final_output = self.output_dir / final_output
        else:
            final_output = self.output_dir / f"{session_id}.mp4"

        final_output.parent.mkdir(parents=True, exist_ok=True)

        bg_path = Path(background_video or self.default_bg_path)
        if not bg_path.exists():
            # Fallback para o gameplay do minecraft se o espaço ainda não tiver terminado
            fallback_bg = Path(settings.BASE_DIR) / "assets" / "backgrounds" / "minecraft_parkour.mp4"
            if fallback_bg.exists():
                bg_path = fallback_bg
            else:
                raise ScienceGenerationError(f"Nenhum vídeo de fundo disponível em {bg_path}")

        logger.info("Iniciando geração de vídeo científico: '%s' (%s)", article.title, article.journal)

        try:
            # 1. Síntese de Voz Neural com Word Timestamps
            logger.info("Sintetizando locução neural com timestamps...")
            audio_path = session_dir / "voice.mp3"
            audio_file, words = self.synthesizer.synthesize(
                text=article.full_script,
                voice_gender=voice_gender,
                output_filename=audio_path,
            )

            if not audio_file.exists() or audio_file.stat().st_size == 0:
                raise ScienceGenerationError("Falha na síntese do áudio do artigo.")

            # 2. Geração do Card do Artigo em PNG
            logger.info("Renderizando card visual do artigo científico...")
            card_img = self.card_renderer.render_card(article, card_width=960)
            card_path = session_dir / "science_card.png"
            card_img.save(card_path, format="PNG")

            # 3. Geração das Legendas Dinâmicas em ASS (Estilo Karaokê com Ciano Tecnológico)
            logger.info("Gerando legendas dinâmicas sincronizadas...")
            ass_content = generate_ass_subtitle(
                words=words,
                words_per_screen=3,
                highlight_color="&H0000FFFF",  # Amarelo vibrante ativo
                primary_color="&H00FFFFFF",    # Branco puro
                outline_color="&H00000000",    # Contorno preto nítido
                font_name="Arial",
                font_size=58,
                margin_v=420,  # Posicionamento centralizado no terço inferior
            )
            ass_path = session_dir / "subtitles.ass"
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)

            # 4. Renderização Final com FFmpeg
            safe_ass_path = str(ass_path.resolve()).replace("\\", "/")
            if ":" in safe_ass_path:
                drive, rest = safe_ass_path.split(":", 1)
                safe_ass_path = f"{drive}\\:{rest}"

            logger.info("Renderizando vídeo final com card científico, background e legendas dinâmicas...")

            # Card aparece no início (0s a 4.5s) e faz fade-out suave
            filter_complex = (
                "[1:v]format=rgba,fade=t=out:st=4.0:d=0.6:alpha=1[card];"
                "[0:v][card]overlay=(W-w)/2:340:enable='lte(t,4.8)'[v_over];"
                f"[v_over]subtitles='{safe_ass_path}'[v_out]"
            )

            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1",
                "-i", str(bg_path),
                "-i", str(card_path),
                "-i", str(audio_file),
                "-filter_complex", filter_complex,
                "-map", "[v_out]",
                "-map", "2:a",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "44100",
                "-ac", "2",
                "-pix_fmt", "yuv420p",
                "-shortest",
                str(final_output),
            ]

            self._run_ffmpeg(cmd, description="Renderização do Artigo Científico")

            logger.info(
                "Vídeo científico gerado com sucesso! Arquivo: %s (%.2f MB)",
                final_output,
                final_output.stat().st_size / (1024 * 1024),
            )
            return final_output

        except Exception as e:
            logger.error("Erro na geração do artigo científico: %s", e)
            raise
