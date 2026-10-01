"""Orquestrador central do pipeline AutoShorts e integração com APScheduler."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import Settings, settings as default_settings
from src.database import Database
from src.models import Clip, Post, Video
from src.scout.monitor import Episode, ScoutMonitor
from src.curator.transcript import TranscriptFetcher
from src.curator.analyzer import CuratorAnalyzer
from src.editor.downloader import SurgicalDownloader
from src.editor.renderer import VideoRenderer
from src.editor.subtitles import extract_subtitles_with_whisper
from src.dubbing import VoiceSynthesizer
from src.publisher.base import BasePublisher, PublishResult
from src.publisher.youtube import YouTubeShortsPublisher
from src.publisher.instagram import InstagramReelsPublisher
from src.publisher.tiktok import TikTokPublisher
from src.publisher.kwai import KwaiPublisher

logger = logging.getLogger(__name__)

DEFAULT_PLATFORMS = ["youtube_shorts", "tiktok", "instagram_reels", "kwai"]

PLATFORM_ALIASES = {
    "youtube": "youtube_shorts",
    "youtube_shorts": "youtube_shorts",
    "instagram": "instagram_reels",
    "instagram_reels": "instagram_reels",
    "tiktok": "tiktok",
    "kwai": "kwai",
}


def _get_default_publishers(settings: Settings) -> Dict[str, BasePublisher]:
    """Instancia os publicadores padrão com base nas configurações e caminhos de segredos."""
    return {
        "youtube_shorts": YouTubeShortsPublisher(
            client_secrets_file=settings.YOUTUBE_CLIENT_SECRETS,
            credentials_file=settings.BASE_DIR / "secrets" / "youtube_token.json",
        ),
        "instagram_reels": InstagramReelsPublisher(
            access_token=settings.INSTAGRAM_ACCESS_TOKEN,
            instagram_account_id=settings.INSTAGRAM_ACCOUNT_ID,
        ),
        "tiktok": TikTokPublisher(
            session_path=settings.BASE_DIR / "secrets" / "tiktok_session.json",
        ),
        "kwai": KwaiPublisher(
            session_path=settings.BASE_DIR / "secrets" / "kwai_session.json",
        ),
    }


class PipelineOrchestrator:
    """Orquestrador ponta a ponta do AutoShorts Pipeline.
    
    Integra Scout, Curadoria, Download Cirúrgico, Reenquadramento 9:16 e Publicação Multiplataforma.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        db: Optional[Database] = None,
        publishers: Optional[Dict[str, BasePublisher]] = None,
        scout: Optional[ScoutMonitor] = None,
        transcript_fetcher: Optional[TranscriptFetcher] = None,
        curator: Optional[CuratorAnalyzer] = None,
        downloader: Optional[SurgicalDownloader] = None,
        renderer: Optional[VideoRenderer] = None,
        voice_synthesizer: Optional[VoiceSynthesizer] = None,
    ) -> None:
        self.settings = settings or default_settings
        self.db = db or Database(self.settings.DB_PATH)
        self.scout = scout or ScoutMonitor(db=self.db)
        self.transcript_fetcher = transcript_fetcher or TranscriptFetcher()
        self.curator = curator or CuratorAnalyzer(api_key=self.settings.GEMINI_API_KEY)
        self.downloader = downloader or SurgicalDownloader(temp_dir=self.settings.TEMP_DIR)
        self.renderer = renderer or VideoRenderer(
            temp_dir=self.settings.TEMP_DIR,
            output_dir=self.settings.OUTPUT_DIR,
        )
        self.voice_synthesizer = voice_synthesizer or VoiceSynthesizer(
            temp_dir=self.settings.TEMP_DIR,
        )

        raw_publishers = (
            publishers if publishers is not None else _get_default_publishers(self.settings)
        )
        self.publishers: Dict[str, BasePublisher] = {}
        for key, pub in raw_publishers.items():
            norm_key = PLATFORM_ALIASES.get(key.lower(), key.lower())
            self.publishers[norm_key] = pub

    def process_episode(self, episode: Episode) -> List[Clip]:
        """Processa um episódio recém-descoberto:
        
        1. Identifica idioma do canal (nacional vs internacional).
        2. Busca transcrição (com fallback de idiomas para canais internacionais).
        3. Analisa cortes virais com IA (traduzindo e adaptando roteiro se internacional).
        4. Para cada clipe: download cirúrgico -> síntese de voz (ou Whisper) -> render 9:16 -> agendamento de posts.
        5. Marca episódio como processado.
        """
        logger.info("Processando episódio: %s (%s)", episode.title, episode.video_id)

        channel = self.db.get_channel(episode.channel_id) if hasattr(self.db, "get_channel") else None
        is_international = channel is not None and getattr(channel, "language", "pt") == "en"

        # 1. Busca da transcrição
        if is_international:
            segments = self.transcript_fetcher.fetch_transcript(
                episode.video_id, languages=["en", "en-US"]
            )
        else:
            segments = self.transcript_fetcher.fetch_transcript(episode.video_id)

        if not segments:
            logger.warning("Nenhuma transcrição encontrada para o vídeo %s.", episode.video_id)
            self.db.mark_video_processed(
                youtube_id=episode.video_id,
                channel_id=episode.channel_id,
                title=episode.title,
            )
            return []

        # 2. Análise de curadoria com Gemini
        formatted_transcript = self.transcript_fetcher.format_transcript_with_timestamps(segments)
        if is_international:
            clips_metadata = self.curator.analyze_and_translate_transcript(
                formatted_transcript,
                max_clips=self.settings.MAX_CLIPS_PER_VIDEO,
                min_duration=self.settings.MIN_CLIP_DURATION,
                max_duration=self.settings.MAX_CLIP_DURATION,
            )
        else:
            clips_metadata = self.curator.analyze_transcript(
                formatted_transcript,
                max_clips=self.settings.MAX_CLIPS_PER_VIDEO,
                min_duration=self.settings.MIN_CLIP_DURATION,
                max_duration=self.settings.MAX_CLIP_DURATION,
            )

        if not clips_metadata:
            logger.warning("Nenhum momento viral identificado para o vídeo %s.", episode.video_id)
            self.db.mark_video_processed(
                youtube_id=episode.video_id,
                channel_id=episode.channel_id,
                title=episode.title,
            )
            return []

        # 3. Registra vídeo no banco de dados
        video_record = self.db.mark_video_processed(
            youtube_id=episode.video_id,
            channel_id=episode.channel_id,
            title=episode.title,
        )

        processed_clips: List[Clip] = []

        # 4. Processa cada clipe identificado
        for idx, clip_meta in enumerate(clips_metadata, start=1):
            logger.info(
                "Gerando corte %d/%d: '%s' [%.1fs -> %.1fs]",
                idx,
                len(clips_metadata),
                clip_meta.hook_title,
                clip_meta.start_time,
                clip_meta.end_time,
            )

            # Download cirúrgico do trecho
            raw_video = self.downloader.download_segment(
                video_id=episode.video_id,
                start_time=clip_meta.start_time,
                end_time=clip_meta.end_time,
            )

            output_name = f"{episode.video_id}_{idx}_{int(clip_meta.start_time)}_{int(clip_meta.end_time)}.mp4"

            if is_international and clip_meta.translated_script:
                # Síntese neural de voz em português com word timestamps
                dubbing_audio, words = self.voice_synthesizer.synthesize(
                    clip_meta.translated_script,
                    voice_gender=clip_meta.voice_gender,
                )

                # Renderização vertical 9:16 com dublagem e ducking do áudio de fundo
                rendered_path = self.renderer.render_clip(
                    input_video=raw_video,
                    hook_text=clip_meta.hook_title,
                    words=words,
                    output_name=output_name,
                    dubbing_audio=dubbing_audio,
                    ducking_volume=0.15,
                )

                # Limpeza do áudio de dublagem temporário
                if dubbing_audio and Path(dubbing_audio).exists():
                    try:
                        Path(dubbing_audio).unlink()
                    except Exception:
                        pass
            else:
                # Fluxo padrão nacional ou fallback sem roteiro traduzido
                words = None
                try:
                    words = extract_subtitles_with_whisper(raw_video)
                except Exception as exc:
                    logger.warning(
                        "Falha ao extrair legendas via Whisper para '%s': %s. Continuando sem legendas.",
                        clip_meta.hook_title,
                        exc,
                    )
                    words = None

                # Renderização 9:16 com gancho e legendas
                rendered_path = self.renderer.render_clip(
                    input_video=raw_video,
                    hook_text=clip_meta.hook_title,
                    words=words,
                    output_name=output_name,
                )

            # Limpeza do download bruto
            if raw_video.exists() and raw_video.resolve() != rendered_path.resolve():
                try:
                    raw_video.unlink()
                except Exception:
                    pass

            # Salva clipe no banco de dados
            clip = self.db.save_clip(
                video_id=video_record.id,
                start_time=clip_meta.start_time,
                end_time=clip_meta.end_time,
                hook_title=clip_meta.hook_title,
                viral_score=clip_meta.viral_score,
                file_path=str(rendered_path),
                status="ready",
            )

            # Agenda publicações para todas as plataformas configuradas
            for platform in DEFAULT_PLATFORMS:
                self.db.create_post(clip_id=clip.id, platform=platform, status="pending")

            processed_clips.append(clip)

        return processed_clips

    def run_scout_cycle(self) -> int:
        """Executa um ciclo completo de varredura nos canais monitorados.
        
        Returns:
            Quantidade de episódios processados com sucesso.
        """
        logger.info("Iniciando ciclo de scouting nos canais monitorados...")
        episodes = self.scout.scan_all_channels()
        logger.info("Encontrados %d episódios novos para processamento.", len(episodes))

        processed_count = 0
        for episode in episodes:
            try:
                self.process_episode(episode)
                processed_count += 1
            except Exception as exc:
                logger.error(
                    "Erro ao processar episódio %s (%s): %s",
                    episode.title,
                    episode.video_id,
                    exc,
                    exc_info=True,
                )

        return processed_count

    def run_publishing_cycle(self) -> int:
        """Executa um ciclo de publicação para postagens pendentes.
        
        Remove o arquivo de vídeo do clipe quando todas as suas postagens forem concluídas.

        Returns:
            Quantidade de postagens publicadas com sucesso neste ciclo.
        """
        logger.info("Iniciando ciclo de publicação de postagens pendentes...")
        pending_posts = self.db.get_pending_posts()
        posted_count = 0

        for post in pending_posts:
            norm_platform = PLATFORM_ALIASES.get(post.platform.lower(), post.platform.lower())
            publisher = self.publishers.get(norm_platform)

            if not publisher:
                logger.warning(
                    "Nenhum publicador configurado para a plataforma '%s'. Post %d ignorado.",
                    post.platform,
                    post.id,
                )
                continue

            clip = self.db.get_clip(post.clip_id)
            if not clip or not clip.file_path or not Path(clip.file_path).exists():
                err_msg = f"Arquivo do clipe não encontrado: {clip.file_path if clip else 'registro inexistente'}"
                logger.warning(err_msg)
                self.db.update_post_status(post.id, status="failed", error_log=err_msg)
                continue

            try:
                result = publisher.publish(
                    video_path=clip.file_path,
                    title=clip.hook_title,
                    description=clip.hook_title,
                    hashtags=["#shorts", "#viral"],
                )
                if result.success:
                    self.db.update_post_status(
                        post.id,
                        status="posted",
                        external_post_id=result.post_id,
                    )
                    posted_count += 1
                else:
                    self.db.update_post_status(
                        post.id,
                        status="failed",
                        error_log=result.error or "Falha desconhecida na publicação",
                    )
            except Exception as exc:
                logger.error("Erro ao publicar post %d na plataforma %s: %s", post.id, post.platform, exc)
                self.db.update_post_status(post.id, status="failed", error_log=str(exc))

            # Verifica se restam posts pendentes para este mesmo clipe
            all_pending = self.db.get_pending_posts()
            has_pending = any(p.clip_id == post.clip_id for p in all_pending)
            if not has_pending:
                # Todos os posts deste clipe foram processados; remove o arquivo temporário
                if clip.file_path and Path(clip.file_path).exists():
                    try:
                        Path(clip.file_path).unlink()
                        logger.info(
                            "Arquivo de vídeo %s removido após conclusão de todas as postagens do clipe %d.",
                            clip.file_path,
                            clip.id,
                        )
                    except Exception as err:
                        logger.warning("Falha ao remover arquivo de vídeo %s: %s", clip.file_path, err)

        return posted_count

    def setup_scheduler(
        self, blocking: bool = False
    ) -> Union[BackgroundScheduler, BlockingScheduler]:
        """Configura os jobs periódicos de scout e publicação com APScheduler."""
        from datetime import datetime

        scheduler = BlockingScheduler() if blocking else BackgroundScheduler()

        scheduler.add_job(
            self.run_scout_cycle,
            "interval",
            minutes=self.settings.POLL_INTERVAL_MINUTES,
            id="scout_cycle",
            replace_existing=True,
            next_run_time=datetime.now(),
        )

        scheduler.add_job(
            self.run_publishing_cycle,
            "interval",
            hours=self.settings.POST_INTERVAL_HOURS,
            id="publishing_cycle",
            replace_existing=True,
        )

        return scheduler
