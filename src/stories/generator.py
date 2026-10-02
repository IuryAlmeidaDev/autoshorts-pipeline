"""Gerador e renderizador de vídeos de histórias do Reddit para Shorts e TikTok."""

import logging
import os
from pathlib import Path
import subprocess
from typing import Optional, Union
import uuid

from src.config import settings
from src.dubbing.voice_synthesizer import VoiceSynthesizer
from src.editor.subtitles import generate_ass_subtitle
from src.stories.card_renderer import RedditCardRenderer
from src.stories.models import RedditStory

logger = logging.getLogger(__name__)


class StoryGenerationError(Exception):
    """Exceção levantada em erros durante a geração do vídeo da história."""

    pass


class RedditStoryGenerator:
    """Orquestrador completo de renderização de histórias do Reddit com gameplay e legendas virais."""

    def __init__(
        self,
        output_dir: Optional[Union[Path, str]] = None,
        temp_dir: Optional[Union[Path, str]] = None,
        voice_synthesizer: Optional[VoiceSynthesizer] = None,
        card_renderer: Optional[RedditCardRenderer] = None,
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
        self.card_renderer = card_renderer or RedditCardRenderer()

        if default_bg_path:
            self.default_bg_path = Path(default_bg_path)
        else:
            self.default_bg_path = Path(settings.BASE_DIR) / "assets" / "backgrounds" / "minecraft_parkour.mp4"

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
            raise StoryGenerationError(f"Erro no FFmpeg ({description}): {result.stderr[:400]}")

    def _ensure_background_exists(self, bg_path: Path) -> Path:
        """Garante que o vídeo de fundo exista, baixando automaticamente clipe livre de direitos se necessário."""
        if bg_path.exists() and bg_path.stat().st_size > 10000:
            return bg_path

        bg_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Vídeo de fundo não encontrado em %s. Baixando clipe CC0 de gameplay...", bg_path)
        cmd = [
            "yt-dlp",
            "--download-sections", "*15-75",
            "--force-keyframes-at-cuts",
            "-f", "bestvideo[height<=1920][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "-o", str(bg_path),
            "https://www.youtube.com/watch?v=7yl7Wc1dtWc",
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not bg_path.exists():
            raise StoryGenerationError(f"Arquivo de vídeo de fundo não encontrado e download falhou: {res.stderr[:200]}")
        return bg_path

    def generate_video(
        self,
        story: RedditStory,
        background_video: Optional[Union[Path, str]] = None,
        output_filename: Optional[Union[Path, str]] = None,
        voice_gender: str = "male",
    ) -> Path:
        """Gera o vídeo final 9:16 completo com áudio neural, card do Reddit, gameplay e legendas dinâmicas."""
        session_id = f"story_{uuid.uuid4().hex[:8]}"
        session_dir = self.temp_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        if output_filename:
            final_output = Path(output_filename)
            if not final_output.is_absolute():
                final_output = self.output_dir / final_output
        else:
            final_output = self.output_dir / f"{session_id}.mp4"

        final_output.parent.mkdir(parents=True, exist_ok=True)

        bg_path = self._ensure_background_exists(Path(background_video or self.default_bg_path))

        logger.info("Iniciando geração de história do Reddit: '%s'", story.title)

        try:
            # 1. Síntese de Voz Neural com Word Timestamps
            logger.info("Sintetizando locução neural com timestamps...")
            audio_path = session_dir / "voice.mp3"
            audio_file, words = self.synthesizer.synthesize(
                text=story.full_script,
                voice_gender=voice_gender,
                output_filename=audio_path,
            )

            if not audio_file.exists() or audio_file.stat().st_size == 0:
                raise StoryGenerationError("Falha na síntese do áudio da história.")

            # 2. Geração do Card do Reddit em PNG
            logger.info("Renderizando card visual do Reddit...")
            card_img = self.card_renderer.render_card(story, card_width=960)
            card_path = session_dir / "reddit_card.png"
            card_img.save(card_path, format="PNG")

            # 3. Geração das Legendas Dinâmicas em ASS (Estilo TikTok Karaokê)
            logger.info("Gerando legendas dinâmicas sincronizadas...")
            ass_content = generate_ass_subtitle(
                words=words,
                words_per_screen=3,
                highlight_color="&H0000FFFF",  # Amarelo vibrante (#FFFF00)
                primary_color="&H00FFFFFF",    # Branco puro
                outline_color="&H00000000",    # Borda preta grossa
                font_name="Arial",
                font_size=58,
                margin_v=420,  # Posicionamento centralizado no terço inferior
            )
            ass_path = session_dir / "subtitles.ass"
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)

            # 4. Renderização Final com FFmpeg
            # Escapa caminhos para o filtro do FFmpeg no Windows
            # No Windows, o filtro subtitles requer barras normais e dois-pontos escapados: C\:/...
            safe_ass_path = str(ass_path.resolve()).replace("\\", "/")
            if ":" in safe_ass_path:
                drive, rest = safe_ass_path.split(":", 1)
                safe_ass_path = f"{drive}\\:{rest}"

            logger.info("Renderizando vídeo final com card, gameplay e legendas dinâmicas...")

            # Filtro complexo:
            # - Input 0: gameplay background (vídeo)
            # - Input 1: reddit_card.png (overlay com fade-out aos 3.5s)
            # - Input 2: voz neural (áudio principal)
            # Overlay do card centralizado em X, Y=340, exibido nos primeiros 4 segundos
            # Após o card sumir, as legendas ASS dominam o centro de atenção
            filter_complex = (
                "[1:v]format=rgba,fade=t=out:st=3.2:d=0.6:alpha=1[card];"
                "[0:v][card]overlay=(W-w)/2:340:enable='lte(t,4.0)'[v_over];"
                f"[v_over]subtitles='{safe_ass_path}'[v_out]"
            )

            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1",  # Garante loop se a narração for mais longa que o clipe de fundo
                "-i", str(bg_path),
                "-i", str(card_path),
                "-i", str(audio_file),
                "-filter_complex", filter_complex,
                "-map", "[v_out]",
                "-map", "2:a",  # Áudio da narração neural
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

            self._run_ffmpeg(cmd, description="Renderização da História do Reddit")

            logger.info("Vídeo da história gerado com sucesso! Arquivo: %s (%.2f MB)", final_output, final_output.stat().st_size / (1024 * 1024))
            return final_output

        except Exception as e:
            logger.error("Erro na geração da história do Reddit: %s", e)
            raise
