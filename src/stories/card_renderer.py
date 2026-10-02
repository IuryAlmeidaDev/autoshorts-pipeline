"""Módulo de renderização do card visual do Reddit em alta resolução."""

import logging
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from src.stories.models import RedditStory

logger = logging.getLogger(__name__)

DEFAULT_FONT = "C:/Windows/Fonts/segoeuib.ttf"
DEFAULT_REGULAR_FONT = "C:/Windows/Fonts/segoeui.ttf"


class RedditCardRenderer:
    """Renderiza um card visual estilo Reddit Dark Mode com acabamento profissional."""

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
        story: RedditStory,
        card_width: int = 940,
        padding: int = 40,
    ) -> Image.Image:
        """Gera imagem PNG transparente do card do post do Reddit."""
        title_font = self._get_font(38, bold=True)
        meta_bold_font = self._get_font(24, bold=True)
        meta_regular_font = self._get_font(22, bold=False)
        badge_font = self._get_font(20, bold=True)

        inner_width = card_width - (padding * 2)

        # 1. Quebra de linha do título
        title_lines = self._wrap_text(story.title, title_font, inner_width)
        line_height = 48
        title_block_h = len(title_lines) * line_height

        # 2. Cálculo da altura total do card
        header_h = 70
        footer_h = 60
        spacing = 24
        card_height = padding + header_h + spacing + title_block_h + spacing + footer_h + padding

        # Cria imagem RGBA transparente
        card = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(card)

        # Fundo do card: Rounded Rectangle com acabamento moderno estilo Reddit Dark
        radius = 28
        # Sombra sutil
        shadow_offset = 6
        draw.rounded_rectangle(
            [0, shadow_offset, card_width, card_height],
            radius=radius,
            fill=(0, 0, 0, 90),
        )
        # Corpo do card
        draw.rounded_rectangle(
            [0, 0, card_width, card_height - shadow_offset],
            radius=radius,
            fill=(26, 26, 27, 248),
            outline=(52, 53, 54, 255),
            width=2,
        )

        curr_y = padding

        # 3. Cabeçalho: Ícone do subreddit + r/nome + autor
        icon_size = 52
        # Círculo laranja do subreddit
        draw.ellipse(
            [padding, curr_y, padding + icon_size, curr_y + icon_size],
            fill=(255, 69, 0, 255),  # Laranja oficial Reddit #FF4500
        )
        # Letra r/ dentro do ícone
        draw.text(
            (padding + 14, curr_y + 12),
            "r/",
            font=badge_font,
            fill=(255, 255, 255, 255),
        )

        # Texto do subreddit
        text_x = padding + icon_size + 16
        draw.text(
            (text_x, curr_y + 2),
            story.subreddit,
            font=meta_bold_font,
            fill=(215, 218, 220, 255),
        )

        # Detalhes do autor e tempo
        meta_str = f"• Postado por {story.author} • há 3h"
        draw.text(
            (text_x, curr_y + 28),
            meta_str,
            font=meta_regular_font,
            fill=(129, 131, 132, 255),
        )

        curr_y += header_h + spacing

        # 4. Título da história em destaque
        for line in title_lines:
            draw.text(
                (padding, curr_y),
                line,
                font=title_font,
                fill=(255, 255, 255, 255),
            )
            curr_y += line_height

        curr_y += spacing

        # 5. Rodapé: Pílula de Upvotes e Comentários
        # Pílula de Upvote
        pill_h = 44
        pill_up_w = 170
        draw.rounded_rectangle(
            [padding, curr_y, padding + pill_up_w, curr_y + pill_h],
            radius=22,
            fill=(39, 39, 41, 255),
            outline=(52, 53, 54, 255),
            width=1,
        )
        # Seta de Upvote estilizada (triângulo laranja)
        arrow_x = padding + 16
        arrow_y = curr_y + 14
        draw.polygon(
            [
                (arrow_x + 8, arrow_y),
                (arrow_x, arrow_y + 14),
                (arrow_x + 16, arrow_y + 14),
            ],
            fill=(255, 69, 0, 255),
        )
        draw.text(
            (arrow_x + 24, curr_y + 10),
            story.upvotes,
            font=meta_bold_font,
            fill=(255, 255, 255, 255),
        )

        # Pílula de Comentários
        pill_com_x = padding + pill_up_w + 14
        pill_com_w = 230
        draw.rounded_rectangle(
            [pill_com_x, curr_y, pill_com_x + pill_com_w, curr_y + pill_h],
            radius=22,
            fill=(39, 39, 41, 255),
            outline=(52, 53, 54, 255),
            width=1,
        )
        # Ícone de balão de comentário
        b_x = pill_com_x + 16
        b_y = curr_y + 14
        draw.rectangle([b_x, b_y, b_x + 18, b_y + 12], fill=(129, 131, 132, 255))
        draw.polygon([(b_x + 3, b_y + 12), (b_x + 3, b_y + 16), (b_x + 8, b_y + 12)], fill=(129, 131, 132, 255))
        draw.text(
            (b_x + 26, curr_y + 10),
            f"{story.comments_count} comentários",
            font=meta_regular_font,
            fill=(129, 131, 132, 255),
        )

        return card
