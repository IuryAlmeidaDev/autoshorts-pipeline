"""Renderizador de quadros gráficos com Pillow para vídeos de Quiz em formato 9:16."""

from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont

from src.quiz.models import QuizQuestion, QuizTheme


class QuizFrameRenderer:
    """Renderiza telas e animações visuais para vídeos de Quiz 1080x1920."""

    WIDTH = 1080
    HEIGHT = 1920

    def __init__(self, theme: Optional[QuizTheme] = None):
        self.theme = theme or QuizTheme()
        self._font_cache = {}
        self._base_bg: Optional[Image.Image] = None

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Carrega e armazena em cache fontes TrueType com fallback seguro."""
        if size in self._font_cache:
            return self._font_cache[size]

        font_candidates = [
            self.theme.font_path,
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
        ]

        font = None
        for path in font_candidates:
            if path and Path(path).exists():
                try:
                    font = ImageFont.truetype(path, size)
                    break
                except Exception:
                    continue

        if font is None:
            font = ImageFont.load_default()

        self._font_cache[size] = font
        return font

    def get_background(self) -> Image.Image:
        """Gera ou reutiliza o fundo em gradiente vertical estilizado com acentos neon."""
        if self._base_bg is not None:
            return self._base_bg.copy()

        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), self.theme.bg_gradient_top)
        draw = ImageDraw.Draw(img)

        half = self.HEIGHT // 2
        top_c = self.theme.bg_gradient_top
        mid_c = self.theme.bg_gradient_mid
        bot_c = self.theme.bg_gradient_bot

        # Metade superior
        for y in range(half):
            factor = y / half
            r = int(top_c[0] + (mid_c[0] - top_c[0]) * factor)
            g = int(top_c[1] + (mid_c[1] - top_c[1]) * factor)
            b = int(top_c[2] + (mid_c[2] - top_c[2]) * factor)
            draw.line([(0, y), (self.WIDTH, y)], fill=(r, g, b))

        # Metade inferior
        for y in range(half, self.HEIGHT):
            factor = (y - half) / half
            r = int(mid_c[0] + (bot_c[0] - mid_c[0]) * factor)
            g = int(mid_c[1] + (bot_c[1] - mid_c[1]) * factor)
            b = int(mid_c[2] + (bot_c[2] - mid_c[2]) * factor)
            draw.line([(0, y), (self.WIDTH, y)], fill=(r, g, b))

        # Círculos decorativos sutis no fundo (luz ambiente difusa)
        ambient_layer = Image.new("RGBA", (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
        ambient_draw = ImageDraw.Draw(ambient_layer)
        ambient_draw.ellipse(
            [-100, -100, 450, 450], fill=(139, 92, 246, 25)
        )  # Brilho roxo topo esquerdo
        ambient_draw.ellipse(
            [700, 1400, 1250, 1950], fill=(59, 130, 246, 20)
        )  # Brilho azul rodapé direito

        img = Image.alpha_composite(img.convert("RGBA"), ambient_layer).convert("RGB")
        self._base_bg = img
        return self._base_bg.copy()

    def wrap_text(
        self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw
    ) -> List[str]:
        """Quebra linhas de texto automaticamente para caber na largura disponível."""
        lines = []
        words = text.split()
        current_line: List[str] = []

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)

        if current_line:
            lines.append(" ".join(current_line))
        return lines

    def render_intro_frame(self, total_questions: int = 3) -> Image.Image:
        """Renderiza a tela inicial de gancho visual para reter a audiência nos primeiros 3s."""
        img = self.get_background()
        draw = ImageDraw.Draw(img)

        f_badge = self._get_font(32)
        f_hero = self._get_font(56)
        f_sub = self._get_font(40)
        f_cta = self._get_font(42)

        # Header Badge
        draw.rounded_rectangle(
            [160, 240, 920, 320],
            radius=40,
            fill=(30, 27, 75),
            outline=self.theme.accent_color,
            width=4,
        )
        draw.text(
            (540, 280),
            self.theme.title,
            fill=(250, 204, 21),
            font=f_badge,
            anchor="mm",
        )

        # Card Central
        card_box = [80, 480, 1000, 1220]
        draw.rounded_rectangle(
            card_box,
            radius=36,
            fill=(19, 27, 46),
            outline=(99, 102, 241),
            width=4,
        )

        # Ícone de cérebro / troféu destacado
        draw.text((540, 620), "⚡ 🧠 ⚡", fill=(255, 255, 255), font=f_hero, anchor="mm")

        # Texto Principal do Gancho
        draw.text(
            (540, 750),
            "TESTE SEU CÉREBRO!",
            fill=(255, 255, 255),
            font=f_hero,
            anchor="mm",
        )
        draw.text(
            (540, 850),
            f"São apenas {total_questions} perguntas!",
            fill=(56, 189, 248),
            font=f_sub,
            anchor="mm",
        )
        draw.text(
            (540, 930),
            "Duvido acertar 3 de 3!",
            fill=(250, 204, 21),
            font=f_sub,
            anchor="mm",
        )

        # Badge CTA inferior
        draw.rounded_rectangle(
            [140, 1030, 940, 1130],
            radius=24,
            fill=(34, 197, 94),
        )
        draw.text(
            (540, 1080),
            "PREPARE-SE! VAI COMEÇAR...",
            fill=(255, 255, 255),
            font=f_cta,
            anchor="mm",
        )

        # Rodapé
        draw.text(
            (540, 1680),
            "👇 Comente sua pontuação no final!",
            fill=(241, 245, 249),
            font=f_sub,
            anchor="mm",
        )

        return img

    def render_question_frame(
        self,
        question: QuizQuestion,
        q_idx: int,
        total_questions: int,
        progress: float = 1.0,
        show_reveal: bool = False,
    ) -> Image.Image:
        """Renderiza o quadro da questão atual (modo leitura, contagem regressiva ou resposta revelada)."""
        img = self.get_background()
        draw = ImageDraw.Draw(img)

        f_badge = self._get_font(28)
        f_num = self._get_font(42)
        f_q = self._get_font(42)
        f_opt = self._get_font(36)
        f_tag = self._get_font(32)
        f_cta = self._get_font(38)

        # 1. Top Badge de Categoria
        draw.rounded_rectangle(
            [180, 130, 900, 200],
            radius=35,
            fill=(30, 27, 75),
            outline=self.theme.accent_color,
            width=3,
        )
        draw.text(
            (540, 165),
            self.theme.title,
            fill=(250, 204, 21),
            font=f_badge,
            anchor="mm",
        )

        # 2. Número da Questão
        draw.text(
            (540, 255),
            f"PERGUNTA {q_idx + 1} DE {total_questions}",
            fill=(255, 255, 255),
            font=f_num,
            anchor="mm",
        )

        # 3. Card da Pergunta
        q_box = [80, 320, 1000, 680]
        draw.rounded_rectangle(
            q_box,
            radius=30,
            fill=self.theme.card_color,
            outline=self.theme.card_border,
            width=3,
        )

        # Texto da Pergunta quebrado em linhas
        lines = self.wrap_text(question.question, f_q, max_width=840, draw=draw)
        line_height = 54
        start_y = 500 - ((len(lines) * line_height) // 2) + 20
        for i, line in enumerate(lines):
            draw.text(
                (540, start_y + i * line_height),
                line,
                fill=(255, 255, 255),
                font=f_q,
                anchor="mm",
            )

        # 4. Barra de Progresso / Temporizador
        draw.rounded_rectangle([120, 720, 960, 750], radius=15, fill=(30, 41, 59))
        if not show_reveal:
            clamped_p = max(0.0, min(progress, 1.0))
            w = int(840 * clamped_p)
            if w > 8:
                if clamped_p > 0.5:
                    p_col = (34, 197, 94)  # Verde
                elif clamped_p > 0.25:
                    p_col = (234, 179, 8)  # Amarelo
                else:
                    p_col = (239, 68, 68)  # Vermelho
                draw.rounded_rectangle(
                    [120, 720, 120 + w, 750], radius=15, fill=p_col
                )
        else:
            # Revelado: barra cheia em verde neon
            draw.rounded_rectangle(
                [120, 720, 960, 750], radius=15, fill=(34, 197, 94)
            )

        # 5. Opções de Resposta
        letters = ["A", "B", "C", "D", "E"]
        y_start = 810
        card_h = 130
        gap = 35

        for i, opt_text in enumerate(question.options):
            y = y_start + i * (card_h + gap)
            letter = letters[i] if i < len(letters) else str(i + 1)
            is_correct = (i == question.correct_index)

            if not show_reveal:
                # Estado Normal / Neutro
                draw.rounded_rectangle(
                    [80, y, 1000, y + card_h],
                    radius=24,
                    fill=(24, 33, 54),
                    outline=(51, 65, 85),
                    width=2,
                )
                # Badge da Letra (Círculo Índigo)
                draw.ellipse([110, y + 25, 190, y + 105], fill=(49, 46, 129))
                draw.text(
                    (150, y + 65),
                    letter,
                    fill=(255, 255, 255),
                    font=f_opt,
                    anchor="mm",
                )
                # Texto da Opção
                draw.text(
                    (220, y + 65),
                    opt_text,
                    fill=(241, 245, 249),
                    font=f_opt,
                    anchor="lm",
                )
            else:
                # Estado Revelado
                if is_correct:
                    # Alternativa Correta em Destaque
                    draw.rounded_rectangle(
                        [80, y, 1000, y + card_h],
                        radius=24,
                        fill=self.theme.correct_color,
                        outline=self.theme.correct_border,
                        width=5,
                    )
                    # Badge da Letra em Verde Neon
                    draw.ellipse([110, y + 25, 190, y + 105], fill=(34, 197, 94))
                    draw.text(
                        (150, y + 65),
                        "✔",
                        fill=(255, 255, 255),
                        font=f_opt,
                        anchor="mm",
                    )
                    # Texto da Opção
                    draw.text(
                        (220, y + 65),
                        opt_text,
                        fill=(255, 255, 255),
                        font=f_opt,
                        anchor="lm",
                    )
                    # Tag "CORRETO! ✔" na ponta direita
                    draw.rounded_rectangle(
                        [780, y + 35, 970, y + 95],
                        radius=16,
                        fill=(34, 197, 94),
                    )
                    draw.text(
                        (875, y + 65),
                        "CORRETO!",
                        fill=(255, 255, 255),
                        font=f_tag,
                        anchor="mm",
                    )
                else:
                    # Alternativas Incorretas (Apagadas)
                    draw.rounded_rectangle(
                        [80, y, 1000, y + card_h],
                        radius=24,
                        fill=(15, 23, 42),
                        outline=(30, 41, 59),
                        width=1,
                    )
                    draw.ellipse([110, y + 25, 190, y + 105], fill=(30, 41, 59))
                    draw.text(
                        (150, y + 65),
                        letter,
                        fill=(100, 116, 139),
                        font=f_opt,
                        anchor="mm",
                    )
                    draw.text(
                        (220, y + 65),
                        opt_text,
                        fill=(100, 116, 139),
                        font=f_opt,
                        anchor="lm",
                    )

        # 6. Rodapé Dinâmico
        if not show_reveal:
            draw.text(
                (540, 1720),
                "💬 Comente sua resposta rápido!",
                fill=(250, 204, 21),
                font=f_cta,
                anchor="mm",
            )
        else:
            draw.text(
                (540, 1720),
                "🔥 Você acertou? Deixe o like!",
                fill=(34, 197, 94),
                font=f_cta,
                anchor="mm",
            )

        return img

    def render_outro_frame(self) -> Image.Image:
        """Renderiza a tela de encerramento com forte apelo para comentários e inscrição."""
        img = self.get_background()
        draw = ImageDraw.Draw(img)

        f_hero = self._get_font(52)
        f_sub = self._get_font(40)
        f_badge = self._get_font(34)

        # Card de resultado
        draw.rounded_rectangle(
            [80, 520, 1000, 1260],
            radius=36,
            fill=(19, 27, 46),
            outline=(139, 92, 246),
            width=4,
        )

        draw.text((540, 660), "🏆 FIM DO DESAFIO! 🏆", fill=(250, 204, 21), font=f_hero, anchor="mm")
        draw.text((540, 800), "Quantas você acertou?", fill=(255, 255, 255), font=f_sub, anchor="mm")

        # Opções de pontuação
        draw.rounded_rectangle([200, 890, 880, 970], radius=20, fill=(30, 41, 59))
        draw.text((540, 930), "0 a 1: Principiante 🐣", fill=(241, 245, 249), font=f_badge, anchor="mm")

        draw.rounded_rectangle([200, 1000, 880, 1080], radius=20, fill=(30, 41, 59))
        draw.text((540, 1040), "2 acertos: Quase Gênio 💡", fill=(56, 189, 248), font=f_badge, anchor="mm")

        draw.rounded_rectangle([200, 1110, 880, 1190], radius=20, fill=(22, 101, 52), outline=(34, 197, 94), width=3)
        draw.text((540, 1150), "3 de 3: Cérebro Supremo! 🧠👑", fill=(255, 255, 255), font=f_badge, anchor="mm")

        # CTA final
        draw.text(
            (540, 1450),
            "💬 Deixe sua pontuação nos comentários!",
            fill=(250, 204, 21),
            font=f_sub,
            anchor="mm",
        )
        draw.text(
            (540, 1550),
            "🔔 Se inscreva para o próximo teste!",
            fill=(255, 255, 255),
            font=f_sub,
            anchor="mm",
        )

        return img
