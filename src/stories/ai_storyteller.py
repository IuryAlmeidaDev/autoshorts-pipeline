"""Módulo de geração e curadoria de histórias virais do Reddit com IA (Gemini)."""

import json
import logging
import os
import random
import re
from typing import List, Optional

try:
    from google import genai
except ImportError:
    genai = None

from src.config import settings
from src.stories.models import RedditStory

logger = logging.getLogger(__name__)

STORY_THEMES = [
    "segredos_de_familia",
    "fofoca_de_trabalho",
    "relacionamentos_e_traicao",
    "conflito_com_vizinhos",
    "vinganca_maligna_leves",
]

FALLBACK_STORIES = [
    {
        "subreddit": "r/desabafos",
        "author": "u/marcos_dev92",
        "upvotes": "18.4k",
        "comments_count": "1.8k",
        "title": "Descobri o maior segredo do meu chefe porque ele esqueceu o notebook na minha mesa.",
        "hook_text": "Eu descobri o segredo mais sujo do meu chefe porque ele esqueceu o notebook aberto na minha mesa.",
        "full_script": (
            "Eu descobri o segredo mais sujo do meu chefe porque ele esqueceu o notebook aberto na minha mesa. "
            "Ele sempre foi aquele tipo de líder arrogante que humilhava estagiários, cobrava metas impossíveis e ameaçava demitir qualquer um por bobeira. "
            "Ontem no final da tarde, ele saiu correndo desesperado para atender uma ligação e deixou a tela completamente desbloqueada em uma conversa do WhatsApp Web. "
            "A curiosidade falou mais alto. Quando bati o olho, vi que ele estava repassando os orçamentos e projetos sigilosos da nossa empresa diretamente para o nosso maior concorrente do mercado. "
            "E o pior de tudo: em troca, ele recebia uma comissão gorda por fora em uma conta de pessoa física no nome da própria esposa. "
            "Eu gelei na hora, mas mantive a calma e tirei fotos nítidas de cada conversa com o meu celular sem que ninguém percebesse. "
            "Hoje de manhã, reuni todas as provas e enviei um e-mail anônimo para o comitê de ética e diretamente para a presidência da empresa. "
            "O clima aqui está um caos absoluto, o RH acabou de fechar a sala dele e a polícia civil acabou de chegar no escritório para escoltar ele até a viatura. "
            "Você teria tido a coragem de denunciar ou ficaria na sua com medo de se queimar? Me conta a verdade nos comentários."
        ),
        "tags": ["#Shorts", "#reddit", "#historiasdoreddit", "#fofoca", "#trabalho", "#tiktok"],
    },
    {
        "subreddit": "r/relacionamentos",
        "author": "u/julia_silva_sp",
        "upvotes": "24.1k",
        "comments_count": "2.4k",
        "title": "Minha noiva me proibiu de convidar minha melhor amiga pro casamento, mas o motivo real me destruiu.",
        "hook_text": "Minha noiva me proibiu de convidar minha melhor amiga pro casamento, e o motivo real me destruiu.",
        "full_script": (
            "Minha noiva me proibiu de convidar minha melhor amiga de infância para o nosso casamento, e o motivo real me destruiu por completo. "
            "Nós namoramos há mais de quatro anos e estávamos com quase tudo pago e planejado para a cerimônia no final do próximo mês. "
            "Do nada, ela começou com uma crise obsessiva de ciúmes, exigindo que eu cortasse qualquer contato com a Ana, minha amiga há mais de quinze anos. "
            "Eu achei super estranho porque durante todos esses anos as duas sempre se deram super bem em todas as reuniões de família. "
            "Até que no último churrasco de domingo, o noivo da irmã da minha noiva bebeu além da conta e acabou deixando escapar toda a verdade. "
            "A minha noiva confessou em um grupo fechado que tinha ficado com o ex-namorado da Ana apenas um mês antes de começarmos a namorar sério, e tinha pavor das duas conversarem na festa e a história vir à tona na frente de todo mundo. "
            "Quando chamei ela para conversar, ela não apenas admitiu sem demonstrar nenhum remorso, como tentou inverter a situação e colocar a culpa toda em mim. "
            "Cancelei a festa, pedi meu dinheiro de volta e bloqueei ela em todas as redes sociais. "
            "Eu fui impulsivo demais ou você teria tomado exatamente a mesma atitude? Comenta aí sua opinião."
        ),
        "tags": ["#Shorts", "#reddit", "#relacionamento", "#traicao", "#casamento", "#tiktok"],
    },
]


def _remove_emojis(text: str) -> str:
    """Remove caracteres especiais e emojis para manter renderização impecável."""
    if not text:
        return ""
    clean = re.sub(r"[^\w\s.,!?:;\'\"\-\(\)/]", "", text)
    return re.sub(r"\s+", " ", clean).strip()


def _extract_clean_json(text: str) -> Optional[dict]:
    """Extrai objeto JSON válido de respostas do modelo."""
    if not text:
        return None
    try:
        clean = text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)
        return json.loads(clean.strip())
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return None


class AIStoryteller:
    """Gerador e curador de roteiros virais no estilo Reddit Stories utilizando Gemini."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-flash-latest"):
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.client = None

        if self.api_key and genai is not None:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning("Falha ao inicializar Gemini Client no AIStoryteller: %s", e)

    def generate_story(
        self,
        theme: Optional[str] = None,
        target_duration_sec: int = 70,
    ) -> RedditStory:
        """Gera uma história viral inédita do Reddit com gancho magnético e roteiro de alta retenção (65-75s)."""
        chosen_theme = theme or random.choice(STORY_THEMES)
        theme_formatted = chosen_theme.replace("_", " ").title()

        logger.info("Gerando história do Reddit com IA sobre tema: %s", theme_formatted)

        prompt = f"""Você é o roteirista número 1 do mundo especializado em 'Reddit Stories' virais para YouTube Shorts e TikTok (estilo r/desabafos, r/EuSouOBabaca, r/AskReddit com gameplay de fundo).

Crie uma história inédita, realista, em primeira pessoa, sobre o tema: '{theme_formatted}'.

REGRAS DE OURO DO ALGORITMO (MONETIZAÇÃO NO TIKTOK E YOUTUBE SHORTS):
1. GANCHO IMEDIATO (0 a 3 segundos): Comece direto no ápice do conflito! NUNCA diga 'Oi galera', 'Vim aqui desabafar' ou 'Tudo bem?'. Comece com algo chocante em primeira pessoa!
2. RITMO E ESTRUTURA PARA MONETIZAÇÃO TOTAL (65 a 75 segundos de narração):
   - OBRIGATÓRIO: O campo 'full_script' DEVE TER ENTRE 180 E 220 PALAVRAS faladas. Isso é um critério mandatório e inegociável para ultrapassar 60 segundos e monetizar no Programa Criativo do TikTok e YouTube Shorts.
   - Frase 1 (0 a 3s): O segredo/fato chocante que prende a atenção.
   - Frases 2 a 4 (3 a 25s): O desenrolar rápido e contexto da situação.
   - Frases 5 a 8 (25 a 55s): O clímax tenso, a reviravolta ou o confronto direto.
   - Frases 9 a 10 (55 a 70s): A consequência chocante e a pergunta engajadora final convidando a audiência a opinar nos comentários.
3. SEM EMOJIS: Não use emojis em nenhum campo.
4. TEXTO NATURAL: Escrita falada fluida em português brasileiro com ritmo dramático envolvente.

FORMATO DE RESPOSTA OBRIGATÓRIO (APENAS JSON PURO):
{{
  "subreddit": "r/desabafos",
  "author": "u/usuario_aleatorio",
  "upvotes": "19.3k",
  "comments_count": "1.7k",
  "title": "Título magnético e intrigante do post (máximo 14 palavras)",
  "hook_text": "A primeira frase exata e chocante da narração",
  "full_script": "O texto completo da história para ser narrado, OBRIGATORIAMENTE com cerca de 180 a 220 palavras.",
  "tags": ["#Shorts", "#reddit", "#historiasdoreddit", "#fofoca", "#tiktok"]
}}
"""

        parsed = None
        if self.client:
            for model in [self.model_name, "gemini-flash-lite-latest", "gemini-2.5-flash-lite"]:
                try:
                    res = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                    )
                    text = getattr(res, "text", "") or str(res)
                    parsed = _extract_clean_json(text)
                    if parsed and "title" in parsed and "full_script" in parsed:
                        logger.info("História gerada com sucesso via Gemini (%s)", model)
                        break
                except Exception as e:
                    logger.warning("Falha ao gerar história com modelo %s: %s", model, e)
                    continue

        if not parsed or "full_script" not in parsed:
            logger.info("Usando história curada de fallback.")
            parsed = random.choice(FALLBACK_STORIES)

        title = _remove_emojis(parsed.get("title", ""))
        subreddit = _remove_emojis(parsed.get("subreddit", "r/desabafos"))
        author = _remove_emojis(parsed.get("author", "u/anonimo_1994"))
        upvotes = _remove_emojis(parsed.get("upvotes", "15.2k"))
        comments_count = _remove_emojis(parsed.get("comments_count", "1.4k"))
        hook_text = _remove_emojis(parsed.get("hook_text", title))
        full_script = _remove_emojis(parsed.get("full_script", ""))
        tags = [_remove_emojis(t) for t in parsed.get("tags", ["#Shorts", "#reddit", "#tiktok"])]

        return RedditStory(
            title=title,
            subreddit=subreddit,
            author=author,
            upvotes=upvotes,
            comments_count=comments_count,
            hook_text=hook_text,
            full_script=full_script,
            tags=tags,
        )
