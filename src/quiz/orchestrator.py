"""Orquestrador completo e agendador autônomo do pipeline de Quiz Viral (6 vídeos/dia)."""

from datetime import datetime
import logging
from pathlib import Path
from typing import Optional, Union

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import settings
from src.database import Database
from src.publisher.youtube import YouTubeShortsPublisher
from src.quiz.ai_curator import AIQuizCurator
from src.quiz.generator import QuizGenerator
from src.quiz.models import QuizData

logger = logging.getLogger(__name__)

DAILY_POST_LIMIT = 6


class QuizPipelineOrchestrator:
    """Orquestra a curadoria por IA, geração de vídeo e publicação diária no YouTube Shorts."""

    def __init__(
        self,
        db: Optional[Database] = None,
        curator: Optional[AIQuizCurator] = None,
        generator: Optional[QuizGenerator] = None,
        publisher: Optional[YouTubeShortsPublisher] = None,
        daily_limit: int = DAILY_POST_LIMIT,
    ):
        self.db = db or Database(settings.DB_PATH)
        self.curator = curator or AIQuizCurator()
        self.generator = generator or QuizGenerator()
        self.publisher = publisher or YouTubeShortsPublisher(privacy_status="public")
        self.daily_limit = daily_limit

    def run_cycle(self, category: Optional[str] = None) -> dict:
        """Executa um ciclo completo: Gera quiz com IA, renderiza vídeo e publica no YouTube."""
        # 1. Verifica cota diária
        posts_today = self.db.count_quizzes_today()
        logger.info("Ciclo do Quiz iniciado. Posts de quiz hoje: %d/%d", posts_today, self.daily_limit)

        if posts_today >= self.daily_limit:
            msg = f"Limite diário de {self.daily_limit} vídeos de quiz atingido para hoje. Aguardando próximo ciclo."
            logger.warning(msg)
            return {"success": False, "reason": "daily_limit_reached", "posts_today": posts_today}

        try:
            # 2. Curadoria com IA
            quiz: QuizData = self.curator.generate_quiz(category=category)
            logger.info("Quiz gerado pela IA: '%s' (%s)", quiz.title, quiz.theme.title)

            # 3. Renderização do Vídeo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"quiz_{timestamp}.mp4"
            video_path = self.generator.generate_video(quiz, output_filename=video_filename)
            logger.info("Vídeo do quiz renderizado: %s (%.2f MB)", video_path, video_path.stat().st_size / (1024 * 1024))

            # 4. Publicação no YouTube Shorts
            hashtags = ["Shorts", "quiz", "curiosidades", "conhecimento", "desafio", "viral"]
            result = self.publisher.publish(
                video_path=video_path,
                title=quiz.title,
                description=f"{quiz.intro_text}\n\n#Shorts #quiz #curiosidades",
                hashtags=hashtags,
            )

            # 5. Registro no Banco de Dados
            status = "published" if result.success else "failed"
            self.db.record_quiz(
                theme=quiz.theme.title,
                title=quiz.title,
                video_path=str(video_path),
                youtube_id=result.post_id if result.success else None,
                youtube_url=result.url if result.success else None,
                status=status,
            )

            if result.success:
                logger.info("🎉 Quiz publicado com sucesso no YouTube Shorts: %s", result.url)
                return {
                    "success": True,
                    "url": result.url,
                    "post_id": result.post_id,
                    "title": quiz.title,
                    "video_path": str(video_path),
                }
            else:
                logger.error("Falha na publicação do quiz: %s", result.error)
                return {"success": False, "error": result.error, "video_path": str(video_path)}

        except Exception as e:
            logger.error("Erro crítico no ciclo do quiz: %s", e)
            return {"success": False, "error": str(e)}

    def setup_scheduler(
        self,
        interval_hours: int = 4,
        run_immediately: bool = True,
        blocking: bool = True,
    ) -> Union[BlockingScheduler, BackgroundScheduler]:
        """Configura e inicia o agendador autônomo (6 vezes ao dia com intervalo de 4 horas)."""
        SchedulerClass = BlockingScheduler if blocking else BackgroundScheduler
        scheduler = SchedulerClass()

        scheduler.add_job(
            self.run_cycle,
            trigger="interval",
            hours=interval_hours,
            name="QuizPipeline_AutoPublisher",
            id="quiz_auto_publisher",
            replace_existing=True,
        )

        logger.info(
            "Agendador do Quiz iniciado! Frequência: 1 vídeo a cada %d horas (total de %d/dia)",
            interval_hours,
            24 // interval_hours,
        )

        if run_immediately:
            logger.info("Executando ciclo inicial imediato de Quiz...")
            self.run_cycle()

        if blocking:
            try:
                scheduler.start()
            except (KeyboardInterrupt, SystemExit):
                logger.info("Agendador do Quiz finalizado pelo usuário.")
        else:
            scheduler.start()

        return scheduler
