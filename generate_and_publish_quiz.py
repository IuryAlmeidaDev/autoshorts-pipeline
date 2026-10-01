"""Script para gerar um vídeo de Quiz vertical completo e publicá-lo no YouTube Shorts."""

import logging
from pathlib import Path
import sys

# Configura encoding do console do Windows para evitar crash com emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from src.config import settings
from src.publisher.youtube import YouTubeShortsPublisher
from src.quiz import QuizData, QuizGenerator, QuizQuestion, QuizTheme

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("QuizRunner")


def main():
    logger.info("=== INICIANDO PIPELINE DE QUIZ VIRAL ===")

    # 1. Monta as perguntas do Quiz
    q1 = QuizQuestion(
        question="Qual é o único mamífero capaz de voar de verdade?",
        options=["Esquilo-voador", "Morcego", "Pinguim", "Lêmure-voador"],
        correct_index=1,
        explanation="O morcego é o único mamífero com asas e voo sustentado!",
    )

    q2 = QuizQuestion(
        question="Quantos corações tem um polvo marinho?",
        options=["1 coração", "2 corações", "3 corações", "4 corações"],
        correct_index=2,
        explanation="O polvo tem 3 corações: dois para as brânquias e um para o corpo!",
    )

    q3 = QuizQuestion(
        question="Qual planeta tem o dia mais longo que o seu próprio ano?",
        options=["Marte", "Mercúrio", "Vênus", "Júpiter"],
        correct_index=2,
        explanation="Vênus demora 243 dias terrestres para girar e 225 para orbitar o Sol!",
    )

    theme = QuizTheme(
        title="DESAFIO DE CONHECIMENTOS",
        bg_gradient_top=(10, 15, 30),
        bg_gradient_mid=(30, 20, 60),
        bg_gradient_bot=(8, 12, 22),
    )

    quiz_data = QuizData(
        title="🧠 TESTE RÁPIDO DE INTELIGÊNCIA | Só 5% acertam todas!",
        questions=[q1, q2, q3],
        intro_text=(
            "Duvido você acertar essas três perguntas de conhecimentos gerais! "
            "Preste atenção e comente quantas você acertou!"
        ),
        outro_text=(
            "E aí, quantas você acertou? Comente o seu resultado abaixo "
            "e se inscreva no canal para o próximo desafio!"
        ),
        theme=theme,
    )

    # 2. Renderiza o vídeo
    generator = QuizGenerator(voice_gender="male")
    output_video_path = settings.OUTPUT_DIR / "quiz_conhecimentos_gerais_01.mp4"

    logger.info("Gerando vídeo em: %s", output_video_path)
    video_path = generator.generate_video(quiz_data, output_filename=output_video_path)

    logger.info("Vídeo gerado com sucesso! Arquivo: %s (%.2f MB)", video_path, video_path.stat().st_size / (1024 * 1024))

    # 3. Publica no YouTube Shorts
    logger.info("Iniciando publicação no YouTube Shorts...")
    publisher = YouTubeShortsPublisher(privacy_status="public")

    title = "🧠 TESTE DE INTELIGÊNCIA! Quantas você acerta? #Shorts"
    description = (
        "Duvido você acertar essas 3 perguntas de conhecimentos gerais!\n"
        "Comente sua pontuação: 0, 1, 2 ou 3? 👇\n\n"
        "Inscreva-se no canal para novos testes todos os dias! 🧠✨\n\n"
        "#Shorts #quiz #curiosidades #conhecimento #quiztime #desafio #perguntaserespostas"
    )
    hashtags = ["Shorts", "quiz", "curiosidades", "conhecimento", "desafio"]

    result = publisher.publish(
        video_path=video_path,
        title=title,
        description=description,
        hashtags=hashtags,
    )

    if result.success:
        logger.info("==================================================")
        logger.info("🎉 SUCESSO! VÍDEO PUBLICADO NO YOUTUBE SHORTS!")
        logger.info("URL: %s", result.url)
        logger.info("ID: %s", result.post_id)
        logger.info("==================================================")
        print(f"\nLINK_DO_SHORTS: {result.url}\n")
    else:
        logger.error("Falha ao publicar vídeo: %s", result.error)
        sys.exit(1)


if __name__ == "__main__":
    main()
