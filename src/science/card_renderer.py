"""Módulo de renderização do card visual de Artigo Científico (Nature/Science/MIT)."""

import logging
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from src.science.models import ScienceArticle

logger = logging.getLogger(__name__)

DEFAULT_FONT = "C:/Windows/Fonts/segoeuib.ttf"
DEFAULT_REGULAR_FONT = "C:/Windows/Fonts/segoeui.ttf"


class ScienceCardRenderer:
    """Renderiza um card moderno estilo Scientific Paper / Breaking Science com estética futurista."""

    def __init__(
        self,
        bold_font_path: str = DEFAULT_FONT,
        regular_font_path: str = DEFAULT_REGULAR_FONT,
    ):
        self.bold_font_path = bold_font_path
        self.regular_font_path = regular_font_path

    def _get_font(self, size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
        font_path = self.bold_font_path if bold else self.regular_font_path
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            try:
                return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", size)
            except Exception:
                return ImageFont.load_default()

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
        words = text.split()
        if not words:
            return []

        lines = []
        current = words[0]

        for word in words[1:]:
            test_line = f"{current} {word}"
            bbox = font.getbbox(test_line)
            line_w = bbox[2] - bbox[0]
            if line_w <= max_width:
                current = test_line
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def render_card(
        self,
        article: ScienceArticle,
        card_width: int = 960,
        padding: int = 40,
    ) -> Image.Image:
        """Gera imagem PNG transparente do card de artigo científico."""
        title_font = self._get_font(38, bold=True)
        meta_bold_font = self._get_font(24, bold=True)
        meta_regular_font = self._get_font(21, bold=False)
        badge_font = self._get_font(19, bold=True)

        inner_width = card_width - (padding * 2)

        # 1. Quebra de linha do título
        title_lines = self._wrap_text(article.title, title_font, inner_width)
        line_height = 48
        title_block_h = len(title_lines) * line_height

        # 2. Dimensões do card
        header_h = 65
        footer_h = 55
        spacing = 22
        card_height = padding + header_h + spacing + title_block_h + spacing + footer_h + padding

        card = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(card)

        # 3. Sombra e Fundo Futurista Dark com borda ciano
        radius = 26
        shadow_offset = 6
        draw.rounded_rectangle(
            [0, shadow_offset, card_width, card_height],
            radius=radius,
            fill=(0, 0, 0, 110),
        )
        draw.rounded_rectangle(
            [0, 0, card_width, card_height - shadow_offset],
            radius=radius,
            fill=(8, 14, 26, 250),  # Deep Navy Dark
            outline=(14, 165, 233, 255),  # Cyan Border (#0EA5E9)
            width=2,
        )

        curr_y = padding

        # 4. Cabeçalho: Badge da Revista + Nome da Revista + Categoria
        badge_w, badge_h = 44, 44
        # Círculo Ciano/Azul da revista
        draw.rounded_rectangle(
            [padding, curr_y, padding + badge_w, curr_y + badge_h],
            radius=12,
            fill=(14, 165, 233, 255),
        )
        # Letra inicial no ícone
        initial = article.journal[:1].upper() if article.journal else "S"
        draw.text(
            (padding + 14, curr_y + 8),
            initial,
            font=badge_font,
            fill=(255, 255, 255, 255),
        )

        # Texto da Revista
        text_x = padding + badge_w + 16
        draw.text(
            (text_x, curr_y + 2),
            f"{article.journal} • Revisado por Pares",
            font=meta_bold_font,
            fill=(224, 242, 254, 255),  # Light Cyan
        )
        draw.text(
            (text_x, curr_y + 26),
            f"Artigo Científico Internacional • Publicação Recente",
            font=meta_regular_font,
            fill=(148, 163, 184, 255),  # Slate Gray
        )

        # Tag de Categoria no canto superior direito
        cat_text = f"● {article.category.upper()}"
        bbox_cat = badge_font.getbbox(cat_text)
        cat_w = bbox_cat[2] - bbox_cat[0] + 20
        cat_x = card_width - padding - cat_w
        draw.rounded_rectangle(
            [cat_x, curr_y + 4, cat_x + cat_w, curr_y + 36],
            radius=16,
            fill=(12, 74, 110, 220),  # Dark Cyan Pill
            outline=(56, 189, 248, 255),
            width=1,
        )
        draw.text(
            (cat_x + 10, curr_y + 8),
            cat_text,
            font=badge_font,
            fill=(56, 189, 248, 255),
        )

        curr_y += header_h + spacing

        # 5. Título do Artigo em Destaque
        for line in title_lines:
            draw.text(
                (padding, curr_y),
                line,
                font=title_font,
                fill=(255, 255, 255, 255),
            )
            curr_y += line_height

        curr_y += spacing

        # 6. Rodapé: Pílula de DOI e Badge de Verificação
        doi_str = f"DOI: {article.doi}"
        bbox_doi = meta_regular_font.getbbox(doi_str)
        pill_doi_w = (bbox_doi[2] - bbox_doi[0]) + 28
        draw.rounded_rectangle(
            [padding, curr_y, padding + pill_doi_w, curr_y + 40],
            radius=20,
            fill=(15, 23, 42, 255),
            outline=(51, 65, 85, 255),
            width=1,
        )
        draw.text(
            (padding + 14, curr_y + 8),
            doi_str,
            font=meta_regular_font,
            fill=(148, 163, 184, 255),
        )

        # Badge de Validação Científica
        val_str = f"Estudo Verificado • {article.reads_count}"
        bbox_val = meta_bold_font.getbbox(val_str)
        val_w = (bbox_val[2] - bbox_val[0]) + 32
        val_x = padding + pill_doi_w + 14
        draw.rounded_rectangle(
            [val_x, curr_y, val_x + val_w, curr_y + 40],
            radius=20,
            fill=(6, 78, 59, 180),  # Emerald Dark
            outline=(52, 211, 153, 255),
            width=1,
        )
        draw.text(
            (val_x + 16, curr_y + 8),
            val_str,
            font=meta_bold_font,
            fill=(167, 243, 208, 255),  # Emerald Light
        )

        return card
