"""Módulo de criação automática de vídeos de Divulgação de Artigos Científicos."""

from src.science.ai_curator import AIScienceCurator
from src.science.card_renderer import ScienceCardRenderer
from src.science.generator import ScienceGenerationError, ScienceShortsGenerator
from src.science.models import ScienceArticle

__all__ = [
    "ScienceArticle",
    "ScienceCardRenderer",
    "AIScienceCurator",
    "ScienceShortsGenerator",
    "ScienceGenerationError",
]
