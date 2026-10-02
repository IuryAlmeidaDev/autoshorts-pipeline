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
        "journal": "Nature",
        "category": "BIOTECNOLOGIA",
        "doi": "10.1038/s41586-024",
        "reads_count": "138.4k",
        "title": "Cientistas conseguem estender a vida em vinte e cinco por cento bloqueando proteína",
        "hook_text": "Cientistas acabaram de provar que desligar uma única proteína pode aumentar a vida em vinte e cinco por cento.",
        "segments": [
            {
                "speaker": "male",
                "text": "Cientistas acabaram de provar que desligar uma única proteína do nosso corpo pode aumentar a expectativa de vida em vinte e cinco por cento. Esse estudo histórico acabou de ser publicado na prestigiosa revista Nature."
            },
            {
                "speaker": "female",
                "text": "A pesquisa foi conduzida pela Faculdade de Medicina Duke-NUS em parceria com pesquisadores de Londres. Eles descobriram que conforme envelhecemos, uma proteína inflamatória chamada interleucina onze se acumula nos órgãos, acelerando drasticamente o envelhecimento celular."
            },
            {
                "speaker": "male",
                "text": "Nos testes de laboratório, os cientistas bloquearam essa proteína em cobaias idosas. O resultado chocou a medicina: os animais não apenas viveram muito mais, como ganharam força muscular jovem, eliminaram gordura prejudicial e regeneraram tecidos vitais sem desenvolver tumores."
            },
            {
                "speaker": "female",
                "text": "Os primeiros testes clínicos com anticorpos em seres humanos já começaram para combater fibroses e doenças crônicas da idade. Se essa terapia for aprovada no futuro, você tomaria para chegar aos cem anos com a saúde de quarenta? Comenta aqui embaixo sua opinião."
            }
        ],
        "full_script": (
            "Cientistas acabaram de provar que desligar uma única proteína do nosso corpo pode aumentar a expectativa de vida em vinte e cinco por cento. Esse estudo histórico acabou de ser publicado na prestigiosa revista Nature. "
            "A pesquisa foi conduzida pela Faculdade de Medicina Duke-NUS em parceria com pesquisadores de Londres. Eles descobriram que conforme envelhecemos, uma proteína inflamatória chamada interleucina onze se acumula nos órgãos, acelerando drasticamente o envelhecimento celular. "
            "Nos testes de laboratório, os cientistas bloquearam essa proteína em cobaias idosas. O resultado chocou a medicina: os animais não apenas viveram muito mais, como ganharam força muscular jovem, eliminaram gordura prejudicial e regeneraram tecidos vitais sem desenvolver tumores. "
            "Os primeiros testes clínicos com anticorpos em seres humanos já começaram para combater fibroses e doenças crônicas da idade. "
            "Se essa terapia for aprovada no futuro, você tomaria para chegar aos cem anos com a saúde de quarenta? Comenta aqui embaixo sua opinião."
        ),
        "tags": ["#Shorts", "#ciencia", "#biologia", "#curiosidades", "#nature", "#tiktok"],
    },
    {
        "journal": "The Astrophysical Journal",
        "category": "ASTROFÍSICA",
        "doi": "10.3847/1538-4357",
        "reads_count": "152.1k",
        "title": "O telescópio James Webb acaba de detectar galáxias gigantescas onde a física dizia ser impossível.",
        "hook_text": "O telescópio James Webb acaba de detectar algo no início do universo que quebrou as leis da física atual.",
        "segments": [
            {
                "speaker": "male",
                "text": "O telescópio espacial James Webb acaba de detectar algo nos confins do universo primitivo que quebrou totalmente as leis da cosmologia moderna. Esse estudo foi publicado no renomado Astrophysical Journal."
            },
            {
                "speaker": "female",
                "text": "Astrônomos identificaram galáxias massivas e extremamente maduras formadas apenas quinhentos milhões de anos após o Big Bang. Pelo modelo padrão que conhecemos há décadas, nesse período inicial só deveria existir poeira difusa e as primeiríssimas estrelas em nascimento."
            },
            {
                "speaker": "male",
                "text": "No entanto, essas galáxias recém-descobertas já possuem bilhões de estrelas condensadas e buracos negros supermassivos no centro, algo que deveria ter levado bilhões de anos para se estruturar."
            },
            {
                "speaker": "female",
                "text": "Os principais cosmólogos do mundo admitem que nossa linha do tempo sobre o início do cosmos está errada, ou existe uma força invisível acelerando a criação de matéria. O que você acha que está escondido no início de tudo? Deixe sua teoria nos comentários."
            }
        ],
        "full_script": (
            "O telescópio espacial James Webb acaba de detectar algo nos confins do universo primitivo que quebrou totalmente as leis da cosmologia moderna. Esse estudo foi publicado no renomado Astrophysical Journal. "
            "Astrônomos identificaram galáxias massivas e extremamente maduras formadas apenas quinhentos milhões de anos após o Big Bang. Pelo modelo padrão que conhecemos há décadas, nesse período inicial só deveria existir poeira difusa e as primeiríssimas estrelas em nascimento. "
            "No entanto, essas galáxias recém-descobertas já possuem bilhões de estrelas condensadas e buracos negros supermassivos no centro, algo que deveria ter levado bilhões de anos para se estruturar. "
            "Os principais cosmólogos do mundo admitem que nossa linha do tempo sobre o início do cosmos está errada, ou existe uma força invisível acelerando a criação de matéria. "
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

O vídeo é apresentado por DOIS CIENTISTAS que intercalam a narração (Homem e Mulher), mantendo a atenção no nível máximo e evitando fadiga auditiva!

REGRAS DE OURO DO ALGORITMO (RETENÇÃO E MONETIZAÇÃO TOTAL 65 A 75 SEGUNDOS):
1. GANCHO IMEDIATO (0 a 3 segundos): Comece direto na descoberta mais impactante da pesquisa! NUNCA use saudações como 'Olá cientistas', 'Tudo bem com vocês?'. Comece com o fato chocante que muda o mundo!
2. RITMO E ESTRUTURA PARA MONETIZAÇÃO TOTAL:
   - OBRIGATÓRIO: A soma de todas as falas DEVE TER ENTRE 180 E 220 PALAVRAS. Isso garante mais de 60 segundos de fala (mínimo exigido para o Programa de Monetização do TikTok e Shorts).
   - Segmento 1 (speaker: 'male', 0 a 15s): O apresentador abre com o gancho bombástico e cita a revista de prestígio (ex: Nature, Science).
   - Segmento 2 (speaker: 'female', 15 a 35s): A cientista explica o mecanismo e a descoberta de forma simples e fascinante.
   - Segmento 3 (speaker: 'male', 35 a 55s): O apresentador traz os resultados práticos chocantes e dados das cobaias/testes.
   - Segmento 4 (speaker: 'female', 55 a 70s): A cientista traz as implicações humanas futuras e a pergunta instigante final que gera comentários.
3. SEM EMOJIS: Não use nenhum emoji em nenhum campo. Apenas texto limpo em português brasileiro.
4. RIGOR E AUTORIDADE: Fatos verdadeiros baseados em ciência real, explicados de forma simples e arrebatadora (ELIF5 inteligente).

FORMATO DE RESPOSTA OBRIGATÓRIO (APENAS JSON PURO):
{{
  "journal": "Nature",
  "category": "BIOTECNOLOGIA",
  "doi": "10.1038/s41586-024",
  "reads_count": "135.2k",
  "title": "Título magnético e arrebatador da descoberta (máximo 14 palavras)",
  "hook_text": "A primeira frase exata e chocante da narração",
  "segments": [
    {{"speaker": "male", "text": "Texto do segmento 1 narrado pela voz masculina..."}},
    {{"speaker": "female", "text": "Texto do segmento 2 narrado pela voz feminina..."}},
    {{"speaker": "male", "text": "Texto do segmento 3 narrado pela voz masculina..."}},
    {{"speaker": "female", "text": "Texto do segmento 4 narrado pela voz feminina..."}}
  ],
  "full_script": "O texto completo concatenado de todos os segmentos (180 a 220 palavras).",
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
                    if parsed and "title" in parsed and ("segments" in parsed or "full_script" in parsed):
                        logger.info("Artigo científico gerado com sucesso via Gemini (%s)", model)
                        break
                except Exception as e:
                    logger.warning("Falha ao gerar artigo científico com modelo %s: %s", model, e)
                    continue

        if not parsed or ("full_script" not in parsed and "segments" not in parsed):
            logger.info("Usando artigo científico curado de fallback.")
            parsed = random.choice(FALLBACK_ARTICLES)

        journal = _remove_emojis(parsed.get("journal", "Nature"))
        category = _remove_emojis(parsed.get("category", "CIÊNCIA"))
        doi = _remove_emojis(parsed.get("doi", "10.1038/s41586-024"))
        reads_count = _remove_emojis(parsed.get("reads_count", "98.5k"))
        title = _remove_emojis(parsed.get("title", ""))
        hook_text = _remove_emojis(parsed.get("hook_text", title))
        
        # Processamento dos segmentos com alternância de vozes
        raw_segments = parsed.get("segments", [])
        segments = []
        if isinstance(raw_segments, list) and raw_segments:
            for s in raw_segments:
                if isinstance(s, dict):
                    spk = "female" if str(s.get("speaker", "")).lower() == "female" else "male"
                    clean_s_text = _remove_emojis(s.get("text", ""))
                    if clean_s_text:
                        segments.append({"speaker": spk, "text": clean_s_text})

        full_script = _remove_emojis(parsed.get("full_script", ""))
        if not full_script and segments:
            full_script = " ".join(s["text"] for s in segments)
        elif full_script and not segments:
            segments = [{"speaker": "male", "text": full_script}]

        tags = [_remove_emojis(t) for t in parsed.get("tags", ["#Shorts", "#ciencia", "#tiktok"])]

        return ScienceArticle(
            title=title,
            journal=journal,
            category=category,
            doi=doi,
            reads_count=reads_count,
            hook_text=hook_text,
            full_script=full_script,
            segments=segments,
            tags=tags,
        )
