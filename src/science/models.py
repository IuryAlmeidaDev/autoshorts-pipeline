"""Modelos de dados para o módulo de Artigos Científicos e Descobertas."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ScienceArticle:
    """Estrutura de dados representando um artigo/avanço científico para Shorts/TikTok."""

    title: str
    journal: str = "Nature Aging"
    category: str = "BIOTECNOLOGIA"
    doi: str = "10.1038/s43587-024"
    reads_count: str = "94.2k"
    hook_text: str = ""
    full_script: str = ""
    tags: List[str] = field(
        default_factory=lambda: [
            "#Shorts",
            "#ciencia",
            "#curiosidades",
            "#tecnologia",
            "#universo",
            "#tiktok",
        ]
    )

    def __post_init__(self):
        if not self.hook_text and self.title:
            self.hook_text = self.title
        if not self.full_script:
            self.full_script = self.title
