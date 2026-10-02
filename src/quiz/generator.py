"""Gerador automatizado de vídeos completos de Quiz em formato vertical para YouTube Shorts."""

import logging
from pathlib import Path
import subprocess
from typing import Optional, Union
import uuid

import src.config  # Garante FFmpeg no PATH
from src.config import settings
from src.dubbing.voice_synthesizer import VoiceSynthesizer
from src.quiz.frame_renderer import QuizFrameRenderer
from src.quiz.models import QuizData, QuizQuestion
from src.quiz.sfx import SoundEffectsGenerator

logger = logging.getLogger(__name__)


class QuizGenerationError(Exception):
    """Exceção levantada quando ocorre um erro na geração do vídeo de quiz."""


class QuizGenerator:
    """Orquestra a síntese de fala, efeitos visuais, temporização e montagem do vídeo de quiz."""

    def __init__(
        self,
        output_dir: Optional[Union[Path, str]] = None,
        temp_dir: Optional[Union[Path, str]] = None,
        voice_synthesizer: Optional[VoiceSynthesizer] = None,
        sfx_generator: Optional[SoundEffectsGenerator] = None,
        frame_renderer: Optional[QuizFrameRenderer] = None,
        voice_gender: str = "male",
    ):
        self.output_dir = Path(output_dir or settings.OUTPUT_DIR)
        self.temp_dir = Path(temp_dir or settings.TEMP_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.voice_gender = voice_gender
        self.synthesizer = voice_synthesizer or VoiceSynthesizer(temp_dir=self.temp_dir)
        self.sfx = sfx_generator or SoundEffectsGenerator(output_dir=self.temp_dir)
        self.renderer = frame_renderer or QuizFrameRenderer()

    def _run_ffmpeg(self, cmd: list[str], description: str = "") -> None:
        """Executa um comando FFmpeg com tratamento seguro de erros."""
        logger.debug("Executando FFmpeg: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if result.returncode != 0:
            err = result.stderr[-800:] if result.stderr else "Erro desconhecido"
            raise QuizGenerationError(f"Falha ao executar FFmpeg ({description}): {err}")

    def generate_video(
        self,
        quiz: QuizData,
        output_filename: Optional[Union[Path, str]] = None,
    ) -> Path:
        """Gera o vídeo vertical completo do quiz (Intro + Questões + Timer + Revelação + Outro)."""
        session_id = uuid.uuid4().hex[:8]
        session_dir = self.temp_dir / f"quiz_{session_id}"
        session_dir.mkdir(parents=True, exist_ok=True)

        if output_filename:
            dest = Path(output_filename)
            final_output = dest if dest.is_absolute() else self.output_dir / dest
        else:
            final_output = self.output_dir / f"quiz_{session_id}.mp4"

        try:
            logger.info("Iniciando geração de quiz: '%s' (%d perguntas)", quiz.title, len(quiz.questions))

            # 1. Gera efeitos sonoros universais
            countdown_audio = self.sfx.generate_countdown(duration_sec=3)
            ding_audio = self.sfx.generate_ding(duration_sec=1.2)

            segments: list[Path] = []
            total_q = len(quiz.questions)

            # 2. Segmento de Introdução
            logger.info("Renderizando introdução...")
            intro_audio, _ = self.synthesizer.synthesize(
                text=quiz.intro_text,
                voice_gender=self.voice_gender,
                output_filename=session_dir / "intro_speech.mp3",
            )
            intro_frame_path = session_dir / "intro_frame.png"
            intro_img = self.renderer.render_intro_frame(total_questions=total_q)
            intro_img.save(intro_frame_path)

            seg_intro = session_dir / "seg_00_intro.mp4"
            self._run_ffmpeg([
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(intro_frame_path),
                "-i", str(intro_audio),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "44100",
                "-ac", "2",
                "-pix_fmt", "yuv420p",
                "-shortest",
                str(seg_intro),
            ], description="Segmento de Introdução")
            segments.append(seg_intro)

            # 3. Segmentos para cada questão
            for idx, q in enumerate(quiz.questions):
                logger.info("Processando pergunta %d/%d: %s", idx + 1, total_q, q.question[:30])

                # 3a. Leitura da pergunta
                q_text = f"Pergunta {idx + 1}: {q.question}"
                q_audio, _ = self.synthesizer.synthesize(
                    text=q_text,
                    voice_gender=self.voice_gender,
                    output_filename=session_dir / f"q_{idx}_speech.mp3",
                )
                q_frame_path = session_dir / f"q_{idx}_frame.png"
                q_img = self.renderer.render_question_frame(
                    question=q,
                    q_idx=idx,
                    total_questions=total_q,
                    progress=1.0,
                    show_reveal=False,
                )
                q_img.save(q_frame_path)

                seg_read = session_dir / f"seg_{idx + 1}_01_read.mp4"
                self._run_ffmpeg([
                    "ffmpeg", "-y",
                    "-loop", "1",
                    "-i", str(q_frame_path),
                    "-i", str(q_audio),
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-tune", "stillimage",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-ar", "44100",
                    "-ac", "2",
                    "-pix_fmt", "yuv420p",
                    "-shortest",
                    str(seg_read),
                ], description=f"Pergunta {idx + 1} Leitura")
                segments.append(seg_read)

                # 3b. Contagem regressiva de 3 segundos com barra animada
                seg_countdown = session_dir / f"seg_{idx + 1}_02_timer.mp4"
                pipe_cmd = [
                    "ffmpeg", "-y",
                    "-f", "image2pipe",
                    "-vcodec", "png",
                    "-r", "30",
                    "-i", "-",
                    "-i", str(countdown_audio),
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-ar", "44100",
                    "-ac", "2",
                    "-shortest",
                    str(seg_countdown),
                ]
                proc = subprocess.Popen(
                    pipe_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                total_frames = 90  # 3 segundos a 30fps
                for f_num in range(total_frames):
                    progress = 1.0 - (f_num / total_frames)
                    frame = self.renderer.render_question_frame(
                        question=q,
                        q_idx=idx,
                        total_questions=total_q,
                        progress=progress,
                        show_reveal=False,
                    )
                    frame.save(proc.stdin, format="PNG")
                stdout, stderr = proc.communicate()
                if proc.returncode != 0:
                    raise QuizGenerationError(f"Erro ao renderizar contagem regressiva da pergunta {idx + 1}: {stderr}")
                segments.append(seg_countdown)

                # 3c. Revelação da resposta com som de acerto e narração
                reveal_phrase = (
                    f"A resposta correta é a letra {q.correct_letter}: {q.correct_text}! "
                    f"{q.explanation}".strip()
                )
                rev_audio, _ = self.synthesizer.synthesize(
                    text=reveal_phrase,
                    voice_gender=self.voice_gender,
                    output_filename=session_dir / f"q_{idx}_reveal.mp3",
                )
                # Mistura o ding no início da revelação
                mixed_reveal_audio = session_dir / f"q_{idx}_reveal_mixed.aac"
                self._run_ffmpeg([
                    "ffmpeg", "-y",
                    "-i", str(rev_audio),
                    "-i", str(ding_audio),
                    "-filter_complex",
                    "[0:a]volume=1.0[speech];[1:a]volume=0.85[bell];[speech][bell]amix=inputs=2:duration=longest[aout]",
                    "-map", "[aout]",
                    "-ar", "44100",
                    "-ac", "2",
                    str(mixed_reveal_audio),
                ], description=f"Pergunta {idx + 1} Áudio Revelação")

                rev_frame_path = session_dir / f"q_{idx}_reveal_frame.png"
                rev_img = self.renderer.render_question_frame(
                    question=q,
                    q_idx=idx,
                    total_questions=total_q,
                    progress=1.0,
                    show_reveal=True,
                )
                rev_img.save(rev_frame_path)

                seg_reveal = session_dir / f"seg_{idx + 1}_03_reveal.mp4"
                self._run_ffmpeg([
                    "ffmpeg", "-y",
                    "-loop", "1",
                    "-i", str(rev_frame_path),
                    "-i", str(mixed_reveal_audio),
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-tune", "stillimage",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-ar", "44100",
                    "-ac", "2",
                    "-pix_fmt", "yuv420p",
                    "-shortest",
                    str(seg_reveal),
                ], description=f"Pergunta {idx + 1} Vídeo Revelação")
                segments.append(seg_reveal)

            # 4. Segmento de Encerramento (Outro)
            logger.info("Renderizando encerramento...")
            outro_audio, _ = self.synthesizer.synthesize(
                text=quiz.outro_text,
                voice_gender=self.voice_gender,
                output_filename=session_dir / "outro_speech.mp3",
            )
            outro_frame_path = session_dir / "outro_frame.png"
            outro_img = self.renderer.render_outro_frame()
            outro_img.save(outro_frame_path)

            seg_outro = session_dir / "seg_99_outro.mp4"
            self._run_ffmpeg([
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(outro_frame_path),
                "-i", str(outro_audio),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "44100",
                "-ac", "2",
                "-pix_fmt", "yuv420p",
                "-shortest",
                str(seg_outro),
            ], description="Segmento de Encerramento")
            segments.append(seg_outro)

            # 5. Concatena todos os segmentos no arquivo final com trilha sonora de suspense
            logger.info("Concatenando %d segmentos e adicionando trilha sonora de suspense...", len(segments))
            concat_list_file = session_dir / "concat_list.txt"
            with open(concat_list_file, "w", encoding="utf-8") as f:
                for seg in segments:
                    safe_path = str(seg.resolve()).replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")

            temp_concatenated = session_dir / "concatenated_raw.mp4"
            self._run_ffmpeg([
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list_file),
                "-c", "copy",
                str(temp_concatenated),
            ], description="Concatenação dos Segmentos")

            # Gera trilha sonora de suspense com pulso rítmico a 120 BPM
            bgm_audio = self.sfx.generate_suspense_bgm(duration_sec=75.0, bpm=120.0)

            # Mixa a voz com a música de fundo (-18dB) e renderiza o arquivo final
            self._run_ffmpeg([
                "ffmpeg", "-y",
                "-i", str(temp_concatenated),
                "-i", str(bgm_audio),
                "-filter_complex",
                "[0:a]volume=1.0[voice];[1:a]volume=0.22[bgm];[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                str(final_output),
            ], description="Mixagem Final com Trilha de Suspense")

            logger.info("Vídeo de quiz finalizado com sucesso! Tamanho: %.2f MB", final_output.stat().st_size / (1024 * 1024))
            return final_output

        except Exception as e:
            logger.error("Erro na geração do quiz: %s", e)
            raise
