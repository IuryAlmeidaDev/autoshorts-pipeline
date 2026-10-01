"""Ponto de entrada principal da aplicação AutoShorts Pipeline."""

import argparse
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
    subparsers.add_parser("run", help="Inicia o loop contínuo 24/7 com APScheduler")

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

    return 0


if __name__ == "__main__":
    sys.exit(main())
