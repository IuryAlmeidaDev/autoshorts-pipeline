"""Módulo base para publicadores de conteúdo em redes sociais."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union


@dataclass
class PublishResult:
    """Resultado padronizado da tentativa de publicação em qualquer plataforma."""

    success: bool
    platform: str
    post_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None


class BasePublisher(ABC):
    """Classe base abstrata para publicadores do AutoShorts."""

    @abstractmethod
    def publish(
        self,
        video_path: Union[Path, str],
        title: str,
        description: str = "",
        hashtags: Optional[List[str]] = None,
    ) -> PublishResult:
        """Publica um vídeo na respectiva plataforma.

        Args:
            video_path: Caminho para o arquivo de vídeo renderizado.
            title: Título principal do vídeo.
            description: Descrição ou texto complementar.
            hashtags: Lista de tags ou palavras-chave para o post.

        Returns:
            PublishResult com status de sucesso, id, url ou mensagem de erro.
        """
        pass

    @staticmethod
    def format_caption(
        title: str,
        description: str = "",
        hashtags: Optional[List[str]] = None,
    ) -> str:
        """Formata título, descrição e hashtags em uma legenda unificada e limpa.

        Args:
            title: Título principal.
            description: Descrição opcional.
            hashtags: Lista opcional de hashtags (com ou sem '#').

        Returns:
            String formatada com parágrafos separados.
        """
        clean_title = (title or "").strip()
        clean_desc = (description or "").strip()

        parts = []
        if clean_title:
            parts.append(clean_title)
        if clean_desc:
            parts.append(clean_desc)

        if hashtags:
            clean_tags = []
            for tag in hashtags:
                tag_str = str(tag).strip()
                if not tag_str:
                    continue
                tag_name = tag_str.lstrip("#")
                if tag_name:
                    clean_tags.append(f"#{tag_name}")
            if clean_tags:
                parts.append(" ".join(clean_tags))

        return "\n\n".join(parts)
