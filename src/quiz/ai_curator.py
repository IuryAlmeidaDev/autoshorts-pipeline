"""Módulo de geração autônoma de quizzes virais utilizando Inteligência Artificial (Gemini)."""

import json
import logging
import os
import random
import re
from typing import Any, Dict, List, Optional

try:
    from google import genai
except ImportError:
    genai = None  # type: ignore

from src.config import settings
from src.quiz.models import QuizData, QuizQuestion, QuizTheme

logger = logging.getLogger(__name__)

QUIZ_CATEGORIES = [
    "conhecimentos_gerais",
    "ciencia_e_universo",
    "corpo_humano",
    "animais_e_natureza",
    "historia_e_mitologia",
    "geografia_e_paises",
    "desafio_de_logica",
    "curiosidades_biblicas",
]

THEME_PALETTES = [
    # Paleta 1: Dark Indigo / Roxo
    {
        "bg_gradient_top": (10, 15, 30),
        "bg_gradient_mid": (30, 20, 60),
        "bg_gradient_bot": (8, 12, 22),
        "accent_color": (139, 92, 246),
        "card_border": (99, 102, 241),
    },
    # Paleta 2: Midnight Cyan / Teal
    {
        "bg_gradient_top": (8, 20, 28),
        "bg_gradient_mid": (12, 38, 52),
        "bg_gradient_bot": (6, 15, 22),
        "accent_color": (6, 182, 212),
        "card_border": (14, 165, 233),
    },
    # Paleta 3: Crimson Dark / Rubi
    {
        "bg_gradient_top": (25, 10, 18),
        "bg_gradient_mid": (48, 16, 32),
        "bg_gradient_bot": (18, 8, 14),
        "accent_color": (244, 63, 94),
        "card_border": (225, 29, 72),
    },
]

# Fallbacks pré-curados de alta qualidade caso a API esteja sem rede
FALLBACK_QUIZZES = [
    {
        "theme_title": "DESAFIO DE CIENCIA",
        "video_title": "TESTE DE CIENCIA! Quantas voce acerta? #Shorts",
        "description": "Duvido voce acertar 3 de 3! Comente sua pontuacao nos comentarios! #Shorts #quiz #ciencia #curiosidades",
        "intro_text": "Duvido voce acertar essas 3 perguntas sobre o universo e a ciencia! Comente quantas acertou!",
        "outro_text": "E ai, quantas voce acertou? Deixe nos comentarios e se inscreva para o proximo teste!",
        "questions": [
            {
                "question": "Qual e o planeta mais quente do nosso sistema solar?",
                "options": ["Mercurio", "Venus", "Marte", "Jupiter"],
                "correct_index": 1,
                "explanation": "Venus tem efeito estufa extremo e passa de 460 graus!",
            },
            {
                "question": "Qual e o osso mais longo do corpo humano?",
                "options": ["Femur", "Tibia", "Umero", "Costela"],
                "correct_index": 0,
                "explanation": "O femur fica na coxa e suporta ate 30 vezes o peso do corpo!",
            },
            {
                "question": "Quanto tempo a luz do Sol demora para chegar na Terra?",
                "options": ["Instantaneo", "8 minutos", "1 hora", "24 horas"],
                "correct_index": 1,
                "explanation": "A luz solar viaja a 300 mil km por segundo e leva 8 minutos e 20 segundos!",
            },
        ],
    },
    {
        "theme_title": "DESAFIO ANIMAIS E NATUREZA",
        "video_title": "TESTE DOS ANIMAIS! Voce sabe tudo? #Shorts",
        "description": "Voce conhece bem o reino animal? Comente quantos acertou! #Shorts #quiz #animais #natureza",
        "intro_text": "Tres perguntas incriveis sobre o reino animal! Sera que voce acerta todas?",
        "outro_text": "Quantas voce acertou? Deixe nos comentarios e se inscreva para mais!",
        "questions": [
            {
                "question": "Qual e o animal terrestre mais rapido do mundo?",
                "options": ["Leao", "Guepardo", "Antilope", "Lebre"],
                "correct_index": 1,
                "explanation": "O guepardo pode ultrapassar 110 km por hora em poucos segundos!",
            },
            {
                "question": "Qual animal tem a impressao digital identica a humana?",
                "options": ["Coala", "Chimpanze", "Golfinho", "Preguica"],
                "correct_index": 0,
                "explanation": "As digitais do coala sao tao parecidas que enganam peritos criminais!",
            },
            {
                "question": "Quantos cerebros tem uma sanguessuga?",
                "options": ["1", "4", "16", "32"],
                "correct_index": 3,
                "explanation": "O corpo da sanguessuga e dividido em 32 segmentos, cada um com um cerebro!",
            },
        ],
    },
]


def _extract_clean_json(text: str) -> Optional[dict]:
    """Extrai e faz parsing de bloco JSON a partir da resposta da LLM."""
    if not text:
        return None

    # Tenta bloco markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    candidate = match.group(1).strip() if match else text.strip()

    # Busca a primeira '{' e a última '}'
    first_b = candidate.find("{")
    last_b = candidate.rfind("}")
    if first_b != -1 and last_b != -1 and last_b > first_b:
        candidate = candidate[first_b : last_b + 1]

    try:
        return json.loads(candidate)
    except Exception as e:
        logger.warning("Falha ao decodificar JSON do quiz: %s", e)
        return None


def _remove_emojis(text: str) -> str:
    """Remove caracteres fora do BMP e emojis para evitar caixas de tofu na renderização."""
    if not isinstance(text, str):
        return ""
    # Remove emojis e caracteres fora da faixa comum
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff"  # Suplementares (emojis comuns)
        "\u2600-\u26ff"            # Símbolos diversos
        "\u2700-\u27bf"            # Dingbats
        "\u200d"                   # Zero-width joiner
        "\ufe0f"                   # Variation selector
        "]+",
        flags=re.UNICODE,
    )
    cleaned = emoji_pattern.sub("", text)
    # Limpa espaços extras resultantes da remoção
    return re.sub(r"\s+", " ", cleaned).strip()


class AIQuizCurator:
    """Gerador inteligente de perguntas e temas virais para quiz com Gemini."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-flash-latest"):
        if api_key is None:
            self.api_key = (
                getattr(settings, "GEMINI_API_KEY", "")
                or os.environ.get("GEMINI_API_KEY", "")
            ).strip()
        else:
            self.api_key = api_key.strip()
        self.model_name = model_name
        self.client = None

        if self.api_key and genai is not None:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning("Falha ao inicializar Gemini Client no AIQuizCurator: %s", e)

    def generate_quiz(
        self,
        category: Optional[str] = None,
        avoid_titles: Optional[List[str]] = None,
    ) -> QuizData:
        """Gera um quiz completo e inédito com 3 perguntas, título único, descrição e tema visual."""
        chosen_cat = category or random.choice(QUIZ_CATEGORIES)
        cat_formatted = chosen_cat.replace("_", " ").title()

        logger.info("Gerando quiz com IA para categoria: %s", cat_formatted)

        avoid_clause = ""
        if avoid_titles:
            recent_sample = [f"'{t}'" for t in avoid_titles[:8]]
            avoid_clause = f"\nIMPORTANTE: NÃO repita nenhum destes títulos já postados recentemente: {', '.join(recent_sample)}."

        prompt = f"""Atue como um roteirista viral de YouTube Shorts e TikTok especialista em Quizzes com milhões de visualizações.
Crie um quiz de alta retenção e curiosidade sobre a categoria: '{cat_formatted}'.

FORMATO DE RESPOSTA OBRIGATÓRIO (APENAS JSON PURO, SEM TEXTO ADICIONAL):
{{
  "theme_title": "DESAFIO DE {cat_formatted.upper()}",
  "video_title": "TÍTULO ÚNICO E CURIOSO BASEADO NA PERGUNTA MAIS CHOCANTE #Shorts",
  "description": "Duvido você acertar 3 de 3! Comente sua pontuação nos comentários! #Shorts #quiz #{chosen_cat}",
  "intro_text": "Duvido você acertar essas 3 perguntas! Preste atenção e comente quantas acertou!",
  "outro_text": "E aí, quantas você acertou? Deixe nos comentários e se inscreva para o próximo teste!",
  "questions": [
    {{
      "question": "Pergunta 1 chamativa e intrigante?",
      "options": ["Opção A", "Opção B", "Opção C", "Opção D"],
      "correct_index": 1,
      "explanation": "Explicação curta e surpreendente de no máximo 12 palavras."
    }},
    {{
      "question": "Pergunta 2 desafiadora?",
      "options": ["Opção A", "Opção B", "Opção C", "Opção D"],
      "correct_index": 2,
      "explanation": "Fato interessante sobre a resposta."
    }},
    {{
      "question": "Pergunta 3 que quase ninguém sabe?",
      "options": ["Opção A", "Opção B", "Opção C", "Opção D"],
      "correct_index": 0,
      "explanation": "Explicação fascinante final."
    }}
  ]
}}

REGRAS CRÍTICAS:
1. O 'video_title' DEVE SER 100% INÉDITO, MAGNÉTICO E ESPECÍFICO!
   Exemplos de ótimos títulos com gancho de curiosidade:
   - "3 Perguntas que 90% das pessoas erram! Você consegue?"
   - "Duvido você acertar a 3ª pergunta! Teste rápido"
   - "Qual o animal mais estranho do mundo? Quase todos erram!"
   NUNCA use títulos genéricos e repetidos!{avoid_clause}
2. NÃO USE NENHUM EMOJI nos campos theme_title, video_title, intro_text, outro_text, question, options ou explanation! Apenas texto limpo em português.
3. Cada pergunta DEVE ter exatamente 4 opções curtas (1 a 4 palavras cada).
4. Apenas 1 opção correta com correct_index (0 a 3).
5. Forneça exatamente 3 perguntas.
6. Fatos 100% verídicos e cientificamente/historicamente precisos.
"""

        parsed_data = None
        if self.client:
            for model in [self.model_name, "gemini-flash-lite-latest", "gemini-2.5-flash-lite"]:
                try:
                    res = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                    )
                    text = getattr(res, "text", "") or str(res)
                    parsed_data = _extract_clean_json(text)
                    if parsed_data and "questions" in parsed_data and len(parsed_data["questions"]) >= 3:
                        logger.info("Quiz gerado com sucesso via Gemini (%s)", model)
                        break
                except Exception as e:
                    logger.warning("Tentativa com modelo %s falhou: %s", model, e)
                    continue

        if not parsed_data or "questions" not in parsed_data:
            logger.info("Utilizando fallback curado para o quiz.")
            matching_fallback = None
            if chosen_cat:
                for fb in FALLBACK_QUIZZES:
                    fb_title = fb.get("theme_title", "").lower()
                    if any(part in fb_title for part in chosen_cat.lower().split("_")):
                        matching_fallback = fb
                        break
            parsed_data = matching_fallback or random.choice(FALLBACK_QUIZZES)

        # Higieniza e constrói as perguntas
        questions: List[QuizQuestion] = []
        for q_dict in parsed_data.get("questions", [])[:3]:
            q_text = _remove_emojis(q_dict.get("question", ""))
            raw_options = q_dict.get("options", [])
            options = [_remove_emojis(str(opt)) for opt in raw_options][:4]
            correct_idx = int(q_dict.get("correct_index", 0))
            explanation = _remove_emojis(q_dict.get("explanation", ""))

            # Valida limites
            if len(options) >= 2 and 0 <= correct_idx < len(options) and q_text:
                questions.append(
                    QuizQuestion(
                        question=q_text,
                        options=options,
                        correct_index=correct_idx,
                        explanation=explanation,
                    )
                )

        if len(questions) < 3:
            # Fallback seguro se alguma pergunta foi inválida
            fb = random.choice(FALLBACK_QUIZZES)
            return self._build_from_dict(fb)

        # Escolhe aleatoriamente uma paleta visual para dar variedade estética aos vídeos
        palette = random.choice(THEME_PALETTES)
        theme_title = _remove_emojis(parsed_data.get("theme_title", f"DESAFIO DE {cat_formatted.upper()}"))

        theme = QuizTheme(
            title=theme_title,
            bg_gradient_top=palette["bg_gradient_top"],
            bg_gradient_mid=palette["bg_gradient_mid"],
            bg_gradient_bot=palette["bg_gradient_bot"],
            accent_color=palette["accent_color"],
            card_border=palette["card_border"],
        )

        return QuizData(
            title=_remove_emojis(parsed_data.get("video_title", f"TESTE DE {cat_formatted.upper()}! #Shorts")),
            questions=questions,
            intro_text=_remove_emojis(parsed_data.get("intro_text", "Duvido você acertar essas três perguntas!")),
            outro_text=_remove_emojis(parsed_data.get("outro_text", "Quantas você acertou? Comente abaixo e se inscreva!")),
            theme=theme,
        )

    def _build_from_dict(self, d: Dict[str, Any]) -> QuizData:
        """Constrói instância de QuizData a partir de dicionário."""
        questions = [
            QuizQuestion(
                question=_remove_emojis(q["question"]),
                options=[_remove_emojis(opt) for opt in q["options"]],
                correct_index=q["correct_index"],
                explanation=_remove_emojis(q.get("explanation", "")),
            )
            for q in d["questions"]
        ]
        palette = random.choice(THEME_PALETTES)
        theme = QuizTheme(
            title=_remove_emojis(d["theme_title"]),
            bg_gradient_top=palette["bg_gradient_top"],
            bg_gradient_mid=palette["bg_gradient_mid"],
            bg_gradient_bot=palette["bg_gradient_bot"],
            accent_color=palette["accent_color"],
            card_border=palette["card_border"],
        )
        return QuizData(
            title=_remove_emojis(d["video_title"]),
            questions=questions,
            intro_text=_remove_emojis(d["intro_text"]),
            outro_text=_remove_emojis(d["outro_text"]),
            theme=theme,
        )
