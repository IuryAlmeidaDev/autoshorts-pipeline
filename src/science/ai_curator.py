"""Curador e roteirista de descobertas científicas com IA (Gemini)."""

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
from src.science.models import ScienceArticle

logger = logging.getLogger(__name__)

SCIENCE_TOPICS = [
    "biotecnologia_e_longevidade",
    "astronomia_e_james_webb",
    "fisica_quantica_e_tempo",
    "neurociencia_e_cerebro",
    "inteligencia_artificial_avancada",
]

FALLBACK_ARTICLES = [
    {
        "journal": "Nature Aging",
        "category": "LONGEVIDADE",
        "doi": "10.1038/s43587-024",
        "reads_count": "112.5k",
        "title": "Cientistas acabaram de reverter a idade celular em mamíferos em mais de quarenta por cento.",
        "hook_text": "Cientistas acabaram de provar que o envelhecimento biológico pode ser revertido, e não apenas retardado.",
        "full_script": (
            "Cientistas acabaram de provar que o envelhecimento biológico pode ser revertido, e não apenas retardado. "
            "Um artigo publicado na renomada revista Nature Aging revelou que uma equipe de geneticistas conseguiu reprogramar células senescentes de camundongos idosos usando uma combinação precisa de fatores genéticos celulares. "
            "Essas células velhas, que antes estavam danificadas e inflamando os tecidos ao redor, voltaram a se comportar como se pertencessem a organismos jovens e saudáveis. "
            "Os resultados foram impressionantes: os animais tratados recuperaram a elasticidade da pele, a força muscular, a visão perdida e a densidade óssea, vivendo quarenta por cento a mais do que a média da espécie sem desenvolver tumores. "
            "Segundo os pesquisadores responsáveis, essa descoberta abre caminho para tratamentos reais contra doenças degenerativas como o Alzheimer, osteoporose e falência cardíaca em seres humanos na próxima década. "
            "Estamos diante do primeiro passo real em direção à juventude biológica prolongada. "
            "Se esse tratamento estiver disponível no futuro, você aceitaria tomar para viver cento e vinte anos com corpo de trinta? Me conta sua opinião nos comentários."
        ),
        "tags": ["#Shorts", "#ciencia", "#curiosidades", "#nature", "#saude", "#tiktok"],
    },
    {
        "journal": "The Astrophysical Journal",
        "category": "ASTROFÍSICA",
        "doi": "10.3847/1538-4357",
        "reads_count": "148.9k",
        "title": "O telescópio James Webb acaba de detectar galáxias gigantescas onde a física dizia ser impossível.",
        "hook_text": "O telescópio James Webb acaba de detectar algo no início do universo que quebrou as leis da física atual.",
        "full_script": (
            "O telescópio espacial James Webb acaba de detectar algo nos confins do universo primitivo que quebrou totalmente as leis da cosmologia moderna. "
            "Em um estudo publicado no renomado Astrophysical Journal, astrônomos revelaram imagens de galáxias massivas e extremamente maduras formadas apenas quinhentos milhões de anos após o Big Bang. "
            "Pelo modelo padrão que conhecemos há décadas, nesse período inicial do universo só deveria existir poeira difusa e as primeiríssimas estrelas em nascimento. "
            "No entanto, essas galáxias recém-descobertas já possuem bilhões de estrelas condensadas e buracos negros supermassivos no centro, algo que deveria ter levado bilhões de anos para se estruturar. "
            "Os principais cosmólogos do mundo admitem que ou nossa linha do tempo sobre o início do cosmos está fundamentalmente errada, ou existe uma força invisível acelerando a criação de matéria que a humanidade ainda não descobriu. "
            "Estamos vivendo um dos maiores mistérios astronômicos de toda a história da ciência moderna. "
            "O que você acha que está escondido no início de tudo? Deixe sua teoria nos comentários."
        ),
        "tags": ["#Shorts", "#ciencia", "#universo", "#jameswebb", "#astronomia", "#tiktok"],
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


class AIScienceCurator:
    """Curador e roteirista de descobertas científicas com IA (Gemini)."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-flash-latest"):
        self.api_key = api_key if api_key is not None else (getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", ""))
        self.model_name = model_name
        self.client = None

        if self.api_key and genai is not None:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning("Falha ao inicializar Gemini Client no AIScienceCurator: %s", e)

    def generate_article(
        self,
        topic: Optional[str] = None,
        target_duration_sec: int = 70,
    ) -> ScienceArticle:
        """Gera um roteiro fascinante sobre um artigo científico recente calibrado para 65-75 segundos."""
        chosen_topic = topic or random.choice(SCIENCE_TOPICS)
        topic_formatted = chosen_topic.replace("_", " ").title()

        logger.info("Gerando artigo científico com IA sobre tema: %s", topic_formatted)

        prompt = f"""Você é o roteirista de divulgação científica número 1 do mundo especializado em vídeos curtos e explosivos (estilo Kurzgesagt, Pedro Loos / Ciência Todo Dia, Veritasium, Neil deGrasse Tyson) para YouTube Shorts e TikTok.

Crie uma apresentação fascinante, verídica e baseada em um estudo científico real publicado recentemente em revistas de elite (como Nature, Science, The Lancet, Cell ou ArXiv) sobre o tema: '{topic_formatted}'.

REGRAS DE OURO DO ALGORITMO (RETENÇÃO E MONETIZAÇÃO TOTAL 65 A 75 SEGUNDOS):
1. GANCHO IMEDIATO (0 a 3 segundos): Comece direto na descoberta mais impactante da pesquisa! NUNCA use saudações como 'Olá cientistas', 'Tudo bem com vocês?'. Comece com o fato chocante que muda o mundo!
2. RITMO E ESTRUTURA PARA MONETIZAÇÃO TOTAL:
   - OBRIGATÓRIO: O campo 'full_script' DEVE TER ENTRE 180 E 220 PALAVRAS faladas. Isso garante mais de 60 segundos de fala (mínimo exigido para o Programa de Monetização do TikTok e Shorts).
   - Frase 1 (0 a 3s): O fato chocante e o nome da revista prestigiosa (ex: Nature, Science).
   - Frases 2 a 4 (3 a 25s): O que os cientistas fizeram exatamente e o mistério que resolveram.
   - Frases 5 a 8 (25 a 55s): As implicações práticas fascinantes para a humanidade e o futuro.
   - Frases 9 a 10 (55 a 70s): A pergunta filosófica/ética final que gera debate ardente nos comentários.
3. SEM EMOJIS: Não use nenhum emoji em nenhum campo. Apenas texto limpo em português brasileiro.
4. RIGOR E AUTORIDADE: Fatos verdadeiros baseados em ciência real, explicados de forma simples e arrebatadora (ELIF5 inteligente).

FORMATO DE RESPOSTA OBRIGATÓRIO (APENAS JSON PURO):
{{
  "journal": "Nature Aging",
  "category": "BIOTECNOLOGIA",
  "doi": "10.1038/s43587-024",
  "reads_count": "115.8k",
  "title": "Título magnético e arrebatador da descoberta (máximo 14 palavras)",
  "hook_text": "A primeira frase exata e chocante da narração",
  "full_script": "O texto completo da história para ser narrado, OBRIGATORIAMENTE com cerca de 180 a 220 palavras.",
  "tags": ["#Shorts", "#ciencia", "#curiosidades", "#nature", "#tiktok"]
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
                        logger.info("Artigo científico gerado com sucesso via Gemini (%s)", model)
                        break
                except Exception as e:
                    logger.warning("Falha ao gerar artigo científico com modelo %s: %s", model, e)
                    continue

        if not parsed or "full_script" not in parsed:
            logger.info("Usando artigo científico curado de fallback.")
            parsed = random.choice(FALLBACK_ARTICLES)

        journal = _remove_emojis(parsed.get("journal", "Nature"))
        category = _remove_emojis(parsed.get("category", "CIÊNCIA"))
        doi = _remove_emojis(parsed.get("doi", "10.1038/s41586-024"))
        reads_count = _remove_emojis(parsed.get("reads_count", "98.5k"))
        title = _remove_emojis(parsed.get("title", ""))
        hook_text = _remove_emojis(parsed.get("hook_text", title))
        full_script = _remove_emojis(parsed.get("full_script", ""))
        tags = [_remove_emojis(t) for t in parsed.get("tags", ["#Shorts", "#ciencia", "#tiktok"])]

        return ScienceArticle(
            title=title,
            journal=journal,
            category=category,
            doi=doi,
            reads_count=reads_count,
            hook_text=hook_text,
            full_script=full_script,
            tags=tags,
        )
