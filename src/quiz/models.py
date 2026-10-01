"""Estruturas de dados para o gerador de vídeos de Quiz Viral."""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class QuizQuestion:
    """Representa uma questão do quiz com opções e resposta correta."""

    question: str
    options: List[str]
    correct_index: int  # 0 a len(options)-1
    explanation: str = ""

    def __post_init__(self):
        if not self.question.strip():
            raise ValueError("O texto da pergunta não pode ser vazio.")
        if len(self.options) < 2:
            raise ValueError("A questão deve ter pelo menos duas opções.")
        if not (0 <= self.correct_index < len(self.options)):
            raise ValueError(
                f"correct_index {self.correct_index} inválido para {len(self.options)} opções."
            )

    @property
    def correct_letter(self) -> str:
        """Retorna a letra correspondente à alternativa correta (A, B, C, D...)."""
        letters = ["A", "B", "C", "D", "E"]
        if self.correct_index < len(letters):
            return letters[self.correct_index]
        return str(self.correct_index + 1)

    @property
    def correct_text(self) -> str:
        """Retorna o texto da alternativa correta."""
        return self.options[self.correct_index]


@dataclass
class QuizTheme:
    """Configuração visual de temas e cores do Quiz."""

    title: str = "DESAFIO DE CONHECIMENTOS"
    bg_gradient_top: Tuple[int, int, int] = (10, 15, 30)
    bg_gradient_mid: Tuple[int, int, int] = (28, 22, 58)
    bg_gradient_bot: Tuple[int, int, int] = (8, 12, 22)
    accent_color: Tuple[int, int, int] = (139, 92, 246)  # Roxo vibrante
    card_color: Tuple[int, int, int] = (19, 27, 46)
    card_border: Tuple[int, int, int] = (59, 130, 246)  # Azul neon
    correct_color: Tuple[int, int, int] = (22, 101, 52)  # Verde esmeralda escuro
    correct_border: Tuple[int, int, int] = (34, 197, 94)  # Verde neon
    text_color: Tuple[int, int, int] = (255, 255, 255)
    font_path: str = "C:/Windows/Fonts/segoeuib.ttf"


@dataclass
class QuizData:
    """Conjunto completo de dados para renderizar um vídeo de quiz."""

    title: str
    questions: List[QuizQuestion]
    intro_text: str = (
        "Duvido você acertar essas três perguntas de conhecimentos gerais! "
        "Já deixa nos comentários quantas você acertou!"
    )
    outro_text: str = (
        "E aí, quantas você acertou? Deixe seu resultado nos comentários "
        "e se inscreva no canal para o próximo desafio!"
    )
    theme: QuizTheme = field(default_factory=QuizTheme)
