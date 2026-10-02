"""Ponto de entrada principal da aplicação AutoShorts Pipeline."""

import argparse
from datetime import datetime
import logging
import sys
from pathlib import Path

from src.config import settings
from src.database import Database
from src.orchestrator import PipelineOrchestrator

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("autoshorts.main")


def cmd_run(args: argparse.Namespace, orchestrator: PipelineOrchestrator) -> int:
    """Inicia o agendador contínuo 24/7 com APScheduler."""
    logger.info("Iniciando AutoShorts Pipeline em modo contínuo (24/7)...")
    scheduler = orchestrator.setup_scheduler(blocking=True)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Encerrando agendador AutoShorts...")
        scheduler.shutdown(wait=False)
    return 0


def cmd_add_channel(args: argparse.Namespace, db: Database) -> int:
    """Cadastra um novo canal no banco de dados para monitoramento contínuo."""
    channel_id = args.channel_id.strip()
    name = args.name.strip()
    language = getattr(args, "lang", "pt")
    channel = db.add_channel(channel_id=channel_id, name=name, language=language)
    logger.info(
        "Canal cadastrado com sucesso: %s (ID: %s, DB ID: %s, Idioma: %s)",
        channel.name,
        channel.channel_id,
        channel.id,
        channel.language,
    )
    print(f"Canal '{channel.name}' ({channel.channel_id}) cadastrado com sucesso [Idioma: {channel.language}].")
    return 0


def cmd_once(args: argparse.Namespace, orchestrator: PipelineOrchestrator) -> int:
    """Executa uma única rodada imediata de scouting e publicação."""
    logger.info("Executando rodada única imediata (scout + publish)...")
    scout_count = orchestrator.run_scout_cycle()
    pub_count = orchestrator.run_publishing_cycle()
    print(
        f"Rodada concluída: {scout_count} episódio(s) processado(s), {pub_count} post(s) publicado(s)."
    )
    return 0


def cmd_run_quiz(args: argparse.Namespace) -> int:
    """Inicia o agendador autônomo de Quizzes (6 vídeos/dia a cada 4 horas)."""
    from src.quiz.orchestrator import QuizPipelineOrchestrator

    logger.info("Iniciando Pipeline de Quiz Viral no piloto automático (6 vídeos/dia)...")
    interval = getattr(args, "interval_hours", 4)
    run_initial = not getattr(args, "no_initial", False)

    orchestrator = QuizPipelineOrchestrator()
    orchestrator.setup_scheduler(interval_hours=interval, run_immediately=run_initial, blocking=True)
    return 0


def cmd_generate_quiz(args: argparse.Namespace) -> int:
    """Gera um quiz com IA imediatamente e opcionalmente publica no YouTube."""
    from src.quiz.ai_curator import AIQuizCurator
    from src.quiz.generator import QuizGenerator
    from src.publisher.youtube import YouTubeShortsPublisher

    category = getattr(args, "category", None)
    should_post = getattr(args, "post", False)

    logger.info("Gerando Quiz imediatamente (Categoria: %s)...", category or "aleatória")
    curator = AIQuizCurator()
    quiz = curator.generate_quiz(category=category)

    generator = QuizGenerator()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = generator.generate_video(quiz, output_filename=f"quiz_{timestamp}.mp4")

    print(f"\nVídeo de Quiz gerado com sucesso!")
    print(f"Título: {quiz.title}")
    print(f"Arquivo: {video_path}")

    if should_post:
        logger.info("Publicando no YouTube Shorts...")
        publisher = YouTubeShortsPublisher(privacy_status="public")
        res = publisher.publish(
            video_path=video_path,
            title=quiz.title,
            description=f"{quiz.intro_text}\n\n#Shorts #quiz #curiosidades",
            hashtags=["Shorts", "quiz", "curiosidades", "desafio"],
        )
        if res.success:
            print(f"🎉 Publicado no YouTube: {res.url}")
            db = Database(settings.DB_PATH)
            db.record_quiz(
                theme=quiz.theme.title,
                title=quiz.title,
                video_path=str(video_path),
                youtube_id=res.post_id,
                youtube_url=res.url,
                status="published",
            )
        else:
            print(f"❌ Falha ao publicar: {res.error}")
            return 1

    return 0


def cmd_generate_story(args: argparse.Namespace) -> int:
    """Gera um vídeo de história do Reddit imediatamente com IA e gameplay de fundo."""
    from src.stories.ai_storyteller import AIStoryteller
    from src.stories.generator import RedditStoryGenerator

    theme = getattr(args, "theme", None)
    bg = getattr(args, "bg", None)
    gender = getattr(args, "gender", "male")

    logger.info("Gerando História do Reddit imediatamente (Tema: %s)...", theme or "aleatório")
    storyteller = AIStoryteller()
    story = storyteller.generate_story(theme=theme)

    generator = RedditStoryGenerator()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = generator.generate_video(
        story=story,
        background_video=bg,
        output_filename=f"reddit_story_{timestamp}.mp4",
        voice_gender=gender,
    )

    print(f"\n=======================================================")
    print(f"🎬 VÍDEO DE HISTÓRIA DO REDDIT GERADO COM SUCESSO!")
    print(f"Título: {story.title}")
    print(f"Subreddit: {story.subreddit} | Autor: {story.author}")
    print(f"Arquivo: {video_path}")
    print(f"Tamanho: {video_path.stat().st_size / (1024 * 1024):.2f} MB")
    print(f"Tags: {' '.join(story.tags)}")
    print(f"=======================================================\n")
    return 0


def cmd_generate_science(args: argparse.Namespace) -> int:
    """Gera um vídeo de artigo/descoberta científica com visual cósmico e legendas dinâmicas."""
    from src.science.ai_curator import AIScienceCurator
    from src.science.generator import ScienceShortsGenerator

    topic = getattr(args, "topic", None)
    bg = getattr(args, "bg", None)
    gender = getattr(args, "gender", "male")

    logger.info("Gerando Vídeo Científico imediatamente (Tópico: %s)...", topic or "aleatório")
    curator = AIScienceCurator()
    article = curator.generate_article(topic=topic)

    generator = ScienceShortsGenerator()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = generator.generate_video(
        article=article,
        background_video=bg,
        output_filename=f"science_shorts_{timestamp}.mp4",
        voice_gender=gender,
    )

    print(f"\n=======================================================")
    print(f"🔬 VÍDEO DE DESCOBERTA CIENTÍFICA GERADO COM SUCESSO!")
    print(f"Título: {article.title}")
    print(f"Revista: {article.journal} | Categoria: {article.category}")
    print(f"Arquivo: {video_path}")
    print(f"Tamanho: {video_path.stat().st_size / (1024 * 1024):.2f} MB")
    print(f"Tags: {' '.join(article.tags)}")
    print(f"=======================================================\n")
    return 0


def create_parser() -> argparse.ArgumentParser:
    """Constrói o parser de argumentos CLI."""
    parser = argparse.ArgumentParser(
        prog="autoshorts",
        description="AutoShorts Pipeline - Automação 24/7 de cortes e publicação",
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Comando a ser executado"
    )

    # Comando 'run'
    subparsers.add_parser("run", help="Inicia o loop contínuo 24/7 de cortes de podcasts")

    # Comando 'add-channel'
    add_parser = subparsers.add_parser("add-channel", help="Cadastra canal para monitorar")
    add_parser.add_argument("channel_id", help="ID do canal no YouTube (ex: UCxxxx...)")
    add_parser.add_argument("name", help="Nome descritivo do canal")
    add_parser.add_argument(
        "--lang",
        "--language",
        dest="lang",
        default="pt",
        choices=["pt", "en"],
        help="Idioma principal do canal (padrão: pt)",
    )

    # Comando 'once'
    subparsers.add_parser("once", help="Executa uma única rodada imediata (scout + publish)")

    # Comando 'run-quiz' (Piloto Automático 6 vídeos/dia)
    quiz_parser = subparsers.add_parser(
        "run-quiz", help="Inicia o piloto automático de Quizzes (6 vídeos/dia a cada 4 horas)"
    )
    quiz_parser.add_argument(
        "--interval-hours",
        type=int,
        default=4,
        help="Intervalo em horas entre cada vídeo publicado (padrão: 4h = 6 vídeos/dia)",
    )
    quiz_parser.add_argument(
        "--no-initial",
        action="store_true",
        help="Não executa um vídeo imediatamente na inicialização",
    )

    # Comando 'generate-quiz'
    gen_parser = subparsers.add_parser(
        "generate-quiz", help="Gera um vídeo de quiz imediatamente com IA"
    )
    gen_parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Categoria específica do quiz (ex: ciencia_e_universo, corpo_humano, etc.)",
    )
    gen_parser.add_argument(
        "--post",
        action="store_true",
        help="Publica automaticamente no YouTube Shorts após a renderização",
    )

    # Comando 'generate-story'
    story_parser = subparsers.add_parser(
        "generate-story", help="Gera um vídeo de história do Reddit imediatamente com IA e gameplay"
    )
    story_parser.add_argument(
        "--theme",
        type=str,
        default=None,
        help="Tema da história (ex: segredos_de_familia, fofoca_de_trabalho, relacionamentos_e_traicao, etc.)",
    )
    story_parser.add_argument(
        "--bg",
        type=str,
        default=None,
        help="Caminho personalizado para o vídeo de fundo (gameplay/satisfatório)",
    )
    story_parser.add_argument(
        "--gender",
        type=str,
        default="male",
        choices=["male", "female"],
        help="Gênero da voz neural (male ou female)",
    )

    # Comando 'generate-science'
    sci_parser = subparsers.add_parser(
        "generate-science", help="Gera um vídeo de artigo/descoberta científica imediatamente com IA e visual cósmico"
    )
    sci_parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Tópico científico (ex: biotecnologia_e_longevidade, astronomia_e_james_webb, etc.)",
    )
    sci_parser.add_argument(
        "--bg",
        type=str,
        default=None,
        help="Caminho personalizado para o vídeo de fundo espacial/científico",
    )
    sci_parser.add_argument(
        "--gender",
        type=str,
        default="male",
        choices=["male", "female"],
        help="Gênero da voz neural (male ou female)",
    )

    return parser


def main(argv=None) -> int:
    """Função principal CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)

    db = Database(settings.DB_PATH)
    orchestrator = PipelineOrchestrator(settings=settings, db=db)

    if args.command == "run":
        return cmd_run(args, orchestrator)
    elif args.command == "add-channel":
        return cmd_add_channel(args, db)
    elif args.command == "once":
        return cmd_once(args, orchestrator)
    elif args.command == "run-quiz":
        return cmd_run_quiz(args)
    elif args.command == "generate-quiz":
        return cmd_generate_quiz(args)
    elif args.command == "generate-story":
        return cmd_generate_story(args)
    elif args.command == "generate-science":
        return cmd_generate_science(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
