"""Módulo de curadoria e identificação de momentos virais com IA (Gemini)."""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from google import genai
except ImportError:
    genai = None  # type: ignore

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ClipMetadata:
    """Metadados e corte identificado pela IA curadora."""

    start_time: float
    end_time: float
    hook_title: str
    description: str = ""
    hashtags: List[str] = field(default_factory=list)
    viral_score: float = 0.0

    @property
    def duration(self) -> float:
        """Duração total do clipe em segundos."""
        return max(0.0, round(self.end_time - self.start_time, 2))


def _extract_json_snippet(text: str) -> str:
    """Extrai blocos JSON ou conteúdo delimitado de markdown."""
    # Procura por blocos ```json ... ``` ou ``` ... ```
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if code_block_match:
        return code_block_match.group(1).strip()

    # Procura pelo primeiro '[' ou '{' e último ']' ou '}'
    first_bracket = text.find("[")
    first_brace = text.find("{")
    
    start_idx = -1
    if first_bracket != -1 and first_brace != -1:
        start_idx = min(first_bracket, first_brace)
    elif first_bracket != -1:
        start_idx = first_bracket
    elif first_brace != -1:
        start_idx = first_brace

    if start_idx != -1:
        last_bracket = text.rfind("]")
        last_brace = text.rfind("}")
        end_idx = max(last_bracket, last_brace)
        if end_idx > start_idx:
            return text[start_idx : end_idx + 1].strip()

    return text.strip()


def parse_llm_clip_response(
    raw_text: Optional[str],
    min_duration: float = 0.0,
    max_duration: float = float("inf"),
) -> List[ClipMetadata]:
    """Converte e valida a resposta textual da LLM em instâncias de ClipMetadata.

    Trata blocos markdown, JSON malformado e valida limites temporais.
    """
    if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
        return []

    cleaned_json_str = _extract_json_snippet(raw_text)

    try:
        parsed_data = json.loads(cleaned_json_str)
    except json.JSONDecodeError as exc:
        logger.warning("Falha ao decodificar JSON retornado pela LLM: %s", exc)
        return []

    # Normaliza se o retorno vier encapsulado em dicionário: {"clips": [...]}
    clip_dicts: List[Dict[str, Any]] = []
    if isinstance(parsed_data, list):
        clip_dicts = parsed_data
    elif isinstance(parsed_data, dict):
        if "clips" in parsed_data and isinstance(parsed_data["clips"], list):
            clip_dicts = parsed_data["clips"]
        else:
            clip_dicts = [parsed_data]
    else:
        return []

    clips: List[ClipMetadata] = []

    for item in clip_dicts:
        if not isinstance(item, dict):
            continue

        try:
            start_time = float(item.get("start_time", item.get("start", 0.0)))
            end_time = float(item.get("end_time", item.get("end", 0.0)))
        except (ValueError, TypeError):
            continue

        if start_time < 0 or end_time <= start_time:
            logger.debug("Clipe ignorado por tempos inválidos: start=%s, end=%s", start_time, end_time)
            continue

        duration = end_time - start_time
        if min_duration > 0 and duration < min_duration:
            logger.debug("Clipe ignorado por duração inferior a %ss: %ss", min_duration, duration)
            continue
        if max_duration < float("inf") and duration > max_duration:
            logger.debug("Clipe ignorado por duração superior a %ss: %ss", max_duration, duration)
            continue

        hook_title = str(item.get("hook_title", item.get("title", "Corte Viral"))).strip()
        description = str(item.get("description", "")).strip()

        raw_tags = item.get("hashtags", item.get("tags", []))
        hashtags: List[str] = []
        if isinstance(raw_tags, list):
            for tag in raw_tags:
                clean_t = str(tag).strip()
                if clean_t:
                    hashtags.append(clean_t if clean_t.startswith("#") else f"#{clean_t}")
        elif isinstance(raw_tags, str):
            for part in raw_tags.replace(",", " ").split():
                clean_p = part.strip()
                if clean_p:
                    hashtags.append(clean_p if clean_p.startswith("#") else f"#{clean_p}")

        try:
            viral_score = float(item.get("viral_score", item.get("score", 8.0)))
        except (ValueError, TypeError):
            viral_score = 8.0

        clips.append(
            ClipMetadata(
                start_time=round(start_time, 2),
                end_time=round(end_time, 2),
                hook_title=hook_title,
                description=description,
                hashtags=hashtags,
                viral_score=round(viral_score, 2),
            )
        )

    return clips


class CuratorAnalyzer:
    """Motor de inteligência artificial para curadoria e detecção de cortes virais."""

    def __init__(self, api_key: str = "", model_name: str = "gemini-2.5-flash") -> None:
        self.api_key = (
            api_key
            or getattr(settings, "GEMINI_API_KEY", "")
            or os.environ.get("GEMINI_API_KEY", "")
        ).strip()
        self.model_name = model_name
        self.client = None

        if self.api_key:
            if genai is not None:
                try:
                    self.client = genai.Client(api_key=self.api_key)
                except Exception as exc:
                    logger.warning("Falha ao inicializar Google GenAI Client: %s", exc)
            else:
                logger.warning("Biblioteca google-genai não disponível no ambiente.")

    def _call_gemini_api(self, prompt: str) -> str:
        """Executa a chamada direta à API do Gemini."""
        if not self.client:
            raise RuntimeError("Cliente do Gemini não inicializado.")

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )
        return getattr(response, "text", "") or ""

    def analyze_transcript(
        self,
        transcript_formatted: Optional[str],
        max_clips: int = 3,
        min_duration: int = 45,
        max_duration: int = 90,
    ) -> List[ClipMetadata]:
        """Analisa a transcrição com marcações temporais e identifica os momentos virais."""
        if not transcript_formatted or not str(transcript_formatted).strip():
            logger.debug("Transcrição vazia fornecida para análise.")
            return []

        if not self.api_key:
            logger.warning("GEMINI_API_KEY não configurada. Fallback seguro ativado: nenhum corte gerado.")
            return []

        prompt = (
            "Você é um editor sênior especializado em cortes virais para TikTok, YouTube Shorts e Reels.\n"
            "Analise a seguinte transcrição com marcações de tempo e selecione os momentos com MAIOR potencial viral.\n"
            "\n"
            "Critérios de seleção:\n"
            "- Momentos de alta retenção: polêmicas, revelações chocantes, conselhos transformadores ou histórias engraçadas.\n"
            f"- Cada corte DEVE durar entre {min_duration} e {max_duration} segundos.\n"
            f"- Selecione no máximo {max_clips} cortes no total.\n"
            "- Escreva um 'hook_title' em português, com letras maiúsculas ou gancho irresistível (máx 50 caracteres).\n"
            "- Crie uma legenda envolvente em 'description'.\n"
            "- Inclua de 3 a 5 'hashtags' virais com #.\n"
            "- Atribua um 'viral_score' de 0.0 a 10.0.\n"
            "\n"
            "Retorne ESTRITAMENTE um JSON com uma lista de objetos no seguinte esquema:\n"
            "[\n"
            "  {\n"
            '    "start_time": 45.0,\n'
            '    "end_time": 105.0,\n'
            '    "hook_title": "O MAIOR ERRO QUE COMETI!",\n'
            '    "description": "Veja o momento em que...",\n'
            '    "hashtags": ["#shorts", "#podcast", "#cortes"],\n'
            '    "viral_score": 9.5\n'
            "  }\n"
            "]\n"
            "\n"
            "Transcrição:\n"
            f"{transcript_formatted}\n"
        )

        try:
            raw_response = self._call_gemini_api(prompt)
            clips = parse_llm_clip_response(
                raw_response, min_duration=min_duration, max_duration=max_duration
            )
            return clips[:max_clips]
        except Exception as exc:
            logger.warning("Falha na chamada ao modelo Gemini: %s", exc)
            return []
