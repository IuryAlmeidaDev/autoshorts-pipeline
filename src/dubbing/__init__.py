"""Módulo de dublagem e síntese de voz para vídeos do AutoShorts."""

from src.dubbing.voice_synthesizer import (
    DEFAULT_FEMALE_VOICE,
    DEFAULT_MALE_VOICE,
    VoiceSynthesizer,
    VoiceSynthesisError,
)
from src.editor.subtitles import WordTimestamp

__all__ = [
    "VoiceSynthesizer",
    "VoiceSynthesisError",
    "DEFAULT_MALE_VOICE",
    "DEFAULT_FEMALE_VOICE",
    "WordTimestamp",
]
